"""
CareerOS — Iteration 2.6 Frontend Integration & Production Discovery Experience Tests

Verifies:
1. Authenticated session issuance and Bearer token verification.
2. Discovery API contract: cursor-based pagination, snapshot_id, next_cursor, has_more.
3. HTTP 410 session expiration error envelope and X-Restart-Required header.
4. Multi-tenant candidate isolation in discovery and matching (Candidate 1 vs Candidate 2).
5. On-demand deterministic matching intelligence calculation.
6. Mutation and lifecycle state consistency (save, dismiss, undismiss).
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models.opportunity import Opportunity
from backend.app.models.candidate import CandidateProfile
from backend.app.models.candidate_opportunity_match import CandidateOpportunityMatch
from backend.app.services.discovery_snapshot_manager import snapshot_manager


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def clean_test_fixtures(db: Session):
    def _cleanup():
        snapshot_manager.clear_all(db)
        try:
            db.query(CandidateOpportunityMatch).filter(
                (CandidateOpportunityMatch.opportunity_id >= 99500) |
                (CandidateOpportunityMatch.user_id == 88888)
            ).delete()
            db.query(Opportunity).filter(Opportunity.id >= 99500).delete()
            db.query(CandidateProfile).filter(CandidateProfile.user_id == 88888).delete()
            db.commit()
        except Exception:
            db.rollback()

    _cleanup()
    yield
    _cleanup()


def test_authenticated_token_issuance_and_security(client: TestClient):
    """Verify developmental token minting and input validation for candidates."""
    # 1. Valid user 1 (Candidate One)
    res1 = client.post("/api/auth/token", json={"user_id": 1})
    assert res1.status_code == 200, res1.text
    data1 = res1.json()
    assert "access_token" in data1
    assert data1["user_id"] == 1
    assert data1["token_type"].lower() == "bearer"

    # 2. Valid user 2 (Candidate B / Demo)
    res2 = client.post("/api/auth/token", json={"user_id": 2})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["access_token"] != data1["access_token"]
    assert data2["user_id"] == 2

    # 3. Validation rejection on zero or negative IDs
    res_zero = client.post("/api/auth/token", json={"user_id": 0})
    assert res_zero.status_code == 422

    res_neg = client.post("/api/auth/token", json={"user_id": -99})
    assert res_neg.status_code == 422


def test_discovery_search_and_cursor_pagination_contract(client: TestClient, db: Session):
    """
    Verify discovery search endpoint contract:
    - Returns snapshot_id, next_cursor, has_more, items
    - Items include ranking_reasons, match_score, category_scores, skill_gaps
    - Next cursor request preserves snapshot stability
    """
    # Mint token for user 1
    auth_res = client.post("/api/auth/token", json={"user_id": 1})
    token = auth_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Request first page with limit=3
    res1 = client.get("/api/opportunities?tab=recommended&limit=3", headers=headers)
    assert res1.status_code == 200, res1.text
    data1 = res1.json()

    assert "total" in data1
    assert "items" in data1
    assert "snapshot_id" in data1
    assert "has_more" in data1
    assert len(data1["items"]) <= 3

    if data1["items"]:
        item = data1["items"][0]
        assert "id" in item
        assert "title" in item
        assert "company_name" in item
        assert "match_score" in item
        assert "ranking_reasons" in item
        assert "category_scores" in item
        assert "skill_gaps" in item
        assert "eligibility_status" in item
        assert "content_version" in item

    # If catalogue has enough items, verify second cursor page
    if data1.get("has_more") and data1.get("next_cursor") is not None:
        snap_id = data1["snapshot_id"]
        cursor = data1["next_cursor"]

        res2 = client.get(
            f"/api/opportunities?tab=recommended&limit=3&snapshot_id={snap_id}&cursor={cursor}",
            headers=headers
        )
        assert res2.status_code == 200, res2.text
        data2 = res2.json()

        page1_ids = [item["id"] for item in data1["items"]]
        page2_ids = [item["id"] for item in data2["items"]]

        # Page 2 items must not overlap with Page 1 items
        assert set(page1_ids).isdisjoint(set(page2_ids)), "Cursor pagination returned duplicate items across pages"


def test_http_410_pagination_session_expired_envelope(client: TestClient):
    """
    Verify that an invalidated or expired snapshot_id triggers HTTP 410 Gone
    with X-Restart-Required header and PAGINATION_SESSION_EXPIRED code.
    """
    auth_res = client.post("/api/auth/token", json={"user_id": 1})
    token = auth_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Query with nonexistent snapshot_id and a nonzero cursor
    res = client.get(
        "/api/opportunities?tab=recommended&limit=5&snapshot_id=definitely_expired_snap_99999&cursor=5",
        headers=headers
    )

    assert res.status_code == 410, f"Expected 410 Gone, got {res.status_code}"
    assert res.headers.get("X-Restart-Required") == "true" or res.headers.get("x-restart-required") == "true"
    payload = res.json()
    assert payload.get("code") == "PAGINATION_SESSION_EXPIRED"
    assert payload.get("restart_required") is True


def test_candidate_tenant_isolation_in_discovery_and_matching(client: TestClient, db: Session):
    """
    Verify strict candidate tenant isolation:
    User 1 (Candidate One) and User 88888 (isolated demo candidate)
    receive independent evaluation results for the same opportunity.
    """
    # 1. Setup Candidate 88888 with different skills
    cand2 = CandidateProfile(
        user_id=88888,
        name="Candidate Isolation Test",
        skills=[{"name": "Rust"}, {"name": "Solidity"}],
        evidence_version=1
    )
    db.add(cand2)

    # 2. Setup a Python/PostgreSQL test opportunity
    opp = Opportunity(
        id=99501,
        title="Senior Python Platform Intern",
        normalized_title="senior python platform intern",
        company_name="Isolated Systems Inc",
        location="Remote",
        normalized_location="Remote",
        workplace_type="remote",
        employment_type="internship",
        status="verified",
        original_url="https://example.com/jobs/99501",
        source_platform="linkedin",
        description="Requires expert Python, FastAPI, and PostgreSQL database internals.",
        required_skills=["Python", "FastAPI", "PostgreSQL"],
        extracted_data={"mandatory_technical_skills": ["Python", "FastAPI", "PostgreSQL"]},
        content_version=1
    )
    db.add(opp)
    db.commit()

    # 3. Mint tokens for User 1 and User 88888
    tok1 = client.post("/api/auth/token", json={"user_id": 1}).json()["access_token"]
    tok2 = client.post("/api/auth/token", json={"user_id": 88888}).json()["access_token"]

    # 4. On-demand evaluate for User 1
    eval1 = client.post(
        f"/api/opportunities/{opp.id}/evaluate-match",
        headers={"Authorization": f"Bearer {tok1}"},
        json={"force_refresh": True, "use_ai": False}
    )
    assert eval1.status_code == 200, eval1.text
    score1 = eval1.json()["profile_match_score"]

    # 5. On-demand evaluate for User 88888
    eval2 = client.post(
        f"/api/opportunities/{opp.id}/evaluate-match",
        headers={"Authorization": f"Bearer {tok2}"},
        json={"force_refresh": True, "use_ai": False}
    )
    assert eval2.status_code == 200, eval2.text
    score2 = eval2.json()["profile_match_score"]

    # Candidate 1 (Python, FastAPI, 7 projects) should have a significantly higher score than Candidate 88888 (Rust, Solidity)
    assert score1 > score2, f"Expected Candidate 1 score ({score1}) to exceed Candidate 88888 score ({score2})"

    # 6. Verify database records are strictly isolated by user_id
    m1 = db.query(CandidateOpportunityMatch).filter_by(opportunity_id=opp.id, user_id=1).first()
    m2 = db.query(CandidateOpportunityMatch).filter_by(opportunity_id=opp.id, user_id=88888).first()

    assert m1 is not None
    assert m2 is not None
    assert m1.user_id == 1
    assert m2.user_id == 88888
    assert m1.match_score == score1
    assert m2.match_score == score2


def test_opportunity_lifecycle_actions(client: TestClient, db: Session):
    """Verify save, dismiss, and undismiss lifecycle transitions."""
    tok = client.post("/api/auth/token", json={"user_id": 1}).json()["access_token"]
    headers = {"Authorization": f"Bearer {tok}"}

    opp = Opportunity(
        id=99502,
        title="Lifecycle Test Intern",
        normalized_title="lifecycle test intern",
        company_name="Lifecycle Corp",
        location="Remote",
        workplace_type="remote",
        employment_type="internship",
        status="verified",
        original_url="https://example.com/jobs/99502",
        source_platform="linkedin",
        description="Testing lifecycle persistence.",
        content_version=1,
        is_saved=False,
        is_dismissed=False
    )
    db.add(opp)
    db.commit()

    # 1. Toggle save
    save_res = client.post(f"/api/opportunities/{opp.id}/save", headers=headers)
    assert save_res.status_code == 200
    assert save_res.json()["is_saved"] is True

    # 2. Dismiss
    dismiss_res = client.post(f"/api/opportunities/{opp.id}/dismiss", headers=headers)
    assert dismiss_res.status_code == 200
    assert dismiss_res.json()["is_dismissed"] is True

    # 3. Undismiss
    undismiss_res = client.post(f"/api/opportunities/{opp.id}/undismiss", headers=headers)
    assert undismiss_res.status_code == 200
    assert undismiss_res.json()["is_dismissed"] is False
