import os
import uuid
import random
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models.candidate import CandidateProfile
from backend.app.models.opportunity import Opportunity
from backend.app.models.resume import ResumeDocument
from backend.app.models.resume_version import ResumeVersion
from backend.app.models.application import ApplicationRecord
from backend.app.models.ai_audit import AIActionAuditLog
from backend.app.services.latex_compiler import compile_latex
from backend.app.services.latex_templates import build_latex_template
from backend.app.services.resume_tailorer import tailor_resume_for_opportunity
from backend.app.services.ai.service import (
    validate_tailoring_safety,
    ResumeTailoringOutput,
    ai_service
)
from backend.app.services.ai.types import TaskType, ProviderType
from backend.app.services.ai.task_router import TASK_ROUTING_MAP
from backend.app.services.global_ai_command_service import execute_consequential_action

from backend.app.core.auth import create_access_token

client = TestClient(app)

def auth_headers(user_id: int) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}



# =========================================================================
# Test 1: Groq is invoked during resume tailoring when GROQ_API_KEY is configured
# =========================================================================
def test_groq_invoked_during_resume_tailoring():
    db = SessionLocal()
    try:
        user_id = random.randint(100000, 999999)
        cand = CandidateProfile(
            user_id=user_id,
            name="Tailor Groq Test",
            skills=[{"name": "Python", "level": "advanced", "category": "language"}]
        )
        opp = Opportunity(
            user_id=user_id,
            title="Python Software Engineer",
            normalized_title="python software engineer",
            company_name="PyCorp",
            original_url=f"https://pycorp.example.com/{uuid.uuid4()}",
            source_platform="direct",
            required_skills=["Python", "FastAPI"]
        )
        db.add_all([cand, opp])
        db.commit()

        with patch("backend.app.api.resumes.ai_service.tailor_resume", new_callable=AsyncMock) as mock_tailor:
            mock_tailor.return_value = {
                "success": True,
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "latency_ms": 150.0,
                "tokens": 300,
                "data": {
                    "matched_skills": ["Python"],
                    "missing_skills": ["FastAPI"],
                    "bullet_refinements": [],
                    "suggested_section_order": ["Skills", "Projects"],
                    "rationale": "Strong Python candidate matching PyCorp backend requirements."
                }
            }
            res = client.post(
                "/api/resumes/tailor",
                json={"opportunity_id": opp.id, "template_id": "minimal_professional"},
                headers=auth_headers(user_id)
            )
            assert res.status_code == 200
            data = res.json()
            assert data["user_id"] == user_id
            assert data["target_opportunity_id"] == opp.id
            assert mock_tailor.called
            # Verify prompt inputs received by tailor_resume
            call_kwargs = mock_tailor.call_args[1]
            assert call_kwargs["opportunity_data"]["title"] == "Python Software Engineer"
            assert call_kwargs["profile_data"]["name"] == "Tailor Groq Test"
    finally:
        db.close()


# =========================================================================
# Test 2: Groq is invoked during resume optimization when GROQ_API_KEY is configured
# =========================================================================
def test_groq_invoked_during_resume_optimization():
    db = SessionLocal()
    try:
        user_id = random.randint(100000, 999999)
        cand = CandidateProfile(
            user_id=user_id,
            name="Opt Groq Test",
            skills=[{"name": "Go", "level": "intermediate", "category": "language"}]
        )
        opp = Opportunity(
            user_id=user_id,
            title="Systems Engineer",
            normalized_title="systems engineer",
            company_name="GoScale Inc",
            original_url=f"https://goscale.example.com/{uuid.uuid4()}",
            source_platform="direct",
            required_skills=["Go", "Docker"]
        )
        db.add_all([cand, opp])
        db.commit()

        resume = ResumeDocument(
            user_id=user_id,
            title="Base Go Resume",
            template_id="minimal_professional",
            latex_content=r"\documentclass{article}\begin{document}Go Developer\end{document}",
            version=1
        )
        db.add(resume)
        db.commit()

        with patch("backend.app.api.resumes.ai_service.tailor_resume", new_callable=AsyncMock) as mock_tailor:
            mock_tailor.return_value = {
                "success": True,
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "latency_ms": 140.0,
                "tokens": 250,
                "data": {
                    "matched_skills": ["Go"],
                    "missing_skills": ["Docker"],
                    "bullet_refinements": [],
                    "suggested_section_order": ["Technical Skills", "Projects"],
                    "rationale": "Highlighted Go proficiency."
                }
            }
            res = client.post(
                f"/api/resumes/{resume.id}/optimize",
                json={"opportunity_id": opp.id},
                headers=auth_headers(user_id)
            )
            assert res.status_code == 200
            data = res.json()
            assert data["ai_provider"] == "groq"
            assert "Go" in data["verified_matching_skills"]
            assert "Docker" in data["missing_job_keywords"]
            assert mock_tailor.called
    finally:
        db.close()


