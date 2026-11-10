import time
import json
import hmac
import hashlib
import base64
import logging
from typing import Optional, Dict, Any
from fastapi import Header, HTTPException, Depends

from backend.app.config import settings

logger = logging.getLogger(__name__)

TOKEN_PREFIX = "cos"


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64_decode(data: str) -> bytes:
    padding = 4 - (len(data) % 4)
    if padding and padding < 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data.encode("utf-8"))


def create_access_token(
    user_id: int, 
    ttl_seconds: int = 86400,
    issuer: str = "careeros",
    audience: str = "careeros-api"
) -> str:
    """
    Mints a cryptographic HMAC-SHA256 signed access token for the given user_id.
    Format: cos.<b64_payload>.<b64_sig>
    """
    if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
        raise ValueError(f"Invalid user_id: {user_id}. Must be a positive integer.")

    secret = settings.SECRET_KEY
    if not secret or not secret.strip():
        raise RuntimeError("Cannot mint token: SECRET_KEY is not configured.")

    now = int(time.time())
    tv = getattr(settings, "TOKEN_VERSION", "1") or "1"
    payload = {
        "sub": str(user_id),
        "user_id": int(user_id),
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + ttl_seconds,
        "v": 1,
        "tv": str(tv),
    }
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode("utf-8")
    payload_b64 = _b64_encode(payload_bytes)

    secret_bytes = secret.encode("utf-8")
    sig = hmac.new(secret_bytes, payload_b64.encode("utf-8"), hashlib.sha256).digest()
    sig_b64 = _b64_encode(sig)

    return f"{TOKEN_PREFIX}.{payload_b64}.{sig_b64}"


def verify_access_token(
    token: str,
    expected_issuer: str = "careeros",
    expected_audience: str = "careeros-api"
) -> int:
    """
    Cryptographically verifies an access token.
    Enforces HMAC-SHA256 signature, payload structure, expiration, clock skew, and valid positive user_id.
    Returns user_id on success, or raises HTTPException(401) on failure.
    """
    if not token or not isinstance(token, str) or not token.strip():
        raise HTTPException(
            status_code=401,
            detail="Authentication failed: Missing or invalid token format."
        )

    parts = token.strip().split(".")
    if len(parts) != 3 or parts[0] != TOKEN_PREFIX or not parts[1] or not parts[2]:
        raise HTTPException(
            status_code=401,
            detail="Authentication failed: Invalid token structure."
        )

    _, payload_b64, provided_sig_b64 = parts

    secret = settings.SECRET_KEY
    if not secret or not secret.strip():
        raise HTTPException(
            status_code=401,
            detail="Authentication failed: Signing secret unconfigured."
        )

    secret_bytes = secret.encode("utf-8")
    expected_sig = hmac.new(secret_bytes, payload_b64.encode("utf-8"), hashlib.sha256).digest()
    expected_sig_b64 = _b64_encode(expected_sig)

    if not hmac.compare_digest(provided_sig_b64, expected_sig_b64):
        raise HTTPException(
            status_code=401,
            detail="Authentication failed: Cryptographic signature mismatch or forged token."
        )

    try:
        payload_bytes = _b64_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a JSON object")
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Authentication failed: Malformed token payload."
        )

    now = int(time.time())

    # Validate issuance time and clock skew (reject future-issued tokens > 60s ahead)
    iat = payload.get("iat")
    if iat is None or not isinstance(iat, (int, float)):
        raise HTTPException(
            status_code=401,
            detail="Authentication failed: Missing or invalid iat claim."
        )
    if iat > now + 60:
        raise HTTPException(
            status_code=401,
            detail="Authentication failed: Token issued in the future (clock skew violation)."
        )

    # Validate expiration
    exp = payload.get("exp")
    if exp is None or not isinstance(exp, (int, float)):
        raise HTTPException(
            status_code=401,
            detail="Authentication failed: Missing or invalid exp claim."
        )
    if exp < now:
        raise HTTPException(
            status_code=401,
            detail="Authentication failed: Token has expired."
        )
    if exp <= iat:
        raise HTTPException(
            status_code=401,
            detail="Authentication failed: Invalid token lifetime claims."
        )

    # Validate token version claim; bump settings.TOKEN_VERSION to revoke all outstanding tokens.
    # Tokens minted before the version gate exist (or with a mismatched tv) are rejected,
    # which invalidates all 30-day legacy tokens and any rotated-out versions.
    expected_tv = getattr(settings, "TOKEN_VERSION", "1") or "1"
    tv = payload.get("tv")
    if str(tv) != str(expected_tv):
        raise HTTPException(
            status_code=401,
            detail="Authentication failed: token version mismatch. Re-authenticate."
        )

    # Validate issuer and audience claims if present
    iss = payload.get("iss")
    if iss is not None and iss != expected_issuer:
        raise HTTPException(
            status_code=401,
            detail=f"Authentication failed: Invalid token issuer '{iss}'."
        )

    aud = payload.get("aud")
    if aud is not None and aud != expected_audience:
        raise HTTPException(
            status_code=401,
            detail=f"Authentication failed: Invalid token audience '{aud}'."
        )

    # Validate user identity claims
    user_id = payload.get("user_id")
    if user_id is None or isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
        raise HTTPException(
            status_code=401,
            detail="Authentication failed: Missing or invalid user_id in token claims."
        )

    sub = payload.get("sub")
    if sub is None or str(sub) != str(user_id):
        raise HTTPException(
            status_code=401,
            detail="Authentication failed: Subject claim does not match user_id."
        )

    return int(user_id)


def get_current_user_id(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret")
) -> int:
    """
    Resolves the authenticated user identity with strict boundary verification:
    1. If client supplies X-User-Id:
       - Must be accompanied by valid X-Internal-Secret == INTERNAL_GATEWAY_SECRET.
       - If secret is missing or invalid, REJECT with HTTP 401.
       - Client-controlled X-User-Id cannot override or bypass Bearer identity.
    2. If client supplies Authorization: Bearer <token>, cryptographically verify and return user_id.
    3. If unauthenticated:
       - In production (settings.is_production) or if AUTH_REQUIRED: REJECT with HTTP 401.
       - In explicitly configured non-production development mode (AUTH_REQUIRED=False): return DEFAULT_USER_ID.
    """
    # 1. Check for client injection of X-User-Id header
    if x_user_id is not None:
        gateway_secret = settings.INTERNAL_GATEWAY_SECRET
        if gateway_secret and gateway_secret.strip() and x_internal_secret:
            if hmac.compare_digest(x_internal_secret, gateway_secret):
                try:
                    uid = int(x_user_id)
                    if uid <= 0:
                        raise ValueError()
                    return uid
                except ValueError:
                    raise HTTPException(status_code=401, detail="Invalid X-User-Id format from gateway.")
            else:
                raise HTTPException(status_code=401, detail="Invalid internal gateway secret.")
        # Reject unverified client spoofing of X-User-Id
        raise HTTPException(
            status_code=401,
            detail="Untrusted client identity: Direct X-User-Id injection rejected. Provide a valid Bearer token."
        )

    # 2. Standard Bearer token authentication
    if authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
            return verify_access_token(token)
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'."
        )

    # 3. Anonymous requests
    if settings.is_production or settings.AUTH_REQUIRED:
        raise HTTPException(
            status_code=401,
            detail="Authentication required: No credentials provided. Include 'Authorization: Bearer <token>'."
        )

    # In local companion / desktop single-user development mode only
    return settings.DEFAULT_USER_ID
