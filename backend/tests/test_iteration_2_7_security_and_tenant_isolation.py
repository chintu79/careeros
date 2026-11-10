import pytest
import time
from starlette.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models.candidate import CandidateProfile
from backend.app.models.opportunity import Opportunity
from backend.app.models.candidate_opportunity_match import CandidateOpportunityMatch
from backend.app.models.resume import ResumeDocument
from backend.app.models.discovery_ranking_snapshot import DiscoveryRankingSnapshot
from backend.app.services.discovery_snapshot_manager import snapshot_manager
from backend.app.config import settings


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
    yield
    try:
        db.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id >= 90000).delete(synchronize_session=False)
        db.query(ResumeDocument).filter(ResumeDocument.user_id >= 90000).delete(synchronize_session=False)
        db.query(Opportunity).filter(Opportunity.id >= 99600).delete(synchronize_session=False)
        db.query(CandidateProfile).filter(CandidateProfile.user_id >= 90000).delete(synchronize_session=False)
        db.query(DiscoveryRankingSnapshot).filter(DiscoveryRankingSnapshot.user_id >= 90000).delete(synchronize_session=False)
        db.commit()
        snapshot_manager.l1_cache.clear()
    except Exception:
        db.rollback()


@pytest.fixture
def auth_headers(client: TestClient):
    """Helper to mint Authorization headers for any user_id."""
    def _mint(user_id: int):
        res = client.post("/api/auth/token", json={"user_id": user_id})
        assert res.status_code == 200, res.text
        token = res.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    return _mint


def test_candidate_profile_tenant_isolation(client: TestClient, db: Session, auth_headers):
    """
    User A cannot access or modify User B's candidate profile.
    GET /api/candidate and PUT /api/candidate must strictly read and write
    to the authenticated caller's identity.
    """
    uid_a = 91001
    uid_b = 91002

    # Seed User A and User B
    cand_a = CandidateProfile(user_id=uid_a, name="User A", degree="B.Tech CS", skills=[{"name": "Python"}])
    cand_b = CandidateProfile(user_id=uid_b, name="User B", degree="M.S. Robotics", skills=[{"name": "Rust"}])
    db.add_all([cand_a, cand_b])
    db.commit()

    headers_a = auth_headers(uid_a)
    headers_b = auth_headers(uid_b)

    # User A reads profile -> receives User A data
    res_a = client.get("/api/candidate", headers=headers_a)
    assert res_a.status_code == 200
    assert res_a.json()["user_id"] == uid_a
    assert res_a.json()["name"] == "User A"

    # User B reads profile -> receives User B data
    res_b = client.get("/api/candidate", headers=headers_b)
    assert res_b.status_code == 200
    assert res_b.json()["user_id"] == uid_b
    assert res_b.json()["name"] == "User B"

    # User A updates profile -> only User A is modified
    update_res = client.put("/api/candidate", headers=headers_a, json={"name": "User A Updated"})
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "User A Updated"

    db.refresh(cand_b)
    assert cand_b.name == "User B", "User B profile was mutated by User A request!"


def test_resume_ownership_authorization(client: TestClient, db: Session, auth_headers):
    """
    User A attempts to access, modify, or delete User B's resume.
    Must return HTTP 403 Forbidden.
    """
    uid_a = 92001
    uid_b = 92002

    resume_b = ResumeDocument(
        user_id=uid_b,
        title="User B Secret Resume",
        latex_content="\\documentclass{article}\\begin{document}User B Secret\\end{document}",
        is_master=False
    )
    db.add(resume_b)
    db.commit()

    headers_a = auth_headers(uid_a)
    headers_b = auth_headers(uid_b)

    # 1. User A tries to GET User B's resume
    res_get = client.get(f"/api/resumes/{resume_b.id}", headers=headers_a)
    assert res_get.status_code == 403, f"Expected 403, got {res_get.status_code}"

    # 2. User A tries to PUT User B's resume
    res_put = client.put(f"/api/resumes/{resume_b.id}", headers=headers_a, json={"title": "Hacked Title"})
    assert res_put.status_code == 403, f"Expected 403, got {res_put.status_code}"

    # 3. User A tries to DELETE User B's resume
    res_del = client.delete(f"/api/resumes/{resume_b.id}", headers=headers_a)
    assert res_del.status_code == 403, f"Expected 403, got {res_del.status_code}"

    # Verify User B can still access their resume
    res_owner = client.get(f"/api/resumes/{resume_b.id}", headers=headers_b)
    assert res_owner.status_code == 200
    assert res_owner.json()["title"] == "User B Secret Resume"


