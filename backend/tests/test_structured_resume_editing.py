import os
import copy
import random
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models.candidate import CandidateProfile
from backend.app.models.resume import ResumeDocument
from backend.app.models.resume_version import ResumeVersion
from backend.app.models.opportunity import Opportunity
from backend.app.core.auth import create_access_token
from backend.app.schemas.structured_resume import (
    StructuredResumeContent,
    PersonalInfo,
    EducationEntry,
    SkillCategory,
    ProjectEntry,
    ExperienceEntry,
    CertificationEntry,
    AchievementEntry,
    PublicationEntry,
    AdditionalLink,
    BulletPoint,
    profile_to_structured_resume,
    generate_stable_id
)
from backend.app.services.latex_templates import (
    build_latex_template,
    list_available_templates
)
from backend.app.services.latex_compiler import compile_latex
from backend.app.services.ai.types import ModelResponse, ProviderType, TaskType, GroqProviderError

client = TestClient(app)


def auth_headers(user_id: int) -> dict:
    token = create_access_token(user_id=user_id)
    return {"Authorization": f"Bearer {token}"}


def sample_structured_content(name: str = "Alice Engineer") -> StructuredResumeContent:
    return StructuredResumeContent(
        personal_info=PersonalInfo(
            name=name,
            email=f"{name.lower().replace(' ', '')}@example.com",
            phone="+1 555-0199",
            location="San Francisco, CA",
            github_url="https://github.com/alice",
            linkedin_url="https://linkedin.com/in/alice",
            portfolio_url="https://alice.dev"
        ),
        summary="Experienced backend systems engineer specializing in distributed architectures and high-throughput pipelines.",
        education=[
            EducationEntry(
                id="edu_1",
                college="University of California, Berkeley",
                degree="B.S. Electrical Engineering & Computer Science",
                graduation_year=2024,
                cgpa=3.92,
                coursework=["Distributed Systems", "Operating Systems", "Algorithms"]
            )
        ],
        skills=[
            SkillCategory(category="Languages", skills=["Python", "Go", "C++", "SQL"]),
            SkillCategory(category="Frameworks & Libraries", skills=["FastAPI", "gRPC", "AsyncIO", "React"]),
            SkillCategory(category="Tools & Platforms", skills=["Docker", "Kubernetes", "PostgreSQL", "Redis", "Kafka"]),
            SkillCategory(category="Core Competencies", skills=["Distributed Systems", "Concurrency", "Database Optimization"])
        ],
        projects=[
            ProjectEntry(
                id="proj_1",
                title="Distributed Key-Value Store",
                tech_stack=["Go", "Raft", "gRPC", "LevelDB"],
                url="https://github.com/alice/kv-raft",
                description="Consensus-driven fault-tolerant distributed key-value storage engine.",
                bullets=[
                    BulletPoint(id="b_p1_1", text="Engineered Raft consensus module with leader election and log replication handling 50k ops/sec.", evidence_ref="projects[0]"),
                    BulletPoint(id="b_p1_2", text="Optimized disk persistence with WAL logging and memory-mapped LevelDB tables.", evidence_ref="projects[0]")
                ]
            )
        ],
        experience=[
            ExperienceEntry(
                id="exp_1",
                title="Software Engineer Intern",
                company="CloudScale Systems",
                duration="May 2023 - Aug 2023",
                location="San Francisco, CA",
                description="Contributed to core microservices infrastructure.",
                bullets=[
                    BulletPoint(id="b_e1_1", text="Architected async message dispatch worker reducing queue latency by 42%.", evidence_ref="experience[0]"),
                    BulletPoint(id="b_e1_2", text="Containerized telemetry exporter and integrated Prometheus alerts across 12 services.", evidence_ref="experience[0]")
                ]
            )
        ],
        certifications=[
            CertificationEntry(
                id="cert_1",
                name="AWS Certified Solutions Architect - Associate",
                issuer="Amazon Web Services",
                year=2024
            )
        ],
        achievements=[
            AchievementEntry(
                id="ach_1",
                title="1st Place - CalHacks Global Hackathon",
                organization="CalHacks",
                year=2023,
                description="Built peer-to-peer verifiable AI model validation network among 2,000+ competitors."
            )
        ],
        publications=[
            PublicationEntry(
                id="pub_1",
                title="Scalable Byzantine Fault Tolerant Consensus for Edge Computing",
                venue="IEEE Distributed Systems Workshop",
                year=2024,
                url="https://doi.org/10.1109/example",
                authors=["Alice Engineer", "Dr. Bob Vance"]
            )
        ],
        additional_links=[
            AdditionalLink(label="Technical Blog", url="https://alice.dev/blog")
        ]
    )


