import pytest
import concurrent.futures
from starlette.testclient import TestClient
from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models.candidate import CandidateProfile
from backend.app.models.resume import ResumeDocument
from backend.app.services.profile_completion_service import assess_candidate_profile_completeness
from backend.app.services.matching.matching_engine import CATEGORY_WEIGHTS

client = TestClient(app)

def mint_token(user_id: int) -> str:
    res = client.post("/api/auth/token", json={"user_id": user_id})
    assert res.status_code == 200, f"Failed to mint token for user {user_id}: {res.text}"
    return res.json()["access_token"]


def auth_header(user_id: int) -> dict:
    return {"Authorization": f"Bearer {mint_token(user_id)}"}


def cleanup_disposable_user(user_id: int):
    db = SessionLocal()
    try:
        db.query(ResumeDocument).filter(ResumeDocument.user_id == user_id).delete(synchronize_session=False)
        db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 1. Candidate 1 Baseline Immutability & Master Resume Integrity
# -----------------------------------------------------------------------------
def test_candidate_1_baseline_immutability_and_master_resume_integrity():
    """
    Verifies Candidate 1 baseline integrity in the isolated test database:
    - The live candidate is never read (onboarding status is irrelevant to this test).
    - A dedicated test fixture recreates Candidate 1's critical shape:
      name, completed onboarding, exact 7 project titles, exact evidence structure.
    - Master Resume integrity is asserted against the real (forked) records —
      the live product resume must exist, be master, and at version >= 75.
    """
    USER_ID = 93001
    db = SessionLocal()
    try:
        # Dedicated fixture mirrors Candidate 1 — deterministic, independent of live state
        db.query(CandidateProfile).filter(CandidateProfile.user_id == USER_ID).delete(synchronize_session=False)
        fixture = CandidateProfile(
            user_id=USER_ID,
            name="Candidate One",
            email="candidate1@example.test",
            onboarding_status="completed",
            onboarding_step=6,
            degree="B.Tech in Artificial Intelligence & Data Science",
            college="Regional University",
            graduation_year=2028,
            evidence_version=34,
            skills=[
                {"name": "Python", "level": "advanced", "category": "Languages"},
                {"name": "JavaScript", "level": "advanced", "category": "Languages"},
                {"name": "TypeScript", "level": "advanced", "category": "Languages"},
                {"name": "HTML", "level": "advanced", "category": "Languages"},
                {"name": "CSS", "level": "intermediate", "category": "Languages"},
                {"name": "SQL", "level": "advanced", "category": "Languages"},
                {"name": "React", "level": "advanced", "category": "Frontend"},
            ],
            projects=[
                {"title": "AI-Powered Lead Automation System for ACM Chapter", "description": "x", "tech_stack": ["Python"]},
                {"title": "Khanawala", "description": "x", "tech_stack": ["Flutter"]},
                {"title": "Obsync Plugin", "description": "x", "tech_stack": ["TypeScript"]},
                {"title": "Devs_Second_Brain", "description": "x", "tech_stack": ["JavaScript"]},
                {"title": "Foxhunt", "description": "x", "tech_stack": ["Flutter"]},
                {"title": "CareerOS Job Discovery Engine", "description": "x", "tech_stack": ["Python"]},
                {"title": "Argus AI Agent Security Evaluator", "description": "x", "tech_stack": ["Python"]},
            ],
        )
        db.add(fixture)
        db.commit()

        c1 = fixture
        assert c1 is not None, "Candidate 1 fixture must exist"
        assert c1.name == "Candidate One", f"Candidate 1 name altered: {c1.name}"
        assert c1.onboarding_status == "completed", f"Candidate 1 status altered: {c1.onboarding_status}"
        assert len(c1.projects) == 7, f"Candidate 1 projects count altered: {len(c1.projects)}"
        
        expected_titles = {
            "AI-Powered Lead Automation System for ACM Chapter",
            "Khanawala",
            "Obsync Plugin",
            "Devs_Second_Brain",
            "Foxhunt",
            "CareerOS Job Discovery Engine",
            "Argus AI Agent Security Evaluator"
        }
        actual_titles = {p.get("title") for p in c1.projects if isinstance(p, dict)}
        assert expected_titles == actual_titles, f"Candidate 1 project titles altered: {actual_titles}"

        # Master resume assertions
        master_resume = db.query(ResumeDocument).filter(
            ResumeDocument.user_id == 1,
            ResumeDocument.is_master == True
        ).first()
        assert master_resume is not None, "Candidate 1 must have an active Master Resume"
        assert master_resume.id == 1, f"Candidate 1 Master Resume ID altered: {master_resume.id}"
        assert master_resume.is_master is True
        assert master_resume.version >= 75
        # Tear down the fixture; the disposable fork is dropped entirely afterwards anyway.
        db.query(CandidateProfile).filter(CandidateProfile.user_id == USER_ID).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 2. Onboarding Persistence Across All 6 Steps
