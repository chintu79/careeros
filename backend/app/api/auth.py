import hmac
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, Field
from typing import Optional

from backend.app.config import settings
from backend.app.core.auth import create_access_token
from backend.app.services.rate_limit import rate_limited

router = APIRouter(prefix="/auth", tags=["Authentication"])


class TokenRequest(BaseModel):
    user_id: int = Field(default=1, description="Candidate User ID to mint token for")
    ttl_seconds: Optional[int] = Field(default=86400, description="Token time-to-live in seconds")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    expires_in: int
    mode: str = "development"


@router.post("/token", response_model=TokenResponse, dependencies=[Depends(rate_limited("auth"))])
def obtain_access_token(
    req: Optional[TokenRequest] = None,
    x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret")
):
    """
    Issues an HMAC-SHA256 signed access token.
    
    SECURITY ENFORCEMENT:
    - In production (settings.is_production):
      Unauthenticated token minting for arbitrary user IDs is strictly disabled (HTTP 403 Forbidden).
      Tokens can only be minted by a verified internal gateway (valid X-Internal-Secret).
    - In development/test mode:
      Used by desktop companion and testing environments to establish authenticated sessions.
      Validates that user_id is a positive integer.
    """
    target_user_id = req.user_id if req and req.user_id is not None else 1
    ttl = req.ttl_seconds if req and req.ttl_seconds is not None else 86400

    if not isinstance(target_user_id, int) or isinstance(target_user_id, bool) or target_user_id <= 0:
        raise HTTPException(
            status_code=422,
            detail="Invalid user_id: must be a positive integer."
        )

    # 1. Strict Production Guard
    if settings.is_production:
        gateway_secret = settings.INTERNAL_GATEWAY_SECRET
        is_trusted_gateway = bool(
            gateway_secret 
            and gateway_secret.strip() 
            and x_internal_secret 
            and hmac.compare_digest(x_internal_secret, gateway_secret)
        )
        if not is_trusted_gateway:
            raise HTTPException(
                status_code=403,
                detail="Arbitrary token minting is disabled in production. "
                       "Authenticate via verified identity provider or trusted internal gateway."
            )

    # 2. Strict Development Mode Check
    if not settings.is_development and not settings.is_production:
        raise HTTPException(
            status_code=403,
            detail="Token issuance endpoint is disabled for the current environment configuration."
        )

    # Maximum TTL cap (24 hours) to prevent unbounded lifetime tokens
    max_ttl = 86400
    if ttl > max_ttl or ttl <= 0:
        ttl = max_ttl

    token = create_access_token(user_id=target_user_id, ttl_seconds=ttl)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=target_user_id,
        expires_in=ttl,
        mode="production" if settings.is_production else "development"
    )