# =========================================================================
# Test 3: Structured output validation correctly parses and validates Groq responses
# =========================================================================
def test_structured_output_validation_parses_groq_response():
    valid_payload = {
        "matched_skills": ["Python", "FastAPI"],
        "missing_skills": ["Kubernetes"],
        "bullet_refinements": [
            {"original": "Worked on backend", "suggested": "Architected backend"}
        ],
        "suggested_section_order": ["Education", "Skills", "Projects"],
        "rationale": "Focus on backend architecture."
    }
    output = ResumeTailoringOutput(**valid_payload)
    assert output.matched_skills == ["Python", "FastAPI"]
    assert len(output.bullet_refinements) == 1

    # Malformed response with invalid types must raise ValidationError
    with pytest.raises(ValidationError):
        ResumeTailoringOutput(matched_skills="Not a list")


# =========================================================================
# Test 4: Unsupported claims in Groq output are rejected or removed by safety filter
# =========================================================================
def test_unsupported_claims_rejected_by_safety_filter():
    candidate_skills = [
        {"name": "Python", "level": "advanced", "category": "language"},
        {"name": "FastAPI", "level": "advanced", "category": "framework"}
    ]
    # AI hallucinated Kubernetes and AWS, which the candidate never had
    ai_raw_output = {
        "matched_skills": ["Python", "FastAPI", "Kubernetes", "AWS Cloud"],
        "missing_skills": ["Terraform"],
        "bullet_refinements": [],
        "suggested_section_order": ["Skills", "Projects"],
        "rationale": "Aligned backend skills."
    }

    sanitized = validate_tailoring_safety(
        tailoring_data=ai_raw_output,
        candidate_skills=candidate_skills
    )

    # Kubernetes and AWS Cloud must be discarded from matched_skills
    assert "Python" in sanitized["matched_skills"]
    assert "FastAPI" in sanitized["matched_skills"]
    assert "Kubernetes" not in sanitized["matched_skills"]
    assert "AWS Cloud" not in sanitized["matched_skills"]
    assert "Kubernetes" in sanitized["dropped_unsupported_skills"]
    assert "AWS Cloud" in sanitized["dropped_unsupported_skills"]
    assert sanitized["zero_fabrication_validated"] is True


# =========================================================================
# Test 5: Missing GROQ_API_KEY produces a clear, recoverable error (HTTP 503)
# =========================================================================
def test_missing_groq_api_key_produces_503_error():
    db = SessionLocal()
    try:
        user_id = random.randint(100000, 999999)
        cand = CandidateProfile(user_id=user_id, name="Key Missing Test", skills=[])
        opp = Opportunity(
            user_id=user_id,
            title="Backend Lead",
            normalized_title="backend lead",
            company_name="Acme Corp",
            original_url=f"https://acme.example.com/{uuid.uuid4()}",
            source_platform="direct"
        )
        db.add_all([cand, opp])
        db.commit()

        with patch("backend.app.api.resumes.ai_service.tailor_resume", new_callable=AsyncMock) as mock_tailor:
            mock_tailor.return_value = {
                "success": False,
                "error": "GROQ_API_KEY is not configured in environment.",
                "provider": "groq",
                "retryable": False
            }
            res = client.post(
                "/api/resumes/tailor",
                json={"opportunity_id": opp.id},
                headers=auth_headers(user_id)
            )
            assert res.status_code == 503
            assert "AI Tailoring service unavailable" in res.json()["detail"]
            # Security: provider internals are NOT exposed to the client
            assert "GROQ_API_KEY is not configured" not in res.json()["detail"]
            assert "Original resume preserved" in res.json()["detail"]
    finally:
        db.close()


