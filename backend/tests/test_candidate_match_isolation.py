"""
Integration Test Suite for CareerOS Iteration 1.8: Candidate-Scoped Match Result Isolation.
Reproduces cross-candidate cache overwrites and verifies isolated persistence across
two independent candidates evaluating the same public opportunity.
"""
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.core.auth import create_access_token
from backend.app.models.candidate import CandidateProfile
from backend.app.models.opportunity import Opportunity

client = TestClient(app)

USER_A = 99801  # Candidate A: Python/FastAPI/PostgreSQL Specialist
USER_B = 99802  # Candidate B: Java/Spring Boot Specialist


def auth_headers(user_id: int):
    token = create_access_token(user_id=user_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def setup_candidates_and_public_opportunity():
    db = SessionLocal()
    try:
        # Clean prior test data
        db.query(Opportunity).filter(
            (Opportunity.user_id.in_([USER_A, USER_B])) |
            (Opportunity.original_url.like("https://example.com/iso_%"))
        ).delete(synchronize_session=False)
        db.query(CandidateProfile).filter(CandidateProfile.user_id.in_([USER_A, USER_B])).delete(synchronize_session=False)
        db.commit()

        # Candidate A: Strong Python backend developer
        cand_a = CandidateProfile(
            user_id=USER_A,
            name="Alice Python",
            email="alice@python.test",
            skills=[
                {"name": "Python", "level": "expert", "category": "language"},
                {"name": "FastAPI", "level": "advanced", "category": "framework"},
                {"name": "PostgreSQL", "level": "advanced", "category": "database"},
                {"name": "Docker", "level": "intermediate", "category": "devops"}
            ],
            projects=[
                {"title": "API Gateway", "tech_stack": ["Python", "FastAPI", "PostgreSQL"], "is_verified": True},
                {"title": "Data Pipeline", "tech_stack": ["Python", "Docker"], "is_verified": True}
            ],
            degree="Bachelor of Science in Computer Science",
            experience=[{"title": "Backend Intern", "company": "Tech", "duration": "12 months"}]
        )

        # Candidate B: Java enterprise developer (lacks Python/FastAPI)
        cand_b = CandidateProfile(
            user_id=USER_B,
            name="Bob Java",
            email="bob@java.test",
            skills=[
                {"name": "Java", "level": "expert", "category": "language"},
                {"name": "Spring Boot", "level": "advanced", "category": "framework"},
                {"name": "MySQL", "level": "intermediate", "category": "database"}
            ],
            projects=[
                {"title": "Enterprise ERP", "tech_stack": ["Java", "Spring Boot", "MySQL"], "is_verified": True}
            ],
            degree="Bachelor of Engineering in Mechanical Engineering",
            experience=[{"title": "Junior Developer", "company": "Legacy Corp", "duration": "6 months"}]
        )

        # Shared Public Opportunity (user_id = None) requiring Python & FastAPI
        opp_pub = Opportunity(
            user_id=None,
            title="Senior Python Backend Engineer",
            normalized_title="Senior Python Backend Engineer",
            company_name="CloudScale Technologies",
            description=(
                "We are looking for a Senior Python Backend Engineer.\n"
                "Requirements:\n"
                "- Strong proficiency in Python and FastAPI (Mandatory)\n"
                "- Experience with PostgreSQL and Docker (Mandatory)\n"
                "- Minimum 1+ years of experience\n"
                "- BS in Computer Science preferred\n"
            ),
            source_platform="greenhouse",
            original_url="https://example.com/iso_public_job_1",
            match_score=0.0,
            match_analysis={}
        )

        db.add(cand_a)
        db.add(cand_b)
        db.add(opp_pub)
        db.commit()
        db.refresh(opp_pub)

        yield {"opp_id": opp_pub.id, "user_a": USER_A, "user_b": USER_B}

    finally:
        db.query(Opportunity).filter(
            (Opportunity.user_id.in_([USER_A, USER_B])) |
            (Opportunity.original_url.like("https://example.com/iso_%"))
        ).delete(synchronize_session=False)
        db.query(CandidateProfile).filter(CandidateProfile.user_id.in_([USER_A, USER_B])).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_phase2_multi_candidate_public_opportunity_lifecycle(setup_candidates_and_public_opportunity):
    """
    Tests complete Phase 2 sequence on a shared public opportunity:
    1. Candidate A evaluates public opportunity.
    2. Candidate B evaluates the same public opportunity.
    3. Candidate A retrieves the opportunity again (must preserve Candidate A's result!).
    4. Candidate B retrieves the opportunity again (must preserve Candidate B's result!).
    5. Both candidates force-refresh their evaluations.
    6. Both candidates update their profiles and reevaluate.
    7. Opportunity description changes and both candidates reevaluate.
    """
    fixture = setup_candidates_and_public_opportunity
    opp_id = fixture["opp_id"]

    # -------------------------------------------------------------
    # Step 1: Candidate A evaluates the public opportunity
    # -------------------------------------------------------------
    resp_eval_a = client.post(
        f"/api/opportunities/{opp_id}/evaluate-match",
        headers=auth_headers(USER_A),
        json={"force_refresh": True, "use_ai": False}
    )
    assert resp_eval_a.status_code == 200
    data_eval_a = resp_eval_a.json()
    score_a_initial = data_eval_a["profile_match_score"]
    assert score_a_initial >= 80.0, f"Candidate A should have high match score, got {score_a_initial}"
    assert data_eval_a["eligibility_status"] == "eligible"
    assert data_eval_a["user_id"] == USER_A

    # -------------------------------------------------------------
    # Step 2: Candidate B evaluates the same public opportunity
    # -------------------------------------------------------------
    resp_eval_b = client.post(
        f"/api/opportunities/{opp_id}/evaluate-match",
        headers=auth_headers(USER_B),
        json={"force_refresh": True, "use_ai": False}
    )
    assert resp_eval_b.status_code == 200
    data_eval_b = resp_eval_b.json()
    score_b_initial = data_eval_b["profile_match_score"]
    assert score_b_initial < 65.0, f"Candidate B (Java dev) should have lower match score, got {score_b_initial}"
    assert data_eval_b["user_id"] == USER_B

    # Distinct scores guarantee
    assert abs(score_a_initial - score_b_initial) >= 20.0

    # -------------------------------------------------------------
    # Step 3: Candidate A retrieves the opportunity again
    # CRITICAL: Candidate A MUST see their own score and matches, NOT Candidate B's!
    # -------------------------------------------------------------
    resp_get_a = client.get(f"/api/opportunities/{opp_id}", headers=auth_headers(USER_A))
    assert resp_get_a.status_code == 200
    data_get_a = resp_get_a.json()

    assert data_get_a["profile_match_score"] == pytest.approx(score_a_initial, abs=0.1), (
        f"Candidate A got {data_get_a['profile_match_score']}, expected own score {score_a_initial}. "
        f"Possible overwrite by Candidate B (score {score_b_initial})!"
    )
    assert data_get_a["match_score"] == pytest.approx(score_a_initial, abs=0.1)
    # Candidate A's requirement matches must be populated, not wiped
    assert len(data_get_a["requirement_matches"]) > 0
    # Candidate A's match analysis must not contain Candidate B's data
    if data_get_a.get("match_analysis"):
        assert data_get_a["match_analysis"].get("user_id") == USER_A

    # -------------------------------------------------------------
    # Step 4: Candidate B retrieves the opportunity again
    # -------------------------------------------------------------
    resp_get_b = client.get(f"/api/opportunities/{opp_id}", headers=auth_headers(USER_B))
    assert resp_get_b.status_code == 200
    data_get_b = resp_get_b.json()

    assert data_get_b["profile_match_score"] == pytest.approx(score_b_initial, abs=0.1), (
        f"Candidate B got {data_get_b['profile_match_score']}, expected own score {score_b_initial}."
    )
    assert data_get_b["match_score"] == pytest.approx(score_b_initial, abs=0.1)
    if data_get_b.get("match_analysis"):
        assert data_get_b["match_analysis"].get("user_id") == USER_B

    # -------------------------------------------------------------
    # Step 5: Both candidates force-refresh their evaluations
    # -------------------------------------------------------------
    ref_a = client.post(
        f"/api/opportunities/{opp_id}/evaluate-match",
        headers=auth_headers(USER_A),
        json={"force_refresh": True, "use_ai": False}
    ).json()
    ref_b = client.post(
        f"/api/opportunities/{opp_id}/evaluate-match",
        headers=auth_headers(USER_B),
        json={"force_refresh": True, "use_ai": False}
    ).json()

    assert ref_a["profile_match_score"] == pytest.approx(score_a_initial, abs=0.1)
    assert ref_b["profile_match_score"] == pytest.approx(score_b_initial, abs=0.1)
    assert ref_a["user_id"] == USER_A
    assert ref_b["user_id"] == USER_B

    # -------------------------------------------------------------
    # Step 6: Both candidates update profiles and reevaluate
    # Candidate B learns Python! Candidate B's score should increase significantly.
    # Candidate A's score should NOT be affected.
    # -------------------------------------------------------------
    db = SessionLocal()
    cand_b_db = db.query(CandidateProfile).filter(CandidateProfile.user_id == USER_B).first()
    cand_b_db.skills = [
        {"name": "Java", "level": "expert", "category": "language"},
        {"name": "Python", "level": "intermediate", "category": "language"},
        {"name": "FastAPI", "level": "intermediate", "category": "framework"}
    ]
    cand_b_db.projects = [
        {"title": "FastAPI Microservice", "tech_stack": ["Python", "FastAPI"], "is_verified": True}
    ]
    db.commit()
    db.close()

    # Re-evaluate Candidate B without force_refresh (hash change should trigger recalculation)
    b_updated_eval = client.post(
        f"/api/opportunities/{opp_id}/evaluate-match",
        headers=auth_headers(USER_B),
        json={"force_refresh": False, "use_ai": False}
    ).json()
    assert b_updated_eval["profile_match_score"] > score_b_initial, (
        f"Candidate B score should increase after learning Python, was {score_b_initial}, now {b_updated_eval['profile_match_score']}"
    )

    # Candidate A gets their evaluation without force_refresh; should be served cached A score
    a_check = client.get(f"/api/opportunities/{opp_id}", headers=auth_headers(USER_A)).json()
    assert a_check["profile_match_score"] == pytest.approx(score_a_initial, abs=0.1)

    # -------------------------------------------------------------
    # Step 7: Opportunity description changes and both candidates reevaluate
    # Description adds Java requirement; both candidates should see invalidated cache
    # -------------------------------------------------------------
    db = SessionLocal()
    opp_db = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
    opp_db.description = (
        "We are looking for a Senior Polyglot Engineer.\n"
        "Requirements:\n"
        "- Strong proficiency in Python and Java (Mandatory)\n"
        "- Experience with Docker (Mandatory)\n"
    )
    db.commit()
    db.close()

    # Both re-evaluate without force_refresh (opportunity hash change should invalidate for BOTH candidates)
    a_new = client.post(
        f"/api/opportunities/{opp_id}/evaluate-match",
        headers=auth_headers(USER_A),
        json={"force_refresh": False, "use_ai": False}
    ).json()
    b_new = client.post(
        f"/api/opportunities/{opp_id}/evaluate-match",
        headers=auth_headers(USER_B),
        json={"force_refresh": False, "use_ai": False}
    ).json()

    assert a_new["user_id"] == USER_A
    assert b_new["user_id"] == USER_B
    # Both have valid updated evaluations
    assert a_new["profile_match_score"] > 0.0
    assert b_new["profile_match_score"] > 0.0


# -------------------------------------------------------------------------
# Phase 4: Cache Key and Invalidation Correctness
# -------------------------------------------------------------------------

def test_phase4_candidate_cache_invalidation_isolation(setup_candidates_and_public_opportunity):
    """
    Validates that updating Candidate A's profile only invalidates Candidate A's cache.
    Candidate B's cached result MUST remain intact with is_cached=True.
    """
    fixture = setup_candidates_and_public_opportunity
    opp_id = fixture["opp_id"]

    # Initial evaluation for both candidates
    eval_a = client.post(f"/api/opportunities/{opp_id}/evaluate-match", headers=auth_headers(USER_A), json={"force_refresh": True, "use_ai": False}).json()
    eval_b = client.post(f"/api/opportunities/{opp_id}/evaluate-match", headers=auth_headers(USER_B), json={"force_refresh": True, "use_ai": False}).json()

    # Verify Candidate B served from cache before profile change
    cached_b1 = client.post(f"/api/opportunities/{opp_id}/evaluate-match", headers=auth_headers(USER_B), json={"force_refresh": False, "use_ai": False}).json()
    assert cached_b1["is_cached"] is True

    # Mutate Candidate A's profile
    db = SessionLocal()
    cand_a = db.query(CandidateProfile).filter(CandidateProfile.user_id == USER_A).first()
    cand_a.skills = [{"name": "Python", "level": "advanced", "category": "language"}]
    db.commit()
    db.close()

    # Re-evaluate Candidate A: must be recalculated (is_cached=False)
    eval_a2 = client.post(f"/api/opportunities/{opp_id}/evaluate-match", headers=auth_headers(USER_A), json={"force_refresh": False, "use_ai": False}).json()
    assert eval_a2["is_cached"] is False

    # Check Candidate B: MUST STILL BE SERVED DIRECTLY FROM CACHE (is_cached=True)
    cached_b2 = client.post(f"/api/opportunities/{opp_id}/evaluate-match", headers=auth_headers(USER_B), json={"force_refresh": False, "use_ai": False}).json()
    assert cached_b2["is_cached"] is True
    assert cached_b2["profile_match_score"] == pytest.approx(eval_b["profile_match_score"], abs=0.1)


# -------------------------------------------------------------------------
# Phase 5: Concurrency and Race Conditions
# -------------------------------------------------------------------------

import concurrent.futures

def test_phase5_concurrent_evaluations_independent_candidates(setup_candidates_and_public_opportunity):
    """
    Validates that Candidate A and Candidate B evaluating the same public opportunity simultaneously
    in parallel threads execute without deadlocks, corruption, or cross-overwrites.
    """
    fixture = setup_candidates_and_public_opportunity
    opp_id = fixture["opp_id"]

    def evaluate_for_user(user_id):
        return client.post(
            f"/api/opportunities/{opp_id}/evaluate-match",
            headers=auth_headers(user_id),
            json={"force_refresh": True, "use_ai": False}
        ).json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(evaluate_for_user, USER_A)
        future_b = executor.submit(evaluate_for_user, USER_B)

        res_a = future_a.result()
        res_b = future_b.result()

    assert res_a["user_id"] == USER_A
    assert res_b["user_id"] == USER_B
    assert res_a["profile_match_score"] != res_b["profile_match_score"]

    # Verify persistent isolation in database
    from backend.app.models.candidate_opportunity_match import CandidateOpportunityMatch
    db = SessionLocal()
    matches = db.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.opportunity_id == opp_id).all()
    assert len(matches) == 2
    users_found = {m.user_id for m in matches}
    assert users_found == {USER_A, USER_B}
    db.close()