def create_test_candidate_and_resume(user_id: int, template_id: str = "minimal_professional") -> ResumeDocument:
    db = SessionLocal()
    try:
        # Candidate Profile
        cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
        if not cand:
            cand = CandidateProfile(
                user_id=user_id,
                name=f"User {user_id}",
                email=f"user{user_id}@example.com",
                skills=[{"name": "Python", "category": "Languages"}, {"name": "Go", "category": "Languages"}, {"name": "Docker", "category": "Tools"}],
                projects=[{"id": "p_cand", "title": "Lead Automation", "tech_stack": ["Python", "FastAPI"], "description": "Automated workflow system."}],
                experience=[{"id": "e_cand", "title": "Developer", "company": "Tech Corp", "duration": "2023", "description": "Backend services."}],
                certifications=[{"id": "c_cand", "name": "Cloud Practitioner", "issuer": "AWS", "year": "2023"}],
                achievements=[{"id": "a_cand", "title": "Dean's Honor Roll", "organization": "University", "year": "2023"}]
            )
            db.add(cand)
            db.commit()

        structured = sample_structured_content(f"User {user_id}")
        latex = build_latex_template(structured.model_dump(), template_id=template_id)
        
        resume = ResumeDocument(
            user_id=user_id,
            title=f"Test Resume {user_id}",
            template_id=template_id,
            latex_content=latex,
            structured_content=structured.model_dump(),
            version=1,
            is_master=False
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)

        v1 = ResumeVersion(
            resume_id=resume.id,
            version_number=1,
            title=resume.title,
            template_id=resume.template_id,
            latex_content=resume.latex_content,
            structured_content=resume.structured_content,
            change_summary="Initial test creation"
        )
        db.add(v1)
        db.commit()
        db.refresh(resume)

        from types import SimpleNamespace
        return SimpleNamespace(
            id=resume.id,
            version=resume.version,
            user_id=resume.user_id,
            title=resume.title,
            template_id=resume.template_id,
            latex_content=resume.latex_content,
            structured_content=copy.deepcopy(resume.structured_content)
        )
    finally:
        db.close()


# =========================================================================
# Test 1: Structured resume content serialization
# =========================================================================
def test_structured_resume_content_serialization():
    """Structured resume content models cleanly serialize to and deserialize from JSON."""
    original = sample_structured_content("Serialization Tester")
    data_dict = original.model_dump()

    # Verify JSON structure
    assert "personal_info" in data_dict
    assert data_dict["personal_info"]["name"] == "Serialization Tester"
    assert len(data_dict["projects"]) == 1
    assert len(data_dict["projects"][0]["bullets"]) == 2
    assert data_dict["projects"][0]["bullets"][0]["id"] == "b_p1_1"

    # Reconstitute from dict
    reconstituted = StructuredResumeContent(**data_dict)
    assert reconstituted.personal_info.name == original.personal_info.name
    assert reconstituted.summary == original.summary
    assert len(reconstituted.education) == len(original.education)
    assert reconstituted.education[0].college == original.education[0].college
    assert len(reconstituted.projects[0].bullets) == 2
    assert reconstituted.projects[0].bullets[1].text == original.projects[0].bullets[1].text
    assert reconstituted.certifications[0].name == original.certifications[0].name
    assert reconstituted.achievements[0].title == original.achievements[0].title
    assert reconstituted.publications[0].title == original.publications[0].title


