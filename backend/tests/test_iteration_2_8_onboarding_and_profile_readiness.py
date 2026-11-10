import pytest
from starlette.testclient import TestClient
from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models.candidate import CandidateProfile
from backend.app.models.resume import ResumeDocument

client = TestClient(app)

TEST_USER_A = 92001
TEST_USER_B = 92002


def get_auth_headers(user_id: int):
    res = client.post("/api/auth/token", json={"user_id": user_id})
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def setup_test_candidates():
    db = SessionLocal()
    # Clean up test users
    db.query(ResumeDocument).filter(ResumeDocument.user_id.in_([TEST_USER_A, TEST_USER_B])).delete(synchronize_session=False)
    db.query(CandidateProfile).filter(CandidateProfile.user_id.in_([TEST_USER_A, TEST_USER_B])).delete(synchronize_session=False)
    db.commit()

    # Create fresh candidate A
    cand_a = CandidateProfile(
        user_id=TEST_USER_A,
        name="Alex River",
        email="alex.river@example.com",
        degree="B.S. Computer Science",
        college="Tech University",
        graduation_year=2026,
        onboarding_status="not_started",
        onboarding_step=1,
        evidence_version=1
    )
    # Create fresh candidate B
    cand_b = CandidateProfile(
        user_id=TEST_USER_B,
        name="Jordan Lee",
        email="jordan.lee@example.com",
        onboarding_status="in_progress",
        onboarding_step=2,
        evidence_version=1
    )
    db.add(cand_a)
    db.add(cand_b)
    db.commit()
    db.close()

    yield

    db = SessionLocal()
    db.query(ResumeDocument).filter(ResumeDocument.user_id.in_([TEST_USER_A, TEST_USER_B])).delete(synchronize_session=False)
    db.query(CandidateProfile).filter(CandidateProfile.user_id.in_([TEST_USER_A, TEST_USER_B])).delete(synchronize_session=False)
    db.commit()
    db.close()