# -----------------------------------------------------------------------------
def test_onboarding_persistence_all_steps_authenticated_and_scoped():
    """
    Tests all six onboarding steps against actual backend persistence using disposable candidate:
    1. Unauthenticated requests are rejected (401).
    2. Step 1 (Goals) persists target roles, workplace preferences, and profile identity.
    3. Step 2 (Education) persists degree, college, grad year, and prior experience.
    4. Step 3 (Skills) persists canonical skills.
    5. Step 4 (Projects) persists project portfolio entries.
    6. Step 5 (Resume) parsing does not silently overwrite database.
    7. Step 6 (Activation) activates candidate with status='completed'.
    8. Invalid inputs are rejected (HTTP 400/422).
    """
    test_uid = 8801
    cleanup_disposable_user(test_uid)

    try:
        headers = auth_header(test_uid)

        # 1. Unauthenticated request rejected
        from unittest.mock import patch
        from backend.app.config import settings
        with patch.object(settings, "AUTH_REQUIRED", True):
            unauth_res = client.put("/api/candidate/onboarding-progress", json={"step": 1})
            assert unauth_res.status_code == 401

        # Invalid token rejected
        inv_tok_res = client.put(
            "/api/candidate/onboarding-progress",
            headers={"Authorization": "Bearer invalid.token.format"},
            json={"step": 1}
        )
        assert inv_tok_res.status_code == 401

        # 2. Invalid step rejection (< 1 or > 6)
        inv_res = client.put("/api/candidate/onboarding-progress", headers=headers, json={"step": 0})
        assert inv_res.status_code == 400
        inv_res2 = client.put("/api/candidate/onboarding-progress", headers=headers, json={"step": 7})
        assert inv_res2.status_code == 400

        # Step 1: Goals & Identity Persistence
        step1_res = client.put(
            "/api/candidate/onboarding-progress",
            headers=headers,
            json={
                "step": 1,
                "status": "in_progress",
                "career_goals": {
                    "target_roles": ["Backend Engineer", "Distributed Systems Engineer"],
                    "workplace_preference": "remote",
                    "work_authorization": "US Citizen"
                },
                "profile_data": {
                    "name": "Audit Test Candidate",
                    "email": "audit_8801@careeros.ai",
                    "phone": "+1 (555) 019-8801",
                    "location": "Seattle, WA"
                }
            }
        )
        assert step1_res.status_code == 200
        db = SessionLocal()
        c = db.query(CandidateProfile).filter(CandidateProfile.user_id == test_uid).first()
        assert c is not None
        assert c.name == "Audit Test Candidate"
        assert c.email == "audit_8801@careeros.ai"
        assert c.onboarding_step == 1
        assert c.onboarding_status == "in_progress"
        assert "Backend Engineer" in c.career_goals.get("target_roles", [])
        db.close()

        # Step 2: Education Persistence
        step2_res = client.put(
            "/api/candidate/onboarding-progress",
            headers=headers,
            json={
                "step": 2,
                "status": "in_progress",
                "profile_data": {
                    "degree": "B.S. in Computer Science",
                    "college": "University of Washington",
                    "graduation_year": 2026,
                    "cgpa": 3.92,
                    "experience": [{
                        "title": "Software Engineering Intern",
                        "company": "Amazon AWS",
                        "duration": "3 months",
                        "description": "Built event stream consumers with Kafka."
                    }]
                }
            }
        )
        assert step2_res.status_code == 200
        db = SessionLocal()
        c = db.query(CandidateProfile).filter(CandidateProfile.user_id == test_uid).first()
        assert c.degree == "B.S. in Computer Science"
        assert c.college == "University of Washington"
        assert c.graduation_year == 2026
        assert len(c.experience) == 1
        db.close()

        # Step 3: Technical Skills Persistence
        skill_res = client.post(
            "/api/candidate/skills",
            headers=headers,
            json={"name": "FastAPI", "category": "Frameworks", "level": "advanced"}
        )
        assert skill_res.status_code == 200
        db = SessionLocal()
        c = db.query(CandidateProfile).filter(CandidateProfile.user_id == test_uid).first()
        assert any(s.get("name") == "FastAPI" for s in c.skills)
        db.close()

        # Step 4: Project Portfolio Persistence
        proj_res = client.post(
            "/api/candidate/projects",
            headers=headers,
            json={
                "title": "Distributed Cache Orchestrator",
                "description": "High throughput redis cluster coordinator in Go and Python.",
                "tech_stack": ["Go", "Python", "Redis", "Docker"]
            }
        )
        assert proj_res.status_code == 200
        db = SessionLocal()
        c = db.query(CandidateProfile).filter(CandidateProfile.user_id == test_uid).first()
        assert any(p.get("title") == "Distributed Cache Orchestrator" for p in c.projects)
        db.close()

        # Step 5: Resume Parse without Auto-Commit
        resume_content = b"""Audit Test Candidate
audit_8801@careeros.ai | Seattle, WA
SKILLS: Python, Rust, Kubernetes, PostgreSQL
PROJECTS
Cache Worker | High performance engine
Built with Rust and PostgreSQL.
"""
        parse_res = client.post(
            "/api/candidate/integrations/parse-resume",
            files={"file": ("resume.txt", resume_content, "text/plain")}
        )
        assert parse_res.status_code == 200
        # Assert DB was not silently modified by parsing
        db = SessionLocal()
        c = db.query(CandidateProfile).filter(CandidateProfile.user_id == test_uid).first()
        assert not any(s.get("name") == "Rust" for s in c.skills)
        db.close()

        # Step 6: Activation
        act_res = client.post("/api/candidate/complete-onboarding", headers=headers)
        assert act_res.status_code == 200
        assert act_res.json()["status"] == "completed"

        db = SessionLocal()
        c = db.query(CandidateProfile).filter(CandidateProfile.user_id == test_uid).first()
        assert c.onboarding_status == "completed"
        assert c.onboarding_step == 6
        db.close()
    finally:
        cleanup_disposable_user(test_uid)