# =========================================================================
# Test 2: Partial section updates
# =========================================================================
def test_partial_section_updates():
    """Updating only projects strictly preserves education, skills, certifications, and achievements."""
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)
    resume = create_test_candidate_and_resume(user_id)

    # Initial state
    get_res = client.get(f"/api/resumes/{resume.id}/sections", headers=headers)
    assert get_res.status_code == 200
    initial_content = get_res.json()["structured_content"]
    assert len(initial_content["certifications"]) >= 1
    assert len(initial_content["achievements"]) >= 1

    # Update ONLY projects
    new_project = {
        "id": "proj_new_1",
        "title": "Quantum Simulation Engine",
        "tech_stack": ["Python", "NumPy", "Qiskit"],
        "url": "https://github.com/alice/quantum",
        "bullets": [
            {"id": "b_q1", "text": "Simulated Shor algorithm for prime factorization on noisy quantum gates."}
        ]
    }
    update_payload = {
        "projects": [new_project],
        "change_summary": "Updated projects section only"
    }

    put_res = client.put(f"/api/resumes/{resume.id}/sections", json=update_payload, headers=headers)
    assert put_res.status_code == 200
    data = put_res.json()
    assert data["status"] == "success"
    assert data["version"] == 2

    updated_content = data["structured_content"]
    # Projects changed
    assert len(updated_content["projects"]) == 1
    assert updated_content["projects"][0]["title"] == "Quantum Simulation Engine"
    assert updated_content["projects"][0]["bullets"][0]["text"].startswith("Simulated Shor algorithm")

    # Untouched sections preserved
    assert updated_content["certifications"] == initial_content["certifications"]
    assert updated_content["achievements"] == initial_content["achievements"]
    assert updated_content["education"] == initial_content["education"]
    assert updated_content["skills"] == initial_content["skills"]
    assert updated_content["summary"] == initial_content["summary"]


# =========================================================================
# Test 3: Preservation of Certifications and Honors
# =========================================================================
def test_preservation_of_certifications_and_honors():
    """Editing work experience strictly preserves certifications and honors in both JSON and LaTeX."""
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)
    resume = create_test_candidate_and_resume(user_id)

    # Update work experience
    new_experience = [{
        "id": "exp_updated",
        "title": "Senior Distributed Systems Engineer",
        "company": "NextGen Cloud Labs",
        "duration": "2024 - Present",
        "location": "Remote",
        "bullets": [
            {"id": "b_exp_new_1", "text": "Spearheaded fault-tolerant Raft replication layer across 8 geographic regions."}
        ]
    }]

    res = client.put(f"/api/resumes/{resume.id}/sections", json={"experience": new_experience}, headers=headers)
    assert res.status_code == 200
    updated_resume = res.json()["resume"]
    updated_structured = res.json()["structured_content"]

    # Verify certifications & achievements preserved in structured content
    assert len(updated_structured["certifications"]) == 1
    assert updated_structured["certifications"][0]["name"] == "AWS Certified Solutions Architect - Associate"
    assert len(updated_structured["achievements"]) == 1
    assert updated_structured["achievements"][0]["title"] == "1st Place - CalHacks Global Hackathon"

    # Verify certifications & achievements preserved in compiled LaTeX
    latex = updated_resume["latex_content"]
    assert "AWS Certified Solutions Architect" in latex
    assert "CalHacks Global Hackathon" in latex
    assert "Senior Distributed Systems Engineer" in latex


# =========================================================================
# Test 4: Template preservation across all six templates
# =========================================================================
def test_template_preservation_across_all_six_templates():
    """All 6 ATS templates render structured multi-bullet content and compile with zero errors."""
    templates = [
        "minimal_professional",
        "modern_technical",
        "software_engineering",
        "aiml_research",
        "fresher_student",
        "experience_focused"
    ]
    structured = sample_structured_content("Template Preservation Test")

    for tmpl in templates:
        latex = build_latex_template(structured.model_dump(), template_id=tmpl)
        assert "\\begin{document}" in latex
        assert "Template Preservation Test" in latex
        assert "Distributed Key-Value Store" in latex

        # Verify multi-bullet itemize list is rendered
        assert "\\item Engineered Raft consensus" in latex
        assert "\\item Optimized disk persistence" in latex

        # Verify strict LaTeX compilation
        ok, pdf_path, compiler = compile_latex(latex, f"test_tmpl_compile_{tmpl}", strict=True)
        assert ok is True, f"Template {tmpl} failed strict compilation: {pdf_path}"
        assert os.path.exists(pdf_path)