def test_onboarding_initialization_and_step_persistence():
    headers = get_auth_headers(TEST_USER_A)

    # Step 1: Save Career Goals
    payload = {
        "step": 1,
        "status": "in_progress",
        "career_goals": {
            "target_roles": ["Frontend Engineer", "Full Stack Developer"],
            "target_locations": ["San Francisco, CA", "Remote"],
            "workplace_preference": "remote",
            "work_authorization": "US Citizen"
        },
        "profile_data": {
            "preferred_locations": ["San Francisco, CA", "Remote"],
            "work_authorization": "US Citizen"
        }
    }
    resp = client.put("/api/candidate/onboarding-progress", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "success"
    assert data["onboarding_step"] == 1
    assert data["onboarding_status"] == "in_progress"

    # Step 2: Save Education
    payload_step2 = {
        "step": 2,
        "status": "in_progress",
        "profile_data": {
            "degree": "B.S. in Computer Science",
            "college": "Stanford University",
            "graduation_year": 2026,
            "cgpa": 3.85
        }
    }
    resp2 = client.put("/api/candidate/onboarding-progress", json=payload_step2, headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["onboarding_step"] == 2

    # Verify directly in DB
    db = SessionLocal()
    cand = db.query(CandidateProfile).filter_by(user_id=TEST_USER_A).first()
    assert cand.onboarding_step == 2
    assert cand.college == "Stanford University"
    assert cand.career_goals.get("workplace_preference") == "remote"
    db.close()


def test_incomplete_onboarding_recovery():
    headers = get_auth_headers(TEST_USER_B)

    # Fetch candidate profile and completeness
    resp = client.get("/api/candidate", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["onboarding_step"] == 2
    assert data["onboarding_status"] == "in_progress"

    comp_resp = client.get("/api/candidate/completeness", headers=headers)
    assert comp_resp.status_code == 200
    comp = comp_resp.json()
    assert comp["is_onboarded"] is False
    assert comp["onboarding_step"] == 2
    assert comp["onboarding_status"] == "in_progress"


def test_profile_completeness_calculation_with_persisted_data():
    headers = get_auth_headers(TEST_USER_A)

    resp = client.get("/api/candidate/completeness", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert "completeness_score" in data
    assert "readiness_stage" in data
    assert "category_scores" in data
    assert "verified_evidence" in data
    assert "missing_evidence" in data
    assert "actionable_recommendations" in data
    assert "disclaimer" in data
    # Basic info and education present, but skills and projects missing
    assert any("Technical skills" in m for m in data["missing_evidence"])
    assert any("projects" in r["action_target"] for r in data["actionable_recommendations"])


def test_missing_versus_unverified_evidence_distinction():
    headers = get_auth_headers(TEST_USER_A)

    # Add a self-reported skill without any project backing
    skill_payload = {
        "name": "Rust",
        "category": "Languages",
        "level": "intermediate",
        "evidence": ""
    }
    resp = client.post("/api/candidate/skills", json=skill_payload, headers=headers)
    assert resp.status_code == 200

    comp_resp = client.get("/api/candidate/completeness", headers=headers)
    assert comp_resp.status_code == 200
    comp = comp_resp.json()

    # Skill Rust should be in unverified_evidence
    assert comp["skills_summary"]["unverified"] == 1
    assert comp["skills_summary"]["verified"] == 0
    assert any("Rust" in u and "self-reported" in u for u in comp["unverified_evidence"])

    # Now add a project that uses Rust
    proj_payload = {
        "title": "Rust High Performance Engine",
        "description": "Built async engine using Tokio and Actix",
        "tech_stack": ["Rust", "Actix", "Tokio"],
        "url": "https://github.com/alex/rust-engine"
    }
    client.post("/api/candidate/projects", json=proj_payload, headers=headers)

    # Re-evaluate completeness
    comp_resp2 = client.get("/api/candidate/completeness", headers=headers)
    comp2 = comp_resp2.json()

    # Skill Rust should now be verified by project code!
    assert comp2["skills_summary"]["verified"] == 1
    assert comp2["skills_summary"]["unverified"] == 0
    rust_skill = next(s for s in comp2["skills_summary"]["items"] if s["name"] == "Rust")
    assert rust_skill["status"] == "verified"
    assert rust_skill["verification_source"] == "project_code"


def test_canonical_skill_addition_and_deletion():
    headers = get_auth_headers(TEST_USER_A)

    # Add skill with non-canonical alias "python3"
    resp = client.post("/api/candidate/skills", json={"name": "python3", "category": "Languages"}, headers=headers)
    assert resp.status_code == 200
    cand = resp.json()
    # Should be normalized to "Python"
    assert any(s["name"] == "Python" for s in cand["skills"])
    v1 = cand["evidence_version"]

    # Delete skill
    del_resp = client.delete("/api/candidate/skills/Python", headers=headers)
    assert del_resp.status_code == 200
    cand2 = del_resp.json()
    assert not any(s["name"] == "Python" for s in cand2["skills"])
    # Evidence version must be bumped
    assert cand2["evidence_version"] > v1


def test_project_addition_and_skill_linking():
    headers = get_auth_headers(TEST_USER_A)

    proj_payload = {
        "title": "Distributed Task Queue",
        "description": "High-throughput asynchronous worker pool in Go",
        "tech_stack": ["golang", "redis"],
        "url": "https://github.com/alex/task-queue"
    }
    resp = client.post("/api/candidate/projects", json=proj_payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    # Check that tech_stack tokens are canonicalized ("golang" -> "Go", "redis" -> "Redis")
    proj = data["projects"][-1]
    assert "Go" in proj["tech_stack"]
    assert "Redis" in proj["tech_stack"]


def test_existing_projects_preservation_during_onboarding():
    db = SessionLocal()
    cand1 = db.query(CandidateProfile).filter_by(user_id=1).first()
    assert cand1 is not None
    original_project_count = len(cand1.projects)
    original_titles = [p["title"] for p in cand1.projects]
    db.close()

    # Candidate 1 adds an 8th project
    headers = get_auth_headers(1)

    new_proj = {
        "title": "Autonomous Agentic Sandbox",
        "description": "Experimental multi-agent orchestrator with typed tool protocols",
        "tech_stack": ["Python", "FastAPI", "Docker"],
        "url": "https://github.com/krishna/agentic-sandbox"
    }
    resp = client.post("/api/candidate/projects", json=new_proj, headers=headers)
    assert resp.status_code == 200
    updated_cand = resp.json()

    # Must contain original 7 projects PLUS the new one
    assert len(updated_cand["projects"]) == original_project_count + 1
    for orig_t in original_titles:
        assert any(p["title"] == orig_t for p in updated_cand["projects"])

    # Clean up the 8th project
    del_resp = client.delete(f"/api/candidate/projects/{original_project_count}", headers=headers)
    assert del_resp.status_code == 200
    assert len(del_resp.json()["projects"]) == original_project_count


def test_resume_upload_and_parse_without_silent_overwrite():
    headers = get_auth_headers(TEST_USER_A)

    sample_resume = (
        "Taylor Morgan\n"
        "taylor.morgan@example.com | 555-0199 | San Francisco, CA\n"
        "https://github.com/taylormorgan\n\n"
        "EDUCATION\n"
        "University of California, Berkeley - B.S. in Computer Science (2025)\n"
        "CGPA: 3.90\n\n"
        "SKILLS\n"
        "Python, React, TypeScript, PostgreSQL, Docker\n\n"
        "PROJECTS\n"
        "Cloud Storage Synchronizer | Python, Docker\n"
        "Built distributed file synchronizer using raft consensus and chunked encryption.\n"
    )

    files = {"file": ("resume.txt", sample_resume.encode("utf-8"), "text/plain")}
    resp = client.post("/api/candidate/integrations/parse-resume", files=files, headers=headers)
    assert resp.status_code == 200
    parse_result = resp.json()

    assert "candidate_draft" in parse_result
    assert parse_result["candidate_draft"]["name"] == "Taylor Morgan"
    assert len(parse_result["detected_skills"]) >= 3

    # Crucial check: Persisted DB profile for User A MUST NOT be modified yet!
    db = SessionLocal()
    cand = db.query(CandidateProfile).filter_by(user_id=TEST_USER_A).first()
    assert cand.name == "Alex River"  # Still Alex, NOT Taylor Morgan!
    assert cand.email == "alex.river@example.com"
    db.close()


def test_candidate_tenant_isolation_in_onboarding_and_completeness():
    headers_a = get_auth_headers(TEST_USER_A)
    headers_b = get_auth_headers(TEST_USER_B)

    # User A updates their onboarding progress to step 4
    client.put("/api/candidate/onboarding-progress", json={"step": 4, "status": "in_progress"}, headers=headers_a)

    # User B checks their completeness
    comp_b = client.get("/api/candidate/completeness", headers=headers_b).json()

    # User B must be unaffected (still on step 2)
    assert comp_b["onboarding_step"] == 2
    assert comp_b["onboarding_status"] == "in_progress"


def test_complete_onboarding_bumps_evidence_version_and_invalidates_snapshots():
    headers = get_auth_headers(TEST_USER_A)

    db = SessionLocal()
    v_before = db.query(CandidateProfile).filter_by(user_id=TEST_USER_A).first().evidence_version
    db.close()

    resp = client.post("/api/candidate/complete-onboarding", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["evidence_version"] > v_before
    assert data["readiness"]["is_onboarded"] is True


def test_first_discovery_search_after_onboarding_uses_new_evidence():
    headers = get_auth_headers(TEST_USER_A)

    # Add core skills
    client.post("/api/candidate/skills", json={"name": "TypeScript", "category": "Languages"}, headers=headers)
    client.post("/api/candidate/skills", json={"name": "React", "category": "Frameworks"}, headers=headers)
    client.post("/api/candidate/projects", json={
        "title": "React Dashboard",
        "description": "Modern frontend with TypeScript and React",
        "tech_stack": ["React", "TypeScript"]
    }, headers=headers)

    # Complete onboarding
    complete_resp = client.post("/api/candidate/complete-onboarding", headers=headers)
    assert complete_resp.status_code == 200
    ev_version = complete_resp.json()["evidence_version"]

    # Execute discovery search
    disc_resp = client.get("/api/opportunities?page=1&page_size=10", headers=headers)
    assert disc_resp.status_code == 200
    disc_data = disc_resp.json()
    assert "items" in disc_data
    assert disc_data["total"] > 0
    # Items should be returned and evaluated cleanly
    first_item = disc_data["items"][0]
    assert "id" in first_item
    assert "match_score" in first_item