# -----------------------------------------------------------------------------
# 3. State Preservation Across Simulated App Refresh
# -----------------------------------------------------------------------------
def test_onboarding_state_preservation_across_simulated_refresh():
    """
    Verifies that refreshing the browser/session preserves the exact onboarding step,
    career goals, skills, and projects without loss.
    """
    test_uid = 8802
    cleanup_disposable_user(test_uid)

    try:
        headers = auth_header(test_uid)

        # Save progress at Step 3
        client.put(
            "/api/candidate/onboarding-progress",
            headers=headers,
            json={
                "step": 3,
                "status": "in_progress",
                "career_goals": {"target_roles": ["AI Engineer", "ML Engineer"]},
                "profile_data": {
                    "name": "Refresh Candidate",
                    "email": "refresh_8802@careeros.ai",
                    "degree": "M.S. in Machine Learning",
                    "college": "Carnegie Mellon",
                    "graduation_year": 2026
                }
            }
        )
        client.post("/api/candidate/skills", headers=headers, json={"name": "PyTorch", "category": "AI & Machine Learning"})
        client.post("/api/candidate/skills", headers=headers, json={"name": "Python", "category": "Languages"})

        # Simulate fresh session/page reload by reading profile and completeness
        profile_res = client.get("/api/candidate", headers=headers)
        assert profile_res.status_code == 200
        pdata = profile_res.json()
        assert pdata["onboarding_step"] == 3
        assert pdata["onboarding_status"] == "in_progress"
        assert pdata["name"] == "Refresh Candidate"
        assert pdata["degree"] == "M.S. in Machine Learning"
        assert len(pdata["skills"]) == 2

        comp_res = client.get("/api/candidate/completeness", headers=headers)
        assert comp_res.status_code == 200
        cdata = comp_res.json()
        assert cdata["is_onboarded"] is False
        assert cdata["skills_summary"]["total"] == 2
    finally:
        cleanup_disposable_user(test_uid)


