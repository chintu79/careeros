import os
import time
import json
import random
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.config import settings
from backend.app.core.auth import (
    create_access_token, 
    verify_access_token, 
    _b64_encode, 
    _b64_decode,
    TOKEN_PREFIX
)

client = TestClient(app)


def auth_headers(user_id: int) -> dict:
    token = create_access_token(user_id=user_id)
    return {"Authorization": f"Bearer {token}"}


# =========================================================================
# Security Test 1: Arbitrary user IDs cannot be used to mint authenticated tokens
# =========================================================================
def test_arbitrary_user_ids_cannot_be_used_to_mint_authenticated_tokens():
    """In production, unauthenticated callers cannot mint tokens for arbitrary user IDs."""
    with patch.object(settings, "ENVIRONMENT", "production"):
        # Attempt to mint token for arbitrary target user_id=999
        res = client.post("/api/auth/token", json={"user_id": 999})
        assert res.status_code == 403
        assert "Arbitrary token minting is disabled in production" in res.json()["detail"]

    # Even in development mode, invalid / negative / non-integer user IDs are rejected
    res_zero = client.post("/api/auth/token", json={"user_id": 0})
    assert res_zero.status_code == 422

    res_neg = client.post("/api/auth/token", json={"user_id": -5})
    assert res_neg.status_code == 422


# =========================================================================
# Security Test 2: Unauthenticated production callers cannot mint tokens
# =========================================================================
def test_unauthenticated_production_callers_cannot_mint_tokens():
    """Production mode strictly blocks unauthenticated token minting."""
    with patch.object(settings, "ENVIRONMENT", "production"):
        # Without headers
        res = client.post("/api/auth/token", json={})
        assert res.status_code == 403

        # With untrusted headers
        res_fake = client.post(
            "/api/auth/token", 
            json={"user_id": 1}, 
            headers={"X-Internal-Secret": "forged-secret-123"}
        )
        assert res_fake.status_code == 403


# =========================================================================
# Security Test 3: Invalid signatures are rejected
# =========================================================================
def test_invalid_signatures_are_rejected():
    """Tokens with altered, invalid, or mismatched signatures return HTTP 401."""
    valid_token = create_access_token(user_id=123)
    parts = valid_token.split(".")

    # Tampered signature
    tampered_sig = f"{parts[0]}.{parts[1]}.bad_signature_here"
    res = client.get("/api/resumes", headers={"Authorization": f"Bearer {tampered_sig}"})
    assert res.status_code == 401
    assert "Cryptographic signature mismatch" in res.json()["detail"]

    # Token signed with a different key
    original_secret = settings.SECRET_KEY
    try:
        settings.SECRET_KEY = "another-completely-different-signing-key-999"
        foreign_token = create_access_token(user_id=123)
    finally:
        settings.SECRET_KEY = original_secret

    res_foreign = client.get("/api/resumes", headers={"Authorization": f"Bearer {foreign_token}"})
    assert res_foreign.status_code == 401
    assert "Cryptographic signature mismatch" in res_foreign.json()["detail"]


# =========================================================================
# Security Test 4: Modified token payloads are rejected
# =========================================================================
def test_modified_token_payloads_are_rejected():
    """Tampering with claims inside the payload breaks HMAC verification and returns HTTP 401."""
    # Mint token for user 105
    valid_token = create_access_token(user_id=105)
    parts = valid_token.split(".")

    # Decode payload, modify user_id to 1 (admin / victim), re-encode without updating signature
    payload = json.loads(_b64_decode(parts[1]).decode("utf-8"))
    payload["user_id"] = 1
    payload["sub"] = "1"
    tampered_payload_b64 = _b64_encode(json.dumps(payload).encode("utf-8"))

    tampered_token = f"{parts[0]}.{tampered_payload_b64}.{parts[2]}"
    res = client.get("/api/resumes", headers={"Authorization": f"Bearer {tampered_token}"})
    assert res.status_code == 401
    assert "Cryptographic signature mismatch" in res.json()["detail"]