# =========================================================================
# Test 5: Stable bullet ID updates
# =========================================================================
def test_stable_bullet_id_updates():
    """Updating bullet text in place preserves its stable identifier."""
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)
    resume = create_test_candidate_and_resume(user_id)

    # Initial bullets have IDs "b_p1_1" and "b_p1_2"
    update_payload = {
        "projects": [{
            "id": "proj_1",
            "title": "Distributed Key-Value Store",
            "tech_stack": ["Go", "Raft"],
            "bullets": [
                {"id": "b_p1_1", "text": "Refactored Raft state machine yielding 3x throughput increase under partition."},
                {"id": "b_p1_2", "text": "Optimized disk persistence with WAL logging and memory-mapped LevelDB tables."}
            ]
        }]
    }

    res = client.put(f"/api/resumes/{resume.id}/sections", json=update_payload, headers=headers)
    assert res.status_code == 200
    projs = res.json()["structured_content"]["projects"]
    assert len(projs[0]["bullets"]) == 2
    # ID is preserved, text is updated
    assert projs[0]["bullets"][0]["id"] == "b_p1_1"
    assert "Refactored Raft state machine" in projs[0]["bullets"][0]["text"]
    assert projs[0]["bullets"][1]["id"] == "b_p1_2"


# =========================================================================
# Test 6: Bullet reordering and deletion
# =========================================================================
def test_bullet_reordering_and_deletion():
    """Reordering bullets updates output order; omitting a bullet deletes it."""
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)
    resume = create_test_candidate_and_resume(user_id)

    # Swap b_p1_2 to position 0, omit b_p1_1 (deleting it), and add a new bullet
    update_payload = {
        "projects": [{
            "id": "proj_1",
            "title": "Distributed Key-Value Store",
            "tech_stack": ["Go", "Raft"],
            "bullets": [
                {"id": "b_p1_2", "text": "Optimized disk persistence with WAL logging."},
                {"text": "Newly added third bullet for benchmarking."}
            ]
        }]
    }

    res = client.put(f"/api/resumes/{resume.id}/sections", json=update_payload, headers=headers)
    assert res.status_code == 200
    bullets = res.json()["structured_content"]["projects"][0]["bullets"]
    assert len(bullets) == 2
    # First bullet is now b_p1_2
    assert bullets[0]["id"] == "b_p1_2"
    # b_p1_1 is deleted
    assert not any(b["id"] == "b_p1_1" for b in bullets)
    # New bullet received an auto-generated stable ID
    assert bullets[1]["id"].startswith("bullet_")
    assert "Newly added third bullet" in bullets[1]["text"]

    # Check LaTeX reflects new order
    latex = res.json()["resume"]["latex_content"]
    assert "Optimized disk persistence" in latex
    assert "Newly added third bullet" in latex
    assert "Engineered Raft consensus module" not in latex


# =========================================================================
# Test 7: Unknown bullet ID rejection
# =========================================================================
def test_unknown_bullet_id_rejection():
    """Attempting an in-place edit with an unrecognized bullet ID returns HTTP 422."""
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)
    resume = create_test_candidate_and_resume(user_id)

    update_payload = {
        "projects": [{
            "id": "proj_1",
            "title": "Distributed Key-Value Store",
            "bullets": [
                {"id": "bogus_unrecognized_bullet_id_999", "text": "Trying to update ghost bullet."}
            ]
        }]
    }

    res = client.put(f"/api/resumes/{resume.id}/sections", json=update_payload, headers=headers)
    assert res.status_code == 422
    assert "Unknown bullet ID 'bogus_unrecognized_bullet_id_999'" in res.json()["detail"]


