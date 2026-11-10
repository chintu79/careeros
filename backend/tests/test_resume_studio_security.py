import os
import uuid
import random
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.config import settings
from backend.app.database import SessionLocal
from backend.app.core.auth import create_access_token
from backend.app.models.candidate import CandidateProfile
from backend.app.models.opportunity import Opportunity
from backend.app.models.resume import ResumeDocument

client = TestClient(app)


def auth_headers(user_id: int) -> dict:
    token = create_access_token(user_id=user_id)
    return {"Authorization": f"Bearer {token}"}


# =========================================================================
# Security Test 1: Missing authentication is strictly rejected with HTTP 401 in strict mode
# =========================================================================
def test_missing_authentication_rejected_401():
    # Attempting to access private resume studio routes without credentials in strict mode
    with patch.object(settings, "AUTH_REQUIRED", True):
        res = client.get("/api/resumes")
        assert res.status_code == 401
        assert "Authentication required" in res.json()["detail"]

        res_master = client.get("/api/resumes/master")
        assert res_master.status_code == 401
        assert "Authentication required" in res_master.json()["detail"]

        res_cand = client.get("/api/candidate")
        assert res_cand.status_code == 401
        assert "Authentication required" in res_cand.json()["detail"]


# =========================================================================
# Security Test 2: Invalid or forged authentication token is rejected with HTTP 401
# =========================================================================
def test_invalid_bearer_token_rejected_401():
    # Random corrupted token
    res = client.get("/api/resumes", headers={"Authorization": "Bearer forged.token.payload"})
    assert res.status_code == 401
    assert "Authentication failed" in res.json()["detail"]

    # Tampered signature
    valid_token = create_access_token(user_id=101)
    parts = valid_token.split(".")
    tampered_token = f"{parts[0]}.{parts[1]}.tamperedsignature"
    res_tampered = client.get("/api/resumes", headers={"Authorization": f"Bearer {tampered_token}"})
    assert res_tampered.status_code == 401
    assert "Authentication failed" in res_tampered.json()["detail"]


# =========================================================================
# Security Test 3: Untrusted client directly injecting X-User-Id is rejected with HTTP 401
# =========================================================================
def test_untrusted_client_x_user_id_spoofing_rejected_401():
    # Client passes X-User-Id: 2 directly without trusted internal gateway secret
    res = client.get("/api/resumes", headers={"X-User-Id": "2"})
    assert res.status_code == 401
    assert "Untrusted client identity" in res.json()["detail"]

    # Client tries to tailor resume using forged X-User-Id
    res_tailor = client.post("/api/resumes/tailor", json={"opportunity_id": 1}, headers={"X-User-Id": "2"})
    assert res_tailor.status_code == 401
    assert "Untrusted client identity" in res_tailor.json()["detail"]


# =========================================================================
# Security Test 4: Trusted internal gateway secret allows verified X-User-Id forwarding
# =========================================================================
def test_trusted_internal_gateway_secret_accepted():
    original_secret = settings.INTERNAL_GATEWAY_SECRET
    try:
        # Simulate configured internal gateway secret
        settings.INTERNAL_GATEWAY_SECRET = "verified-internal-proxy-secret-999"
        gateway_headers = {
            "X-User-Id": "7771",
            "X-Internal-Secret": "verified-internal-proxy-secret-999"
        }
        res = client.get("/api/resumes", headers=gateway_headers)
        # Should authenticate successfully (not 401)
        assert res.status_code == 200
        assert "items" in res.json()
    finally:
        settings.INTERNAL_GATEWAY_SECRET = original_secret


# =========================================================================
# Security Test 5: A user cannot access, modify, or delete another user's resume (HTTP 403)
# =========================================================================
def test_user_cannot_access_or_modify_other_user_resume_403():
    db = SessionLocal()
    try:
        user_a = random.randint(100000, 499999)
        user_b = random.randint(500000, 999999)

        resume_a = ResumeDocument(
            user_id=user_a,
            title="User A Confidential Resume",
            template_id="minimal_professional",
            latex_content=r"\documentclass{article}\begin{document}Private Resume A\end{document}",
            version=1
        )
        db.add(resume_a)
        db.commit()
        r_id = resume_a.id

        # User B attempts to read User A's resume
        res_get = client.get(f"/api/resumes/{r_id}", headers=auth_headers(user_b))
        assert res_get.status_code == 403
        assert "Forbidden" in res_get.json()["detail"]

        # User B attempts to update User A's resume
        res_put = client.put(f"/api/resumes/{r_id}", json={"title": "Hacked"}, headers=auth_headers(user_b))
        assert res_put.status_code == 403

        # User B attempts to compile User A's resume
        res_compile = client.post(f"/api/resumes/{r_id}/compile", headers=auth_headers(user_b))
        assert res_compile.status_code == 403

        # User B attempts to delete User A's resume
        res_del = client.delete(f"/api/resumes/{r_id}", headers=auth_headers(user_b))
        assert res_del.status_code == 403
    finally:
        db.close()


