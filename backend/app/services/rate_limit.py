"""
Rate limiting backed by the shared PostgreSQL store.

Design:
- Buckets are (scope, identity) tuples persisted in `rate_limit_buckets`.
- All reads/writes happen inside one transaction with SELECT ... FOR UPDATE,
  which serializes per-bucket across processes and workers.
- This avoids the correctness hole of process-local counters when multiple
  workers serve behind a load balancer.
- Failure policy (fail-closed): any store error returns 503, never fail open.
"""

import logging
import os
import time
from dataclasses import dataclass
from typing import Optional, Tuple

from fastapi import Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.core.auth import get_current_user_id
from backend.app.observability.metrics import metrics as _rate_metrics

logger = logging.getLogger("interniq.ratelimit")


@dataclass(frozen=True)
class RateLimitRule:
    capacity: float
    refill_per_second: float  # tokens added per second; 1/x = window for full refill
    scope: str                 # "ip" or "user"

    def retry_after_seconds(self, tokens_now: float) -> int:
        if tokens_now >= 1.0:
            return 1
        missing = max(1.0 - tokens_now, 0.0)
        return max(1, int(missing / max(self.refill_per_second, 1e-9)))


# Scale factor for capacities; defaults to 1.0 (production). Tests may set
# RATE_LIMIT_SCALE > 1 to relax limits fork-wide (the same code path runs, so behavior is consistent).
_RATE_LIMIT_SCALE = float(os.environ.get("RATE_LIMIT_SCALE", "1.0") or 1.0)
if _RATE_LIMIT_SCALE != 1.0:
    logger.info("rate-limit scale factor=%.2f (test fork)", _RATE_LIMIT_SCALE)

# Named policies. Values lean conservative for AI/upload endpoints.
RULES = {
    # 20 AI requests per hour per user
    "ai": RateLimitRule(capacity=20.0, refill_per_second=20.0 / 3600.0, scope="user"),
    # 10 uploads per hour per user
    "upload": RateLimitRule(capacity=10.0, refill_per_second=10.0 / 3600.0, scope="user"),
    # 30 match evaluations per hour per user
    "match": RateLimitRule(capacity=30.0, refill_per_second=30.0 / 3600.0, scope="user"),
    # 120 discovery reads per minute per user
    "discovery": RateLimitRule(capacity=120.0, refill_per_second=2.0, scope="user"),
    # 300 mints per minute per IP (dev-friendly; production minting is gated by the gateway secret anyway)
    "auth": RateLimitRule(capacity=300.0, refill_per_second=5.0, scope="ip"),
}


if _RATE_LIMIT_SCALE != 1.0:
    RULES = {
        name: RateLimitRule(capacity=rule.capacity * _RATE_LIMIT_SCALE,
                            refill_per_second=rule.refill_per_second * _RATE_LIMIT_SCALE,
                            scope=rule.scope)
        for name, rule in RULES.items()
    }


def self_validate_rule(policy_name: str) -> 'RateLimitRule':
    rule = RULES.get(policy_name)
    if rule is None:
        raise RuntimeError(f"unknown rate limit policy: {policy_name}")
    return rule


def client_ip(request: Request) -> str:
    """
    Best-effort client IP without trusting spoofed headers by default.
    TRUST_PROXY_HOPS=0 (default): use request.client.host, ignore X-Forwarded-For.
    TRUST_PROXY_HOPS=N>0: use the N-th X-Forwarded-For entry counting from the right,
    matching the number of reverse proxy hops the app is deployed behind.
    """
    hops = int(getattr(__import__("backend.app.config", fromlist=["settings"]).settings, "TRUST_PROXY_HOPS", 0) or 0)
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if hops > 0 and xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if len(parts) >= hops:
            return parts[-hops]
    return (request.client.host if request.client else "unknown").strip().lower()


def _bucket_key(rule: RateLimitRule, identity: str) -> str:
    return f"{rule.scope}:{identity}"