# =========================================================================
# Test 8: Individual section regeneration
# =========================================================================
def test_individual_section_regeneration():
    """POST /api/resumes/{id}/sections/regenerate returns proposal for individual sections."""
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)
    resume = create_test_candidate_and_resume(user_id)

    mock_resp = ModelResponse(
        provider=ProviderType.GROQ,
        model="llama-3.3-70b-versatile",
        content="{}",
        parsed_json={
            "summary": "High-performance systems software engineer with deep expertise in Raft consensus and Linux kernel optimization.",
            "rationale": "Emphasizes candidate demonstrated systems experience."
        },
        latency_ms=120,
        total_tokens=150
    )

    with patch("backend.app.services.ai.service.ai_service.router.execute", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = mock_resp

        req_payload = {
            "section": "summary",
            "user_instructions": "Focus heavily on Linux systems and consensus"
        }
        res = client.post(f"/api/resumes/{resume.id}/sections/regenerate", json=req_payload, headers=headers)
        assert res.status_code == 200
        proposal = res.json()
        assert proposal["section"] == "summary"
        assert "High-performance systems software engineer" in proposal["proposed_content"]
        assert "Linux systems" in mock_exec.call_args[1]["prompt"]


# =========================================================================
# Test 9: Unsupported AI claims rejection
# =========================================================================
def test_unsupported_ai_claims_rejection():
    """Hallucinated skills suggested by AI during section regeneration are rejected by safety filter."""
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)
    resume = create_test_candidate_and_resume(user_id)

    # Groq hallucinates unverified skills "Quantum Assembly" and "COBOL"
    mock_resp = ModelResponse(
        provider=ProviderType.GROQ,
        model="llama-3.3-70b-versatile",
        content="{}",
        parsed_json={
            "categorized_skills": [
                {"category": "Languages", "skills": ["Python", "Quantum Assembly", "Go", "COBOL"]},
                {"category": "Tools", "skills": ["Docker"]}
            ],
            "rationale": "Grouped verified skills."
        },
        latency_ms=110,
        total_tokens=100
    )

    with patch("backend.app.services.ai.service.ai_service.router.execute", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = mock_resp

        res = client.post(
            f"/api/resumes/{resume.id}/sections/regenerate",
            json={"section": "skills"},
            headers=headers
        )
        assert res.status_code == 200
        proposal = res.json()
        # Verify hallucinated skills were caught and dropped
        dropped = proposal["unsupported_claims_rejected"]
        assert "Quantum Assembly" in dropped
        assert "COBOL" in dropped

        # Verify proposed skills only contain verified skills
        all_proposed_skills = [
            s
            for cat in proposal["proposed_content"]
            for s in cat["skills"]
        ]
        assert "Quantum Assembly" not in all_proposed_skills
        assert "COBOL" not in all_proposed_skills
        assert "Python" in all_proposed_skills


# =========================================================================
# Test 10: Groq failure preserving original content
# =========================================================================
def test_groq_failure_preserving_original_content():
    """When Groq fails or is unavailable, regeneration returns HTTP 503 and preserves original state."""
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)
    resume = create_test_candidate_and_resume(user_id)

    db = SessionLocal()
    try:
        orig_resume = db.query(ResumeDocument).filter(ResumeDocument.id == resume.id).first()
        orig_version = orig_resume.version
        orig_content = copy.deepcopy(orig_resume.structured_content)

        # Simulate Groq provider failure
        with patch("backend.app.services.ai.service.ai_service.router.execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = GroqProviderError("Groq 429 Rate limit exceeded. Try again in 20s.", retryable=True)

            res = client.post(
                f"/api/resumes/{resume.id}/sections/regenerate",
                json={"section": "summary"},
                headers=headers
            )
            assert res.status_code == 503
            assert "AI Section Regeneration unavailable" in res.json()["detail"]
            assert "Original section preserved" in res.json()["detail"]

        # Check database: state untouched
        db.refresh(orig_resume)
        assert orig_resume.version == orig_version
        assert orig_resume.structured_content == orig_content
    finally:
        db.close()


# =========================================================================
# Test 11: Regeneration proposals not modifying saved resumes
# =========================================================================
def test_regeneration_proposals_not_modifying_saved_resumes():
    """Generating a section proposal leaves the resume in database completely unmodified."""
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)
    resume = create_test_candidate_and_resume(user_id)

    mock_resp = ModelResponse(
        provider=ProviderType.GROQ,
        model="llama-3.3-70b-versatile",
        content="{}",
        parsed_json={
            "summary": "Proposed revolutionary new summary.",
            "rationale": "High impact proposal."
        },
        latency_ms=100,
        total_tokens=80
    )

    with patch("backend.app.services.ai.service.ai_service.router.execute", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = mock_resp

        res = client.post(
            f"/api/resumes/{resume.id}/sections/regenerate",
            json={"section": "summary"},
            headers=headers
        )
        assert res.status_code == 200

    db = SessionLocal()
    try:
        r = db.query(ResumeDocument).filter(ResumeDocument.id == resume.id).first()
        # Stored resume summary must remain original
        assert r.version == 1
        assert "revolutionary" not in (r.structured_content.get("summary") or "")
    finally:
        db.close()


# =========================================================================
# Test 12: Compilation failure rollback
# =========================================================================
def test_compilation_failure_rollback():
    """If generated LaTeX fails compilation, changes are rolled back and version is not incremented."""
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)
    resume = create_test_candidate_and_resume(user_id)

    # Patch compile_latex to simulate tectonic syntax error
    with patch("backend.app.api.resumes.compile_latex") as mock_compile:
        mock_compile.return_value = (False, "Fatal LaTeX error: Missing $ inserted at line 42", "tectonic")

        update_payload = {
            "summary": "This update should be aborted because compilation failed.",
            "change_summary": "Attempting doomed update"
        }
        res = client.put(f"/api/resumes/{resume.id}/sections", json=update_payload, headers=headers)
        assert res.status_code == 400
        assert "original resume was preserved unchanged" in res.json()["detail"].lower()

    # Verify rollback in database
    db = SessionLocal()
    try:
        r = db.query(ResumeDocument).filter(ResumeDocument.id == resume.id).first()
        assert r.version == 1
        assert "doomed" not in str(r.structured_content)
    finally:
        db.close()