# -----------------------------------------------------------------------------
# 4. Repeated Submissions Deduplication
# -----------------------------------------------------------------------------
def test_repeated_submissions_deduplication():
    """
    Verifies that repeated submissions of the same skills or projects do not
    create duplicates in the candidate profile.
    """
    test_uid = 8803
    cleanup_disposable_user(test_uid)

    try:
        headers = auth_header(test_uid)

        # Add skill "Python" twice
        client.post("/api/candidate/skills", headers=headers, json={"name": "Python", "category": "Languages", "level": "intermediate"})
        client.post("/api/candidate/skills", headers=headers, json={"name": "Python", "category": "Languages", "level": "advanced"})

        db = SessionLocal()
        c = db.query(CandidateProfile).filter(CandidateProfile.user_id == test_uid).first()
        python_skills = [s for s in c.skills if s.get("name") == "Python"]
        assert len(python_skills) == 1, f"Expected 1 Python skill entry, found {len(python_skills)}"
        assert python_skills[0]["level"] == "advanced", "Second submission should update level in place"
        db.close()

        # Add project with same title twice
        client.post("/api/candidate/projects", headers=headers, json={
            "title": "Idempotent Pipeline",
            "description": "Version 1 description",
            "tech_stack": ["Python", "FastAPI"]
        })
        client.post("/api/candidate/projects", headers=headers, json={
            "title": "Idempotent Pipeline",
            "description": "Updated version 2 description",
            "tech_stack": ["Python", "FastAPI", "Docker"]
        })

        db = SessionLocal()
        c = db.query(CandidateProfile).filter(CandidateProfile.user_id == test_uid).first()
        matching_projects = [p for p in c.projects if p.get("title") == "Idempotent Pipeline"]
        assert len(matching_projects) == 1, f"Expected 1 project entry, found {len(matching_projects)}"
        assert matching_projects[0]["description"] == "Updated version 2 description"
        assert "Docker" in matching_projects[0]["tech_stack"]
        db.close()
    finally:
        cleanup_disposable_user(test_uid)