def _take(db: Session, key: str, rule: RateLimitRule) -> Tuple[bool, float, int]:
    """
    Atomically attempt to consume one token for `key`.
    Returns (allowed, current_tokens_after_this_call, retry_after_seconds).
    """
    # SELECT ... FOR UPDATE serializes competing writers for this bucket across
    # processes. A single transaction gives atomic check-and-consume semantics.
    row = db.execute(
        text(
            """
            SELECT tokens, capacity, refill_per_second,
                   extract(epoch from updated_at) AS updated_epoch
            FROM rate_limit_buckets
            WHERE bucket_key = :k
            FOR UPDATE
            """
        ),
        {"k": key},
    ).mappings().first()

    now = time.time()
    if row is None:
        # First request for this bucket: start full, consume one.
        new_tokens = rule.capacity - 1.0
        db.execute(
            text("""
                INSERT INTO rate_limit_buckets (bucket_key, tokens, capacity, refill_per_second, updated_at)
                VALUES (:k, :t, :c, :r, NOW())
                ON CONFLICT (bucket_key) DO NOTHING
            """),
            {"k": key, "t": new_tokens, "c": rule.capacity, "r": rule.refill_per_second},
        )
        db.commit()
        return True, new_tokens, rule.retry_after_seconds(new_tokens)

    stored_tokens = float(row["tokens"])
    capacity = float(row["capacity"])
    refill = float(row["refill_per_second"])
    updated_epoch = float(row["updated_epoch"] or now)

    # Lazy refill: add tokens proportional to elapsed time, capped at capacity.
    elapsed = max(0.0, now - updated_epoch)
    tokens_now = min(capacity, stored_tokens + elapsed * refill)

    if tokens_now < 1.0:
        db.commit()  # release the FOR UPDATE row without consuming a token
        return False, tokens_now, rule.retry_after_seconds(tokens_now)

    new_tokens = tokens_now - 1.0
    db.execute(
        text("UPDATE rate_limit_buckets SET tokens = :t, updated_at = NOW() WHERE bucket_key = :k"),
        {"t": new_tokens, "k": key},
    )
    db.commit()
    return True, new_tokens, rule.retry_after_seconds(new_tokens)


def rate_limited(policy_name: str):
    """
    Dependency factory. Usage:
        @router.post("/...", dependencies=[Depends(rate_limited("ai"))])
        def handler(..., _: RateLimitOutcome = Depends(rate_limited("ai"))): ...
    """
    async def _check_user(request: Request, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
        rule = RULES.get(policy_name) or self_validate_rule(policy_name)
        try:
            key = _bucket_key(rule, str(user_id))
            allowed, tokens_now, retry_after = _take(db, key, rule)
        except Exception as exc:
            _rate_metrics.inc("rate_limit_store_failures_total", {"policy": policy_name})
            logger.warning("rate_limit_store_unavailable bucket=%s error=%s", policy_name, exc)
            raise HTTPException(status_code=503, detail="Service temporarily unavailable. Please retry shortly.", headers={"Retry-After": "5"})
        if not allowed:
            _rate_metrics.inc("rate_limit_rejections_total", {"policy": policy_name, "scope": rule.scope})
            raise HTTPException(status_code=429, detail="Too many requests. Please retry later.", headers={"Retry-After": str(retry_after)})
        return True

    async def _check_ip(request: Request, db: Session = Depends(get_db)):
        rule = RULES.get(policy_name) or self_validate_rule(policy_name)
        try:
            key = _bucket_key(rule, client_ip(request))
            allowed, tokens_now, retry_after = _take(db, key, rule)
        except Exception as exc:
            _rate_metrics.inc("rate_limit_store_failures_total", {"policy": policy_name})
            logger.warning("rate_limit_store_unavailable bucket=%s error=%s", policy_name, exc)
            raise HTTPException(status_code=503, detail="Service temporarily unavailable. Please retry shortly.", headers={"Retry-After": "5"})
        if not allowed:
            _rate_metrics.inc("rate_limit_rejections_total", {"policy": policy_name, "scope": rule.scope})
            raise HTTPException(status_code=429, detail="Too many requests. Please retry later.", headers={"Retry-After": str(retry_after)})
        return True

    if (RULES.get(policy_name) or (_ for _ in ()).throw(RuntimeError(f"unknown rate limit policy: {policy_name}"))).scope == "user":
        return _check_user
    return _check_ip


def prune_expired_buckets(db: Session, max_age_seconds: int = 86400) -> int:
    """Delete buckets untouched for max_age_seconds (default 24h). Returns count."""
    res = db.execute(
        text("DELETE FROM rate_limit_buckets WHERE updated_at < NOW() - (:s * INTERVAL '1 second')"),
        {"s": int(max_age_seconds)},
    )
    db.commit()
    return res.rowcount or 0