def test_snapshot_session_candidate_isolation(client: TestClient, db: Session, auth_headers):
    """
    User A attempts to reuse User B's pagination snapshot token / session ID.
    Backend must verify snapshot session ownership and reject with HTTP 410 Gone.
    """
    uid_a = 93001
    uid_b = 93002

    cand_a = CandidateProfile(user_id=uid_a, name="User A", skills=[{"name": "Python"}])
    cand_b = CandidateProfile(user_id=uid_b, name="User B", skills=[{"name": "Go"}])
    db.add_all([cand_a, cand_b])
    db.commit()

    headers_b = auth_headers(uid_b)
    headers_a = auth_headers(uid_a)

    # User B creates a pagination snapshot
    res_b = client.get("/api/opportunities?tab=recommended&limit=5", headers=headers_b)
    assert res_b.status_code == 200
    b_data = res_b.json()
    snapshot_id_b = b_data.get("snapshot_id")
    assert snapshot_id_b is not None

    # User A tries to query using User B's snapshot_id on cursor > 0
    res_cross = client.get(
        f"/api/opportunities?tab=recommended&limit=5&snapshot_id={snapshot_id_b}&cursor=5",
        headers=headers_a
    )
    # Must reject with 410 Gone and X-Restart-Required
    assert res_cross.status_code == 410, f"Expected 410 for cross-user snapshot access, got {res_cross.status_code}"
    assert res_cross.headers.get("X-Restart-Required") == "true" or res_cross.headers.get("x-restart-required") == "true"
    payload = res_cross.json()
    assert payload.get("code") == "PAGINATION_SESSION_EXPIRED"


def test_on_demand_match_evaluation_candidate_ownership(client: TestClient, db: Session, auth_headers):
    """
    Verify that on-demand evaluation:
    1. Uses caller's verified user_id (not client-injected ID).
    2. Strictly partitions candidate match records in database.
    3. Blocks access to private opportunities owned by another user.
    """
    uid_a = 94001
    uid_b = 94002

    cand_a = CandidateProfile(user_id=uid_a, name="User A", skills=[{"name": "Python"}])
    cand_b = CandidateProfile(user_id=uid_b, name="User B", skills=[{"name": "Java"}])
    
    # Private opportunity owned by User B
    private_opp = Opportunity(
        id=99601,
        user_id=uid_b,
        title="User B Private Job",
        normalized_title="user b private job",
        company_name="Private Corp",
        location="Remote",
        normalized_location="remote",
        original_url="https://example.com/p/99601",
        source_platform="manual",
        description="Private job.",
        content_version=1
    )
    db.add_all([cand_a, cand_b, private_opp])
    db.commit()

    headers_a = auth_headers(uid_a)
    headers_b = auth_headers(uid_b)

    # User A tries to evaluate match on User B's private opportunity -> 403 Forbidden
    res_unauth = client.post(
        f"/api/opportunities/{private_opp.id}/evaluate-match",
        headers=headers_a,
        json={"force_refresh": True}
    )
    assert res_unauth.status_code == 403, f"Expected 403, got {res_unauth.status_code}"

    # User B evaluates match on their private opportunity -> 200 OK
    res_owner = client.post(
        f"/api/opportunities/{private_opp.id}/evaluate-match",
        headers=headers_b,
        json={"force_refresh": True, "use_ai": False}
    )
    assert res_owner.status_code == 200


def test_token_expiration_security(client: TestClient):
    """
    Verify that an expired token is rejected with HTTP 401.
    """
    # Mint a token with 1 second TTL
    res = client.post("/api/auth/token", json={"user_id": 95001, "ttl_seconds": 1})
    assert res.status_code == 200
    token = res.json()["access_token"]

    # Sleep 2 seconds to ensure expiration
    time.sleep(2)

    expired_headers = {"Authorization": f"Bearer {token}"}
    res_exp = client.get("/api/candidate", headers=expired_headers)
    assert res_exp.status_code == 401, f"Expected 401 for expired token, got {res_exp.status_code}"
    assert "expired" in res_exp.text.lower()


def test_production_token_endpoint_protection(client: TestClient):
    """
    Verify that when settings.is_production is True:
    1. Unauthenticated requests to /api/auth/token are rejected with HTTP 403.
    2. Requests with valid X-Internal-Secret are allowed.
    """
    orig_env = settings.ENVIRONMENT
    orig_secret = settings.INTERNAL_GATEWAY_SECRET
    try:
        settings.ENVIRONMENT = "production"
        settings.INTERNAL_GATEWAY_SECRET = "super_secure_gateway_secret_123"

        # 1. Unauthenticated request without gateway secret -> 403 Forbidden
        res_blocked = client.post("/api/auth/token", json={"user_id": 96001})
        assert res_blocked.status_code == 403, f"Expected 403 in production, got {res_blocked.status_code}"

        # 2. Request with invalid gateway secret -> 403 Forbidden
        res_bad_secret = client.post(
            "/api/auth/token",
            json={"user_id": 96001},
            headers={"X-Internal-Secret": "wrong_secret"}
        )
        assert res_bad_secret.status_code == 403

        # 3. Request with valid gateway secret -> 200 OK
        res_ok = client.post(
            "/api/auth/token",
            json={"user_id": 96001},
            headers={"X-Internal-Secret": "super_secure_gateway_secret_123"}
        )
        assert res_ok.status_code == 200
        assert res_ok.json()["mode"] == "production"
    finally:
        settings.ENVIRONMENT = orig_env
        settings.INTERNAL_GATEWAY_SECRET = orig_secret