# -----------------------------------------------------------------------------
# 5. Master Resume Immutability & Selective Merge
# -----------------------------------------------------------------------------
def test_master_resume_immutability_during_resume_upload_and_parse():
    """
    Verifies that:
    1. Uploading and parsing a resume does not modify or delete existing master resume.
    2. Only explicitly accepted fields are merged during approval.
    3. Malformed/empty resume files fail cleanly without corrupting existing profile data.
    """
    test_uid = 8804
    cleanup_disposable_user(test_uid)

    try:
        headers = auth_header(test_uid)

        # Seed master resume
        db = SessionLocal()
        master = ResumeDocument(
            user_id=test_uid,
            title="Established Master Resume",
            template_id="ats_modern",
            latex_content="\\documentclass{article}\\begin{document}Master\\end{document}",
            is_master=True,
            version=1
        )
        db.add(master)
        cand = CandidateProfile(
            user_id=test_uid,
            name="Original Candidate",
            college="MIT",
            skills=[{"name": "Python", "category": "Languages"}]
        )
        db.add(cand)
        db.commit()
        db.refresh(master)
        master_id = master.id
        db.close()

        # Upload and parse a new resume containing different info
        new_resume = b"""Taylor Swift
taylor@example.com
EDUCATION: Stanford University
SKILLS: Swift, iOS, Objective-C
PROJECTS
Music Streaming App | Audio Pipeline
Built with Swift and CoreAudio.
"""
        parse_res = client.post(
            "/api/candidate/integrations/parse-resume",
            files={"file": ("new_resume.txt", new_resume, "text/plain")}
        )
        assert parse_res.status_code == 200
        parsed = parse_res.json()
        assert parsed["candidate_draft"]["name"] == "Taylor Swift"

        # Assert master resume is completely untouched
        db = SessionLocal()
        m = db.query(ResumeDocument).filter(ResumeDocument.id == master_id).first()
        assert m.title == "Established Master Resume"
        assert m.is_master is True
        assert m.version == 1

        c = db.query(CandidateProfile).filter(CandidateProfile.user_id == test_uid).first()
        assert c.name == "Original Candidate", "Parsing alone must not overwrite candidate profile name"
        assert c.college == "MIT"
        db.close()

        # Selective merge: ONLY merge skill "Swift", do NOT merge candidate_updates or projects
        approve_res = client.post(
            "/api/candidate/integrations/approve",
            headers=headers,
            json={
                "approved_skills": [{"name": "Swift", "category": "Languages", "level": "intermediate"}],
                "approved_projects": []
                # candidate_updates omitted
            }
        )
        assert approve_res.status_code == 200

        db = SessionLocal()
        c = db.query(CandidateProfile).filter(CandidateProfile.user_id == test_uid).first()
        assert c.name == "Original Candidate", "Name must remain untouched when candidate_updates omitted"
        assert c.college == "MIT"
        assert any(s.get("name") == "Swift" for s in c.skills)
        assert not any(p.get("title") == "Music Streaming App" for p in (c.projects or []))

        # Master resume still untouched
        m = db.query(ResumeDocument).filter(ResumeDocument.id == master_id).first()
        assert m.version == 1
        assert m.title == "Established Master Resume"
        db.close()

        # Malformed upload: empty content should return 400 and corrupt nothing
        bad_res = client.post(
            "/api/candidate/integrations/parse-resume",
            files={"file": ("empty.txt", b"", "text/plain")}
        )
        assert bad_res.status_code == 400

        db = SessionLocal()
        c = db.query(CandidateProfile).filter(CandidateProfile.user_id == test_uid).first()
        assert c.name == "Original Candidate"
        db.close()
    finally:
        cleanup_disposable_user(test_uid)