# =========================================================================
# Test 13: Successful version snapshot creation
# =========================================================================
def test_successful_version_snapshot_creation():
    """Applying a valid section update creates a new ResumeVersion snapshot with structured content."""
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)
    resume = create_test_candidate_and_resume(user_id)

    update_payload = {
        "summary": "Staff Backend Engineer specializing in cloud-native resilient storage.",
        "change_summary": "Promoted to Staff summary"
    }

    res = client.put(f"/api/resumes/{resume.id}/sections", json=update_payload, headers=headers)
    assert res.status_code == 200
    assert res.json()["version"] == 2

    db = SessionLocal()
    try:
        v2 = db.query(ResumeVersion).filter(
            ResumeVersion.resume_id == resume.id,
            ResumeVersion.version_number == 2
        ).first()
        assert v2 is not None
        assert v2.change_summary == "Promoted to Staff summary"
        assert v2.structured_content["summary"] == "Staff Backend Engineer specializing in cloud-native resilient storage."
        assert "Staff Backend Engineer" in v2.latex_content
    finally:
        db.close()


# =========================================================================
# Test 14: Concurrent update conflict handling
# =========================================================================
def test_concurrent_update_conflict_handling():
    """Optimistic concurrency check rejects updates with outdated expected_version (HTTP 409)."""
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)
    resume = create_test_candidate_and_resume(user_id)

    # First update: increments version from 1 to 2
    client.put(
        f"/api/resumes/{resume.id}/sections",
        json={"summary": "First valid update.", "expected_version": 1},
        headers=headers
    )

    # Concurrent second update sends stale expected_version=1 while resume is at version 2
    res_conflict = client.put(
        f"/api/resumes/{resume.id}/sections",
        json={"summary": "Stale conflicting update.", "expected_version": 1},
        headers=headers
    )
    assert res_conflict.status_code == 409
    assert "Current resume version is 2, but expected 1" in res_conflict.json()["detail"]