# =========================================================================
# Test 6: Groq failure (rate limit, outage, invalid output) preserves original resume state
# =========================================================================
def test_groq_failure_preserves_original_resume_state():
    db = SessionLocal()
    try:
        user_id = random.randint(100000, 999999)
        cand = CandidateProfile(user_id=user_id, name="Failure Safety Test", skills=[])
        opp = Opportunity(
            user_id=user_id,
            title="Platform Engineer",
            normalized_title="platform engineer",
            company_name="CloudCo",
            original_url=f"https://cloudco.example.com/{uuid.uuid4()}",
            source_platform="direct"
        )
        original_latex = r"\documentclass{article}\begin{document}Original Unchanged Resume\end{document}"
        resume = ResumeDocument(
            user_id=user_id,
            title="Preserved Resume",
            template_id="minimal_professional",
            latex_content=original_latex,
            version=1
        )
        db.add_all([cand, opp, resume])
        db.commit()
        db.refresh(resume)
        initial_id = resume.id

        with patch("backend.app.api.resumes.ai_service.tailor_resume", new_callable=AsyncMock) as mock_tailor:
            # Simulate Groq 429 Rate Limit
            mock_tailor.return_value = {
                "success": False,
                "error": "Rate limit exceeded (HTTP 429)",
                "provider": "groq",
                "retryable": True
            }
            res = client.post(
                f"/api/resumes/{initial_id}/optimize",
                json={"opportunity_id": opp.id},
                headers=auth_headers(user_id)
            )
            assert res.status_code == 503

            # Verify original resume was NOT modified
            db.refresh(resume)
            assert resume.version == 1
            assert resume.latex_content == original_latex
            assert resume.title == "Preserved Resume"
    finally:
        db.close()


# =========================================================================
# Test 7: No silent fallback to Ollama occurs when Groq fails
# =========================================================================
def test_no_silent_fallback_to_ollama_on_groq_failure():
    # Verify architectural policy mapping: RESUME_TAILORING must map strictly to GROQ
    assert TASK_ROUTING_MAP[TaskType.RESUME_TAILORING] == ProviderType.GROQ
    assert TASK_ROUTING_MAP[TaskType.RESUME_GENERATION] == ProviderType.GROQ

    db = SessionLocal()
    try:
        user_id = random.randint(100000, 999999)
        cand = CandidateProfile(user_id=user_id, name="No Fallback Test", skills=[])
        opp = Opportunity(
            user_id=user_id,
            title="ML Engineer",
            normalized_title="ml engineer",
            company_name="DeepLabs",
            original_url=f"https://deeplabs.example.com/{uuid.uuid4()}",
            source_platform="direct"
        )
        db.add_all([cand, opp])
        db.commit()

        with patch("backend.app.api.resumes.ai_service.tailor_resume", new_callable=AsyncMock) as mock_tailor:
            mock_tailor.return_value = {
                "success": False,
                "error": "Groq provider outage",
                "provider": "groq",
                "retryable": False
            }
            res = client.post(
                "/api/resumes/tailor",
                json={"opportunity_id": opp.id},
                headers=auth_headers(user_id)
            )
            # Must return 503 and never return 200 with fallback Ollama output
            assert res.status_code == 503
            # Check database: no resume was created with an Ollama provider
            tailored_resume = db.query(ResumeDocument).filter(
                ResumeDocument.user_id == user_id,
                ResumeDocument.target_opportunity_id == opp.id
            ).first()
            assert tailored_resume is None
    finally:
        db.close()


