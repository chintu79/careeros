import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import get_db, SessionLocal
from backend.app.models.resume import ResumeDocument
from backend.app.models.resume_version import ResumeVersion
from backend.app.models.candidate import CandidateProfile
from backend.app.models.opportunity import Opportunity
from backend.app.services.latex_templates import list_available_templates, build_latex_template

client = TestClient(app)

def test_available_templates():
    templates = list_available_templates()
    assert len(templates) == 6
    template_ids = [t["id"] for t in templates]
    assert "minimal_professional" in template_ids
    assert "modern_technical" in template_ids
    assert "software_engineering" in template_ids
    assert "aiml_research" in template_ids
    assert "fresher_student" in template_ids
    assert "experience_focused" in template_ids

    response = client.get("/api/resumes/templates")
    assert response.status_code == 200
    res_json = response.json()
    assert len(res_json) == 6

def test_template_generation_and_compilation():
    sample_profile = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+91 9999988888",
        "location": "Bengaluru, India",
        "degree": "B.Tech Computer Science",
        "college": "IIT Bombay",
        "graduation_year": 2026,
        "cgpa": 9.2,
        "skills": [{"name": "Python", "category": "Languages"}, {"name": "PyTorch", "category": "Frameworks"}],
        "experience": [{"title": "ML Intern", "company": "AI Labs", "duration": "Summer 2025", "description": "Trained transformer models."}],
        "projects": [{"title": "Vision Transformer", "tech_stack": ["Python", "PyTorch"], "description": "Trained vision models with 94% precision."}]
    }
    for t in list_available_templates():
        tex = build_latex_template(sample_profile, t["id"])
        assert "\\begin{document}" in tex
        assert "Jane Doe" in tex
        assert "\\end{document}" in tex

def test_master_resume_initialization_and_protection():
    # 1. Fetch or create master resume
    res = client.get("/api/resumes/master")
    assert res.status_code == 200
    master_data = res.json()
    assert master_data["is_master"] is True
    master_id = master_data["id"]

    # 2. Verify deleting master is strictly blocked
    del_res = client.delete(f"/api/resumes/{master_id}")
    assert del_res.status_code == 400
    assert "Master Candidate Resume is protected" in del_res.json()["detail"]

def test_resume_lifecycle_crud():
    # 1. Create a custom resume
    create_res = client.post("/api/resumes", json={
        "title": "Backend Engineering Resume",
        "template_id": "software_engineering"
    })
    assert create_res.status_code == 200
    created = create_res.json()
    resume_id = created["id"]
    assert created["title"] == "Backend Engineering Resume"
    assert created["template_id"] == "software_engineering"
    assert created["version"] == 1

    # 2. Check version history has v1 snapshot
    v_res = client.get(f"/api/resumes/{resume_id}/versions")
    assert v_res.status_code == 200
    versions = v_res.json()
    assert len(versions) >= 1
    assert versions[0]["version_number"] == 1

    # 3. Rename resume
    rename_res = client.post(f"/api/resumes/{resume_id}/rename", json={"title": "Systems Software Resume"})
    assert rename_res.status_code == 200
    assert rename_res.json()["title"] == "Systems Software Resume"

    # 4. Duplicate resume
    dup_res = client.post(f"/api/resumes/{resume_id}/duplicate")
    assert dup_res.status_code == 200
    dup_data = dup_res.json()
    assert dup_data["title"] == "Copy of Systems Software Resume"
    assert dup_data["id"] != resume_id
    assert dup_data["is_master"] is False

    # 5. Check manual version checkpoint
    snap_res = client.post(f"/api/resumes/{resume_id}/versions", json={"change_summary": "Added distributed cache section"})
    assert snap_res.status_code == 200
    assert snap_res.json()["version"] == 2

    # 6. Delete duplicated resume
    del_res = client.delete(f"/api/resumes/{dup_data['id']}")
    assert del_res.status_code == 200
    assert del_res.json()["message"] == "Resume deleted successfully"

    # 7. Clean up original created test resume
    client.delete(f"/api/resumes/{resume_id}")