# =========================================================================
# Test 15: Cross-user section access rejection
# =========================================================================
def test_cross_user_section_access_rejected():
    """Users cannot inspect or update sections of resumes belonging to other users (HTTP 403)."""
    owner_id = random.randint(100000, 499999)
    attacker_id = random.randint(500000, 999999)

    resume_owner = create_test_candidate_and_resume(owner_id)
    attacker_headers = auth_headers(attacker_id)

    # GET sections
    res_get = client.get(f"/api/resumes/{resume_owner.id}/sections", headers=attacker_headers)
    assert res_get.status_code == 403

    # PUT sections
    res_put = client.put(
        f"/api/resumes/{resume_owner.id}/sections",
        json={"summary": "Malicious takeover attempt"},
        headers=attacker_headers
    )
    assert res_put.status_code == 403

    # POST sections regenerate
    res_regen = client.post(
        f"/api/resumes/{resume_owner.id}/sections/regenerate",
        json={"section": "summary"},
        headers=attacker_headers
    )
    assert res_regen.status_code == 403


# =========================================================================
# Test 16: Empty sections compiling correctly
# =========================================================================
def test_empty_sections_compiling_correctly():
    """Empty sections are omitted gracefully and compile cleanly without syntax errors."""
    empty_content = StructuredResumeContent(
        personal_info=PersonalInfo(
            name="Empty Section Candidate",
            email="empty@example.com"
        ),
        summary=None,
        education=[],
        skills=[],
        projects=[],
        experience=[],
        certifications=[],
        achievements=[],
        publications=[],
        additional_links=[]
    )

    for tmpl in ["minimal_professional", "modern_technical", "software_engineering"]:
        latex = build_latex_template(empty_content.model_dump(), template_id=tmpl)
        # Should not contain empty section headings
        assert "\\section*{Technical Projects}" not in latex
        assert "\\section*{Experience}" not in latex
        assert "\\section*{Certifications}" not in latex

        # Compiles successfully
        ok, pdf_path, compiler = compile_latex(latex, f"test_empty_{tmpl}", strict=True)
        assert ok is True, f"Failed compilation for empty resume on {tmpl}: {pdf_path}"


# =========================================================================
# Test 17: Existing resume records remaining compatible
# =========================================================================
def test_existing_resume_records_remaining_compatible():
    """Legacy resume documents where structured_content is NULL load and update seamlessly."""
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)

    db = SessionLocal()
    try:
        # Create candidate profile
        cand = CandidateProfile(
            user_id=user_id,
            name=f"Legacy User {user_id}",
            email=f"legacy{user_id}@example.com",
            skills=[{"name": "Python", "category": "Languages"}, {"name": "SQL", "category": "Languages"}],
            projects=[{"id": "p1", "title": "Legacy Project", "tech_stack": ["Python"], "description": "Existing project."}],
            experience=[],
            certifications=[],
            achievements=[]
        )
        db.add(cand)
        db.commit()

        # Create legacy resume with structured_content=None
        legacy_resume = ResumeDocument(
            user_id=user_id,
            title="Legacy Unmigrated Resume",
            template_id="minimal_professional",
            latex_content="% Legacy LaTeX content",
            structured_content=None,
            version=1,
            is_master=True
        )
        db.add(legacy_resume)
        db.commit()
        db.refresh(legacy_resume)
        res_id = legacy_resume.id
    finally:
        db.close()

    # GET /sections automatically migrates and initializes structured content
    get_res = client.get(f"/api/resumes/{res_id}/sections", headers=headers)
    assert get_res.status_code == 200
    sec_data = get_res.json()["structured_content"]
    assert sec_data["personal_info"]["name"] == f"Legacy User {user_id}"
    assert len(sec_data["projects"]) == 1

    # PUT /sections works immediately on migrated record
    put_res = client.put(
        f"/api/resumes/{res_id}/sections",
        json={"summary": "Successfully edited legacy resume via structured API."},
        headers=headers
    )
    assert put_res.status_code == 200
    assert put_res.json()["version"] == 2
    assert put_res.json()["structured_content"]["summary"] == "Successfully edited legacy resume via structured API."