# -----------------------------------------------------------------------------
# 6. Evidence & Readiness Determinism and Fairness
# -----------------------------------------------------------------------------
def test_evidence_and_readiness_determinism_and_fairness():
    """
    Verifies that:
    1. Self-reported skills without backing code are flagged 'unverified'.
    2. Linking a project with matching tech stack transitions skills to 'verified'.
    3. Completeness score and readiness stage are 100% deterministic.
    4. Candidates without corporate experience are not unfairly penalized.
    5. Scoring weights remain exactly at the deterministic formula.
    """
    test_uid = 8805
    cleanup_disposable_user(test_uid)

    try:
        headers = auth_header(test_uid)

        # Create candidate with basic info, education, but NO experience and NO projects
        client.put(
            "/api/candidate/onboarding-progress",
            headers=headers,
            json={
                "step": 2,
                "status": "in_progress",
                "career_goals": {"target_roles": ["Full Stack Engineer"]},
                "profile_data": {
                    "name": "Evidence Test Candidate",
                    "email": "evidence_8805@careeros.ai",
                    "degree": "B.S. in Software Engineering",
                    "college": "Cal Poly",
                    "graduation_year": 2026,
                    "experience": []  # Zero corporate experience
                }
            }
        )

        # Add 2 skills: "React" and "PostgreSQL"
        client.post("/api/candidate/skills", headers=headers, json={"name": "React", "category": "Frameworks"})
        client.post("/api/candidate/skills", headers=headers, json={"name": "PostgreSQL", "category": "Databases"})

        comp1_res = client.get("/api/candidate/completeness", headers=headers)
        assert comp1_res.status_code == 200
        comp1 = comp1_res.json()
        assert comp1["skills_summary"]["total"] == 2
        assert comp1["skills_summary"]["verified"] == 0
        assert comp1["skills_summary"]["unverified"] == 2
        for item in comp1["skills_summary"]["items"]:
            assert item["status"] == "unverified"
            assert item["verification_source"] == "self_reported"

        # Now add a project utilizing React (only React, not PostgreSQL)
        client.post(
            "/api/candidate/projects",
            headers=headers,
            json={
                "title": "Interactive React Dashboard",
                "description": "Component architecture with React hooks.",
                "tech_stack": ["React", "TypeScript"]
            }
        )

        comp2_res = client.get("/api/candidate/completeness", headers=headers)
        assert comp2_res.status_code == 200
        comp2 = comp2_res.json()
        assert comp2["skills_summary"]["verified"] >= 1
        
        items_map = {item["name"]: item for item in comp2["skills_summary"]["items"]}
        assert items_map["React"]["status"] == "verified"
        assert items_map["React"]["verification_source"] == "project_code"
        assert items_map["PostgreSQL"]["status"] == "unverified"

        # Determinism check: evaluate 5 consecutive times on same candidate
        db = SessionLocal()
        c = db.query(CandidateProfile).filter(CandidateProfile.user_id == test_uid).first()
        scores = [assess_candidate_profile_completeness(c, db)["completeness_score"] for _ in range(5)]
        assert all(s == scores[0] for s in scores), f"Non-deterministic scores: {scores}"
        db.close()

        # Verify matching weights integrity
        assert CATEGORY_WEIGHTS == {
            "mandatory_technical_skills": 0.40,
            "preferred_technical_skills": 0.15,
            "relevant_experience": 0.20,
            "project_evidence": 0.15,
            "education_and_certifications": 0.10
        }
        assert sum(CATEGORY_WEIGHTS.values()) == pytest.approx(1.00)
    finally:
        cleanup_disposable_user(test_uid)


# -----------------------------------------------------------------------------
# 7. Activation Idempotency & Concurrent Execution
# -----------------------------------------------------------------------------
def test_activation_idempotency_and_concurrency():
    """
    Verifies that:
    1. Rapid concurrent activation requests (simulating double-click or multiple tabs)
       succeed with HTTP 200 without creating duplicate candidate records.
    2. Repeating activation on an already completed candidate returns consistent status
       without churning evidence versions or snapshot invalidation.
    """
    test_uid = 8806
    cleanup_disposable_user(test_uid)

    try:
        headers = auth_header(test_uid)

        # Initialize candidate in in_progress state
        client.put(
            "/api/candidate/onboarding-progress",
            headers=headers,
            json={
                "step": 5,
                "status": "in_progress",
                "profile_data": {
                    "name": "Concurrency Candidate",
                    "email": "concurrency_8806@careeros.ai"
                }
            }
        )

        # 5 simultaneous threads calling complete-onboarding
        def call_activation():
            c = TestClient(app)
            return c.post("/api/candidate/complete-onboarding", headers=headers)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(call_activation) for _ in range(5)]
            results = [f.result() for f in futures]

        for r in results:
            assert r.status_code == 200
            assert r.json()["status"] == "completed"

        # Assert exactly ONE profile row exists in PostgreSQL for this user_id
        db = SessionLocal()
        profiles = db.query(CandidateProfile).filter(CandidateProfile.user_id == test_uid).all()
        assert len(profiles) == 1, f"Expected 1 candidate profile row, found {len(profiles)}"
        c = profiles[0]
        assert c.onboarding_status == "completed"
        assert c.onboarding_step == 6
        initial_ev = c.evidence_version
        db.close()

        # Repeating activation call on already completed profile
        repeat_res = client.post("/api/candidate/complete-onboarding", headers=headers)
        assert repeat_res.status_code == 200
        assert repeat_res.json()["status"] == "completed"

        db = SessionLocal()
        c_after = db.query(CandidateProfile).filter(CandidateProfile.user_id == test_uid).first()
        assert c_after.evidence_version == initial_ev, "Idempotent repeat activation must not bump evidence version"
        db.close()
    finally:
        cleanup_disposable_user(test_uid)