# =========================================================================
# Test 8: Empty candidate profiles do not receive fabricated information in LaTeX output
# =========================================================================
def test_empty_candidate_profile_receives_no_fabricated_info_in_latex():
    empty_profile = {
        "name": "",
        "email": "",
        "phone": "",
        "location": "",
        "degree": "",
        "college": "",
        "graduation_year": None,
        "cgpa": None,
        "github_url": "",
        "linkedin_url": "",
        "portfolio_url": "",
        "skills": [],
        "projects": [],
        "experience": [],
        "certifications": [],
        "achievements": []
    }
    latex = build_latex_template(empty_profile, template_id="minimal_professional")
    # Verify no fake dummy defaults appear in LaTeX
    assert "Krishna" not in latex
    assert "Pune Institute of Computer Technology" not in latex
    assert "PICT" not in latex
    assert "8.8" not in latex
    assert "Python, TypeScript, SQL, C++" not in latex
    assert "FastAPI, React, PyTorch, Node.js" not in latex
    assert "Docker, Git, PostgreSQL, Linux" not in latex


# =========================================================================
# Test 9: Missing skill categories remain empty without breaking LaTeX compilation
# =========================================================================
def test_missing_skill_categories_remain_empty_without_breaking_compilation():
    profile_with_empty_skills = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "degree": "B.S. Mathematics",
        "skills": [],  # Completely empty skills list
        "projects": [],
        "experience": []
    }
    latex = build_latex_template(profile_with_empty_skills, template_id="minimal_professional")
    assert r"\section*{Technical Skills}" not in latex
    # Pre-validate compilation through tectonic / reportlab compiler
    ok, path, compiler = compile_latex(latex, "test_empty_skills_resume")
    assert ok is True, f"Compilation failed: {path}"


# =========================================================================
# Test 10: Global AI command service calls prepare_tailored_resume without signature errors
# =========================================================================
def test_global_ai_command_service_prepare_tailored_resume_signature():
    db = SessionLocal()
    try:
        user_id = random.randint(100000, 999999)
        cand = CandidateProfile(
            user_id=user_id,
            name="Command Center User",
            degree="B.Tech Computer Science",
            skills=[{"name": "Rust", "level": "advanced", "category": "language"}]
        )
        opp = Opportunity(
            user_id=user_id,
            title="Rust Core Engineer",
            normalized_title="rust core engineer",
            company_name="RustLabs",
            original_url=f"https://rustlabs.example.com/{uuid.uuid4()}",
            source_platform="direct"
        )
        db.add_all([cand, opp])
        db.commit()

        # Create action audit record
        audit = AIActionAuditLog(
            conversation_id=None,
            action_type="prepare_tailored_resume",
            tool_name="prepare_tailored_resume",
            description="Generate tailored resume variant for RustLabs",
            status="pending_approval",
            data_payload={"opportunity_id": opp.id, "user_id": user_id, "template_id": "minimal_professional"}
        )
        db.add(audit)
        db.commit()

        # Execute action - must NOT fail with TypeError or signature mismatch
        result = execute_consequential_action(audit.id, db)
        assert "error" not in result
        assert result.get("status") == "executed"
        assert "RustLabs" in result.get("result_summary", "")

        # Verify tailored resume was persisted in DB
        resumes = db.query(ResumeDocument).filter(
            ResumeDocument.user_id == user_id,
            ResumeDocument.target_opportunity_id == opp.id
        ).all()
        assert len(resumes) >= 1
    finally:
        db.close()


# =========================================================================
# Test 11: Candidate profile queries are scoped to the authenticated user
# =========================================================================
def test_candidate_profile_scoped_to_authenticated_user():
    db = SessionLocal()
    try:
        user_a = random.randint(100000, 499999)
        user_b = random.randint(500000, 999999)

        # Create distinct profiles for user_a and user_b
        cand_a = CandidateProfile(user_id=user_a, name="User A Candidate", degree="Degree A")
        cand_b = CandidateProfile(user_id=user_b, name="User B Candidate", degree="Degree B")
        db.add_all([cand_a, cand_b])
        db.commit()

        # Query user A
        res_a = client.get("/api/candidate", headers=auth_headers(user_a))
        assert res_a.status_code == 200
        assert res_a.json()["name"] == "User A Candidate"

        # Query user B
        res_b = client.get("/api/candidate", headers=auth_headers(user_b))
        assert res_b.status_code == 200
        assert res_b.json()["name"] == "User B Candidate"
    finally:
        db.close()