# =========================================================================
# Security Test 6: A user cannot view or modify another user's candidate profile
# =========================================================================
def test_user_cannot_modify_other_user_candidate_profile_403():
    db = SessionLocal()
    try:
        user_a = random.randint(100000, 499999)
        user_b = random.randint(500000, 999999)

        cand_a = CandidateProfile(user_id=user_a, name="Candidate Alpha", degree="B.Tech CS")
        cand_b = CandidateProfile(user_id=user_b, name="Candidate Beta", degree="M.S. Data Science")
        db.add_all([cand_a, cand_b])
        db.commit()

        # User B reads their own profile -> gets Candidate Beta, never Candidate Alpha
        res_b = client.get("/api/candidate", headers=auth_headers(user_b))
        assert res_b.status_code == 200
        assert res_b.json()["name"] == "Candidate Beta"
        assert res_b.json()["user_id"] == user_b

        # User B updates their profile -> only updates Candidate Beta
        res_update = client.put("/api/candidate", json={"name": "Candidate Beta Updated"}, headers=auth_headers(user_b))
        assert res_update.status_code == 200
        assert res_update.json()["name"] == "Candidate Beta Updated"

        # Verify Candidate Alpha is untouched
        db.refresh(cand_a)
        assert cand_a.name == "Candidate Alpha"
    finally:
        db.close()


# =========================================================================
# Security Test 7: A user cannot tailor a resume using an unauthorized private opportunity (HTTP 403)
# =========================================================================
def test_user_cannot_tailor_resume_using_unauthorized_private_opportunity_403():
    db = SessionLocal()
    try:
        user_a = random.randint(100000, 499999)
        user_b = random.randint(500000, 999999)

        cand_b = CandidateProfile(user_id=user_b, name="User B Candidate")
        opp_a = Opportunity(
            user_id=user_a, # Private to User A
            title="Private Executive Role",
            normalized_title="private executive role",
            company_name="Secret Stealth",
            original_url=f"https://stealth.example.com/{uuid.uuid4()}",
            source_platform="direct"
        )
        db.add_all([cand_b, opp_a])
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
# Security Test 8: Anonymous requests cannot access private resume data
# =========================================================================
def test_anonymous_requests_cannot_access_private_resume_data_401():
    db = SessionLocal()
    try:
        user_a = random.randint(100000, 499999)
        resume_a = ResumeDocument(
            user_id=user_a,
            title="Confidential Resume",
            template_id="minimal_professional",
            latex_content=r"\documentclass{article}\begin{document}Private\end{document}",
            version=1
        )
        db.add(resume_a)
        db.commit()
        r_id = resume_a.id

        with patch.object(settings, "AUTH_REQUIRED", True):
            # Anonymous GET in strict mode
            assert client.get(f"/api/resumes/{r_id}").status_code == 401
            # Anonymous PDF download in strict mode
            assert client.get(f"/api/resumes/{r_id}/pdf").status_code == 401
            # Anonymous versions in strict mode
            assert client.get(f"/api/resumes/{r_id}/versions").status_code == 401
            # Anonymous optimize in strict mode
            assert client.post(f"/api/resumes/{r_id}/optimize", json={"opportunity_id": 1}).status_code == 401

        with patch.object(settings, "AUTH_REQUIRED", False):
            # In local mode, requesting other user's private data is blocked with 403 Forbidden
            assert client.get(f"/api/resumes/{r_id}").status_code == 403
    finally:
        db.close()


# =========================================================================
# Security Test 9: Local companion mode allows unauthenticated frontend access (HTTP 200)
# =========================================================================
def test_local_companion_mode_allows_unauthenticated_frontend_access():
    """Verify that in local companion mode (AUTH_REQUIRED=False), the frontend can fetch resumes and candidate profile."""
    with patch.object(settings, "AUTH_REQUIRED", False):
        res = client.get("/api/resumes?page_size=50")
        assert res.status_code == 200
        data = res.json()
        assert "items" in data

        res_cand = client.get("/api/candidate")
        assert res_cand.status_code == 200
        cand_data = res_cand.json()
        assert cand_data["user_id"] == 1