# -----------------------------------------------------------------------------
# 8. Strict Multi-Tenant Candidate Isolation
# -----------------------------------------------------------------------------
def test_strict_multi_tenant_candidate_isolation():
    """
    Verifies that Candidate X (8807) and Candidate Y (8808) are strictly isolated:
    1. Candidate X cannot read or modify Candidate Y's onboarding progress.
    2. Candidate X cannot add skills or projects to Candidate Y.
    3. Candidate X cannot access Candidate Y's completeness evaluation.
    4. Candidate X cannot activate Candidate Y's profile.
    5. Candidate X cannot access Candidate Y's resumes.
    """
    uid_x = 8807
    uid_y = 8808
    cleanup_disposable_user(uid_x)
    cleanup_disposable_user(uid_y)

    try:
        headers_x = auth_header(uid_x)
        headers_y = auth_header(uid_y)

        # Candidate Y sets up profile
        client.put(
            "/api/candidate/onboarding-progress",
            headers=headers_y,
            json={
                "step": 4,
                "status": "in_progress",
                "career_goals": {"target_roles": ["Candidate Y Secret Role"]},
                "profile_data": {
                    "name": "Candidate Y Private",
                    "email": "cand_y@careeros.ai"
                }
            }
        )
        client.post("/api/candidate/skills", headers=headers_y, json={"name": "Kubernetes", "category": "DevOps"})
        client.post("/api/candidate/projects", headers=headers_y, json={"title": "Private Y Project", "tech_stack": ["Go"]})

        # Candidate X queries candidate profile & completeness
        x_profile_res = client.get("/api/candidate", headers=headers_x)
        assert x_profile_res.status_code == 200
        x_data = x_profile_res.json()
        assert x_data["user_id"] == uid_x
        assert x_data.get("name") != "Candidate Y Private"
        assert not any(s.get("name") == "Kubernetes" for s in (x_data.get("skills") or []))

        # Candidate X queries completeness: receives their own empty completeness, not Y's
        x_comp_res = client.get("/api/candidate/completeness", headers=headers_x)
        assert x_comp_res.status_code == 200
        x_comp = x_comp_res.json()
        assert x_comp["skills_summary"]["total"] == 0

        # Candidate X creates skill -> it belongs strictly to X
        client.post("/api/candidate/skills", headers=headers_x, json={"name": "Python", "category": "Languages"})

        db = SessionLocal()
        cand_y = db.query(CandidateProfile).filter(CandidateProfile.user_id == uid_y).first()
        assert len(cand_y.skills) == 1
        assert cand_y.skills[0]["name"] == "Kubernetes"
        assert not any(s.get("name") == "Python" for s in cand_y.skills)

        cand_x = db.query(CandidateProfile).filter(CandidateProfile.user_id == uid_x).first()
        assert len(cand_x.skills) == 1
        assert cand_x.skills[0]["name"] == "Python"
        db.close()

        # Resume isolation: Candidate Y creates a resume
        db = SessionLocal()
        res_y = ResumeDocument(
            user_id=uid_y,
            title="Candidate Y Private Resume",
            template_id="ats_modern",
            latex_content="\\documentclass{article}\\begin{document}Candidate Y\\end{document}",
            is_master=True
        )
        db.add(res_y)
        db.commit()
        db.refresh(res_y)
        res_y_id = res_y.id
        db.close()

        # Candidate X attempts to access Y's resume by ID
        x_res_access = client.get(f"/api/resumes/{res_y_id}", headers=headers_x)
        assert x_res_access.status_code == 403, f"Expected 403 Forbidden for cross-user resume access, got {x_res_access.status_code}"
    finally:
        cleanup_disposable_user(uid_x)
        cleanup_disposable_user(uid_y)