# =========================================================================
# Security Test 5: Expired tokens are rejected
# =========================================================================
def test_expired_tokens_are_rejected():
    """Tokens with an expiration timestamp in the past return HTTP 401."""
    # Mint a token expired 10 seconds ago
    expired_token = create_access_token(user_id=105, ttl_seconds=-10)

    res = client.get("/api/resumes", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401
    assert "Token has expired" in res.json()["detail"]


# =========================================================================
# Security Test 6: Malformed tokens are rejected
# =========================================================================
def test_malformed_tokens_are_rejected():
    """Malformed tokens (bad prefix, missing parts, bad JSON) fail closed with HTTP 401."""
    malformed_samples = [
        "not.a.token",
        "cos.onlytwoparts",
        "cos..missingpayload",
        "cos.payload.",
        "xyz.payload.sig",
        "",
        "Bearer",
        "cos.%%%notb64%%%.signature"
    ]
    for sample in malformed_samples:
        res = client.get("/api/resumes", headers={"Authorization": f"Bearer {sample}"})
        detail = res.json()["detail"]
        assert "Authentication failed" in detail or "Invalid Authorization header" in detail or "Authentication required" in detail


# =========================================================================
# Security Test 7: Missing production secrets prevent startup
# =========================================================================
def test_shipped_secret_key_default_is_empty():
    """No usable signing key may ship as a module default."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    env = {k: v for k, v in os.environ.items() if k != "SECRET_KEY"}
    env["PYTHONPATH"] = str(repo_root)
    out = subprocess.check_output(
        [
            sys.executable,
            "-c",
            "from backend.app.config import Settings; "
            "print(Settings.model_fields['SECRET_KEY'].default)",
        ],
        cwd=repo_root,
        env=env,
        text=True,
    ).strip()
    assert out == ""


def test_missing_production_secrets_prevent_startup():
    """In production, missing or weak default SECRET_KEY aborts startup with RuntimeError."""
    with patch.object(settings, "ENVIRONMENT", "production"):
        with patch.object(settings, "AUTH_REQUIRED", True):
            # Test empty secret
            with patch.object(settings, "SECRET_KEY", ""):
                with pytest.raises(RuntimeError) as exc:
                    settings.validate_security_configuration()
                assert "Missing or insecure SECRET_KEY" in str(exc.value)

            # Test weak default secret
            with patch.object(settings, "SECRET_KEY", "careeros-secure-signing-secret-key-2026"):
                with pytest.raises(RuntimeError) as exc:
                    settings.validate_security_configuration()
                assert "Missing or insecure SECRET_KEY" in str(exc.value)

            # Test short secret (< 32 characters)
            with patch.object(settings, "SECRET_KEY", "too-short-secret"):
                with pytest.raises(RuntimeError) as exc:
                    settings.validate_security_configuration()
                assert "Missing or insecure SECRET_KEY" in str(exc.value)

            # Test strong secret (>= 32 chars) passes
            strong_secret = "a" * 32
            with patch.object(settings, "SECRET_KEY", strong_secret), patch.object(settings, "CAREEROS_TOKEN_SECRET", strong_secret):
                settings.validate_security_configuration() # Should not raise


# =========================================================================
# Security Test 8: Production cannot run with AUTH_REQUIRED=False
# =========================================================================
def test_production_cannot_run_with_auth_required_false():
    """In production, disabling authentication is forbidden and raises RuntimeError."""
    with patch.object(settings, "ENVIRONMENT", "production"):
        with patch.object(settings, "AUTH_REQUIRED", False):
            with patch.object(settings, "SECRET_KEY", "a" * 32):
                with pytest.raises(RuntimeError) as exc:
                    settings.validate_security_configuration()
                assert "Production cannot run with AUTH_REQUIRED=False" in str(exc.value)


# =========================================================================
# Security Test 9: Client-controlled X-User-Id cannot override Bearer identity
# =========================================================================
def test_client_controlled_x_user_id_cannot_override_bearer_identity():
    """A client cannot inject an untrusted X-User-Id to hijack identity when Bearer auth is present."""
    token_user_100 = create_access_token(user_id=100)

    # Attempting to send Bearer token for 100 while also injecting X-User-Id: 200
    headers = {
        "Authorization": f"Bearer {token_user_100}",
        "X-User-Id": "200"
    }
    # Direct X-User-Id injection is untrusted and rejected with 401
    res = client.get("/api/resumes", headers=headers)
    assert res.status_code == 401
    assert "Untrusted client identity" in res.json()["detail"]


# =========================================================================
# Security Test 10: Invalid internal gateway secrets are rejected
# =========================================================================
def test_invalid_internal_gateway_secrets_are_rejected():
    """Gateway forwarding with incorrect internal secret is rejected with HTTP 401."""
    with patch.object(settings, "INTERNAL_GATEWAY_SECRET", "super-secret-gateway-signing-token-999"):
        headers = {
            "X-User-Id": "500",
            "X-Internal-Secret": "wrong-and-invalid-secret-token"
        }
        res = client.get("/api/resumes", headers=headers)
        assert res.status_code == 401
        assert "Invalid internal gateway secret" in res.json()["detail"]


# =========================================================================
# Security Test 11: Valid development authentication works only in configured dev mode
# =========================================================================
def test_valid_development_authentication_works_only_in_configured_dev_mode():
    """Development token minting functions in development, but is strictly blocked in production."""
    # 1. In development mode
    with patch.object(settings, "ENVIRONMENT", "development"):
        res = client.post("/api/auth/token", json={"user_id": 42})
        assert res.status_code == 200
        token_data = res.json()
        assert token_data["user_id"] == 42
        assert token_data["token_type"] == "bearer"
        assert token_data["mode"] == "development"

        # Verify minted development token works
        dev_token = token_data["access_token"]
        res_cand = client.get("/api/candidate", headers={"Authorization": f"Bearer {dev_token}"})
        assert res_cand.status_code == 200
        assert res_cand.json()["user_id"] == 42

    # 2. In production mode without gateway secret -> strictly blocked
    with patch.object(settings, "ENVIRONMENT", "production"):
        res_prod = client.post("/api/auth/token", json={"user_id": 42})
        assert res_prod.status_code == 403


# =========================================================================
# Security Test 12: Existing authorized user workflows remain functional
# =========================================================================
def test_existing_authorized_user_workflows_remain_functional():
    """Authorized users with valid Bearer tokens can execute all Resume Studio and Candidate workflows."""
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)

    # Candidate profile access
    res_cand = client.get("/api/candidate", headers=headers)
    assert res_cand.status_code == 200
    assert res_cand.json()["user_id"] == user_id

    # Master resume initialization
    res_master = client.get("/api/resumes/master", headers=headers)
    assert res_master.status_code == 200
    assert res_master.json()["user_id"] == user_id
    assert res_master.json()["is_master"] is True

    # List resumes
    res_resumes = client.get("/api/resumes", headers=headers)
    assert res_resumes.status_code == 200
    assert "items" in res_resumes.json()