# =========================================================================
# Security Test 9: Existing authenticated workflows continue working (HTTP 200)
# =========================================================================
def test_authenticated_workflows_continue_working():
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)

    # 1. Master resume initialization
    res_master = client.get("/api/resumes/master", headers=headers)
    assert res_master.status_code == 200
    data = res_master.json()
    assert data["user_id"] == user_id
    assert data["is_master"] is True

    # 2. List resumes
    res_list = client.get("/api/resumes", headers=headers)
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 1

    # 3. Candidate profile access
    res_cand = client.get("/api/candidate", headers=headers)
    assert res_cand.status_code == 200
    assert res_cand.json()["user_id"] == user_id


# =========================================================================
# Security Test 11: Unauthorized PDF downloads are strictly rejected (HTTP 403/401)
# =========================================================================
def test_unauthorized_pdf_downloads_rejected():
    db = SessionLocal()
    try:
        user_a = random.randint(100000, 499999)
        user_b = random.randint(500000, 999999)

        resume_a = ResumeDocument(
            user_id=user_a,
            title="User A Downloadable Resume",
            template_id="minimal_professional",
            latex_content=r"\documentclass{article}\begin{document}Private\end{document}",
            version=1
        )
        db.add(resume_a)
        db.commit()
        r_id = resume_a.id

        # Cross-user PDF preview request is rejected with 403 Forbidden
        res_pdf = client.get(f"/api/resumes/{r_id}/pdf", headers=auth_headers(user_b))
        assert res_pdf.status_code == 403
        assert "Forbidden" in res_pdf.json()["detail"]

        # Cross-user PDF download request is rejected with 403 Forbidden
        res_dl = client.get(f"/api/resumes/{r_id}/download", headers=auth_headers(user_b))
        assert res_dl.status_code == 403
        assert "Forbidden" in res_dl.json()["detail"]
    finally:
        db.close()


# =========================================================================
# Security Test 12: Unauthorized version restoration is rejected (HTTP 403)
# =========================================================================
def test_unauthorized_version_restoration_rejected():
    db = SessionLocal()
    try:
        user_a = random.randint(100000, 499999)
        user_b = random.randint(500000, 999999)

        resume_a = ResumeDocument(
            user_id=user_a,
            title="User A Versioned Resume",
            template_id="minimal_professional",
            latex_content=r"\documentclass{article}\begin{document}Original\end{document}",
            version=2
        )
        db.add(resume_a)
        db.commit()

        from backend.app.models.resume_version import ResumeVersion
        v1 = ResumeVersion(
            resume_id=resume_a.id,
            version_number=1,
            title="User A Version 1",
            template_id="minimal_professional",
            latex_content=r"\documentclass{article}\begin{document}V1\end{document}",
            change_summary="Initial version"
        )
        db.add(v1)
        db.commit()

        # User B attempts to restore User A's version snapshot
        res_restore = client.post(
            f"/api/resumes/{resume_a.id}/versions/{v1.id}/restore",
            headers=auth_headers(user_b)
        )
        assert res_restore.status_code == 403
        assert "Forbidden" in res_restore.json()["detail"]
    finally:
        db.close()


# =========================================================================
# Security Test 13: Cross-user application-resume associations are rejected (HTTP 403)
# =========================================================================
def test_cross_user_application_resume_association_rejected():
    db = SessionLocal()
    try:
        user_a = random.randint(100000, 499999)
        user_b = random.randint(500000, 999999)

        resume_a = ResumeDocument(
            user_id=user_a,
            title="User A Confidential Resume",
            template_id="minimal_professional",
            latex_content=r"\documentclass{article}\begin{document}Confidential\end{document}",
            version=1
        )
        opp = Opportunity(
            title="Open Application Role",
            normalized_title="open application role",
            company_name="Universal Tech",
            original_url=f"https://example.com/jobs/{uuid.uuid4()}",
            source_platform="direct"
        )
        db.add_all([resume_a, opp])
        db.commit()

        # User B attempts to submit an application referencing User A's private resume
        payload = {
            "opportunity_id": opp.id,
            "resume_id": resume_a.id,
            "submission_mode": "assisted"
        }
        res = client.post("/api/applications/submit-assisted", json=payload, headers=auth_headers(user_b))
        assert res.status_code == 403
        assert "Forbidden" in res.json()["detail"]
    finally:
        db.close()