def test_phase5_concurrent_evaluations_same_candidate(setup_candidates_and_public_opportunity):
    """
    Validates that Candidate A sending concurrent evaluation requests serializes cleanly
    and produces exactly ONE database record in candidate_opportunity_matches.
    """
    fixture = setup_candidates_and_public_opportunity
    opp_id = fixture["opp_id"]

    def evaluate():
        return client.post(
            f"/api/opportunities/{opp_id}/evaluate-match",
            headers=auth_headers(USER_A),
            json={"force_refresh": True, "use_ai": False}
        ).status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(evaluate) for _ in range(3)]
        statuses = [f.result() for f in futures]

    assert all(s == 200 for s in statuses)

    from backend.app.models.candidate_opportunity_match import CandidateOpportunityMatch
    db = SessionLocal()
    cand_matches = (
        db.query(CandidateOpportunityMatch)
        .filter(
            CandidateOpportunityMatch.opportunity_id == opp_id,
            CandidateOpportunityMatch.user_id == USER_A
        )
        .all()
    )
    assert len(cand_matches) == 1, f"Expected exactly 1 persistent record, found {len(cand_matches)}"
    db.close()


def test_phase5_error_isolation_preserves_other_candidate_cache(setup_candidates_and_public_opportunity):
    """
    Validates that if an unexpected error occurs during Candidate B's evaluation,
    Candidate A's valid cached matching result remains completely uncorrupted and intact.
    """
    fixture = setup_candidates_and_public_opportunity
    opp_id = fixture["opp_id"]

    # Candidate A evaluates successfully
    res_a = client.post(f"/api/opportunities/{opp_id}/evaluate-match", headers=auth_headers(USER_A), json={"force_refresh": True, "use_ai": False}).json()
    score_a = res_a["profile_match_score"]

    # Candidate B evaluation encounters an artificial failure during calculation
    from unittest.mock import patch
    with patch("backend.app.services.matching.service.calculate_profile_match", side_effect=RuntimeError("Simulated Engine Flaw")):
        try:
            client.post(f"/api/opportunities/{opp_id}/evaluate-match", headers=auth_headers(USER_B), json={"force_refresh": True, "use_ai": False})
        except RuntimeError:
            pass  # Expected testclient server exception propagation

    # Candidate A retrieves result: MUST be 100% valid and unaffected by B's crash
    get_a = client.get(f"/api/opportunities/{opp_id}", headers=auth_headers(USER_A)).json()
    assert get_a["profile_match_score"] == pytest.approx(score_a, abs=0.1)
    assert len(get_a["requirement_matches"]) > 0