# =========================================================================
# Test 12: Resumes belonging to user A cannot be viewed, updated, or deleted by user B (HTTP 403)
# =========================================================================
def test_cross_user_resume_access_rejected_403():
    db = SessionLocal()
    try:
        user_a = random.randint(100000, 499999)
        user_b = random.randint(500000, 999999)

        resume_a = ResumeDocument(
            user_id=user_a,
            title="User A Secret Resume",
            template_id="minimal_professional",
            latex_content=r"\documentclass{article}\begin{document}User A\end{document}",
            version=1
        )
        db.add(resume_a)
        db.commit()
        r_id = resume_a.id

        # User B attempts GET -> 403
        get_res = client.get(f"/api/resumes/{r_id}", headers=auth_headers(user_b))
        assert get_res.status_code == 403
        assert "Forbidden" in get_res.json()["detail"]

        # User B attempts PUT -> 403
        put_res = client.put(f"/api/resumes/{r_id}", json={"title": "Hacked Title"}, headers=auth_headers(user_b))
        assert put_res.status_code == 403

        # User B attempts DELETE -> 403
        del_res = client.delete(f"/api/resumes/{r_id}", headers=auth_headers(user_b))
        assert del_res.status_code == 403

        # User B attempts apply-optimization -> 403
        opt_res = client.post(
            f"/api/resumes/{r_id}/apply-optimization",
            json={"latex_content": r"\documentclass{article}\begin{document}Hacked\end{document}"},
            headers=auth_headers(user_b)
        )
        assert opt_res.status_code == 403
    finally:
        db.close()


# =========================================================================
# Test 13: Opportunities belonging to user A cannot be used for tailoring by user B (HTTP 403)
# =========================================================================
def test_cross_user_opportunity_access_rejected_403():
    db = SessionLocal()
    try:
        user_a = random.randint(100000, 499999)
        user_b = random.randint(500000, 999999)

        opp_a = Opportunity(
            user_id=user_a,
            title="Proprietary Role A",
            normalized_title="proprietary role a",
            company_name="Private Corp A",
            original_url=f"https://private.example.com/{uuid.uuid4()}",
            source_platform="direct"
        )
        cand_b = CandidateProfile(user_id=user_b, name="Candidate B")
        db.add_all([opp_a, cand_b])
        db.commit()

        # User B attempts tailoring against User A's private opportunity
        res = client.post(
            "/api/resumes/tailor",
            json={"opportunity_id": opp_a.id},
            headers=auth_headers(user_b)
        )
        assert res.status_code == 403
        assert "Forbidden" in res.json()["detail"]
    finally:
        db.close()


# =========================================================================
# Test 14: Failed tailoring or optimization does not increment versions or modify application links
# =========================================================================
def test_failed_operations_do_not_increment_version_or_modify_links():
    db = SessionLocal()
    try:
        user_id = random.randint(100000, 999999)
        valid_latex = r"\documentclass{article}\begin{document}Clean Resume v1\end{document}"
        resume = ResumeDocument(
            user_id=user_id,
            title="Stable Resume",
            template_id="minimal_professional",
            latex_content=valid_latex,
            version=1
        )
        db.add(resume)
        db.commit()
        r_id = resume.id

        # Submit broken LaTeX that cannot compile
        broken_latex = r"\documentclass{article}\begin{document} Broken Syntax \unclosed{environment "
        res = client.post(
            f"/api/resumes/{r_id}/apply-optimization",
            json={"latex_content": broken_latex},
            headers=auth_headers(user_id)
        )
        assert res.status_code == 400
        assert "LaTeX compilation failed" in res.json()["detail"]

        # Verify version did NOT increment and content was preserved
        db.refresh(resume)
        assert resume.version == 1
        assert resume.latex_content == valid_latex

        # Verify no version snapshot was created for version 2
        v2 = db.query(ResumeVersion).filter(
            ResumeVersion.resume_id == r_id,
            ResumeVersion.version_number == 2
        ).first()
        assert v2 is None
    finally:
        db.close()