def test_quality_check_audit():
    # Fetch master resume
    master = client.get("/api/resumes/master").json()
    resume_id = master["id"]

    audit_res = client.post(f"/api/resumes/{resume_id}/quality-check")
    assert audit_res.status_code == 200
    report = audit_res.json()
    assert "ats_score" in report
    assert "grade" in report
    assert "checks" in report
    assert len(report["checks"]) == 6

    check_categories = [c["category"] for c in report["checks"]]
    assert "ats_readability" in check_categories
    assert "formatting_validation" in check_categories
    assert "grammar_and_verbs" in check_categories
    assert "keyword_coverage" in check_categories
    assert "section_completeness" in check_categories
    assert "date_consistency" in check_categories
    assert report["ats_score"] >= 70

def test_ai_optimization_and_approval_flow():
    # Get master resume
    master = client.get("/api/resumes/master").json()
    resume_id = master["id"]

    # Get an opportunity from DB
    db = SessionLocal()
    opp = db.query(Opportunity).first()
    opp_id = opp.id if opp else 1
    db.close()

    # 1. Request AI Optimization proposal
    with patch("backend.app.api.resumes.ai_service.tailor_resume", new_callable=AsyncMock) as mock_tailor:
        mock_tailor.return_value = {
            "success": True,
            "provider": "groq",
            "model": "llama-3.3-70b-versatile",
            "latency_ms": 120.0,
            "tokens": 200,
            "data": {
                "matched_skills": ["Python"],
                "missing_skills": ["Kubernetes"],
                "bullet_refinements": [],
                "suggested_section_order": ["Experience", "Projects", "Skills"],
                "rationale": "Matched verified skills against requirements."
            }
        }
        opt_res = client.post(f"/api/resumes/{resume_id}/optimize", json={"opportunity_id": opp_id})
        assert opt_res.status_code == 200
        proposal = opt_res.json()
        assert "verified_matching_skills" in proposal
        assert "missing_job_keywords" in proposal
        assert "suggested_section_order" in proposal
        assert proposal["strict_zero_fabrication_confirmed"] is True

    # 2. Apply user-approved optimization
    apply_res = client.post(f"/api/resumes/{resume_id}/apply-optimization", json={
        "latex_content": master["latex_content"] + "\n% Optimized for " + opp.title if opp else master["latex_content"],
        "change_summary": "Applied AI verified recommendations"
    })
    assert apply_res.status_code == 200
    updated = apply_res.json()
    assert updated["version"] > master["version"]

def test_compare_resumes_diff():
    master = client.get("/api/resumes/master").json()
    resume_id = master["id"]

    diff_res = client.post(f"/api/resumes/{resume_id}/compare", json={"compare_with_master": True})
    assert diff_res.status_code == 200
    diff_data = diff_res.json()
    assert "diff_lines" in diff_data
    assert "section_changes" in diff_data
    assert "added_lines" in diff_data
    assert "removed_lines" in diff_data

def test_restore_version_snapshot():
    # Create custom resume
    create_res = client.post("/api/resumes", json={
        "title": "Version Restore Test Resume",
        "template_id": "minimal_professional"
    })
    res_id = create_res.json()["id"]

    # Get versions
    v_res = client.get(f"/api/resumes/{res_id}/versions")
    v1_id = v_res.json()[0]["id"]

    # Update resume with new text
    client.put(f"/api/resumes/{res_id}", json={
        "latex_content": "% Modified content\n\\documentclass{article}\\begin{document}Updated\\end{document}",
        "change_summary": "Made temporary changes"
    })

    # Restore v1
    restore_res = client.post(f"/api/resumes/{res_id}/versions/{v1_id}/restore")
    assert restore_res.status_code == 200
    restored = restore_res.json()
    assert restored["version"] >= 3
    # Check that versions now includes the restored audit record
    v_after = client.get(f"/api/resumes/{res_id}/versions").json()
    assert any("Restored from version snapshot" in v["change_summary"] for v in v_after)

    # Clean up
    client.delete(f"/api/resumes/{res_id}")