# -------------------------------------------------------------------------
# Phase 6: API Contract Validation
# -------------------------------------------------------------------------

def test_phase6_not_evaluated_candidate_receives_neutral_state(setup_candidates_and_public_opportunity):
    """
    Validates that a new Candidate C (who has not yet evaluated the public opportunity)
    receives a clean, neutral response with score 0.0 and empty matches, NEVER leaking
    Candidate A's or B's scores, matches, or raw match_analysis.
    """
    fixture = setup_candidates_and_public_opportunity
    opp_id = fixture["opp_id"]

    # Candidate A evaluates
    client.post(f"/api/opportunities/{opp_id}/evaluate-match", headers=auth_headers(USER_A), json={"force_refresh": True, "use_ai": False})

    USER_C = 99803
    db = SessionLocal()
    cand_c = CandidateProfile(user_id=USER_C, name="Charlie", email="charlie@test.com", skills=[])
    db.add(cand_c)
    db.commit()
    db.close()

    try:
        # Candidate C views opportunity before evaluating
        resp_c = client.get(f"/api/opportunities/{opp_id}", headers=auth_headers(USER_C))
        assert resp_c.status_code == 200
        data_c = resp_c.json()

        assert data_c["profile_match_score"] == 0.0
        assert data_c["match_score"] == 0.0
        assert data_c["requirement_matches"] == []
        assert data_c["skill_gaps"] == []
        assert data_c["match_analysis"] == {}
        assert "not yet been calculated" in data_c["scoring_explanation"]
        assert data_c["match_freshness"]["calculated_at"] is None
        assert data_c["match_freshness"]["is_cached"] is False

    finally:
        db = SessionLocal()
        db.query(CandidateProfile).filter(CandidateProfile.user_id == USER_C).delete()
        db.commit()
        db.close()


def test_phase6_client_payload_tampering_ignored(setup_candidates_and_public_opportunity):
    """
    Client attempting to inject user_id, candidate_id, or fake match score in request body
    is strictly ignored; server binds strictly to authenticated JWT user.
    """
    fixture = setup_candidates_and_public_opportunity
    opp_id = fixture["opp_id"]

    malicious_body = {
        "force_refresh": True,
        "user_id": USER_A,         # Bob attempts to impersonate Alice
        "candidate_id": 1,
        "profile_match_score": 100.0
    }
    resp = client.post(
        f"/api/opportunities/{opp_id}/evaluate-match",
        headers=auth_headers(USER_B),
        json=malicious_body
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == USER_B  # Server strictly bound to Bob

