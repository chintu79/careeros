import hmac
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings
from backend.app.database import engine, Base, SessionLocal
from backend.app.services.seed_data import seed_initial_data

from backend.app.observability import (
    bind_request_context,
    clear_request_context,
    configure_logging,
    get_logger,
)
from backend.app.observability.metrics import http_completed, bounded_route, bounded_method

configure_logging()
logger = get_logger("interniq")

from backend.app.api.opportunities import router as opportunities_router
from backend.app.api.import_jobs import router as import_router
from backend.app.api.companies import router as companies_router
from backend.app.api.sources import router as sources_router
from backend.app.api.preferences import router as preferences_router
from backend.app.api.candidate import router as candidate_router
from backend.app.api.applications import router as applications_router
from backend.app.api.analytics import router as analytics_router
from backend.app.api.notifications import router as notifications_router
from backend.app.api.resumes import router as resumes_router
from backend.app.api.interviews import router as interviews_router
from backend.app.api.chat import router as chat_router
from backend.app.api.command_center import router as command_center_router
from backend.app.api.searches import router as searches_router
from backend.app.api.recruiters import router as recruiters_router
from backend.app.api.ai_command import router as ai_command_router
from backend.app.api.integrations import router as integrations_router
from backend.app.api.email_intelligence import router as email_intelligence_router
from backend.app.api.ai_diagnostics import ai_diagnostics_router
from backend.app.api.auth import router as auth_router

import asyncio
from backend.app.services.discovery_scheduler import background_scheduler_worker

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Enforce production security constraints before accepting requests
    settings.validate_security_configuration()

    if settings.RUN_MIGRATIONS:
        from backend.app.services.database_migration import run_database_migrations
        run_database_migrations(engine)
    else:
        logger.info("CAREEROS_RUN_MIGRATIONS not set — skipping implicit migrations at startup.")
    
    db = SessionLocal()
    try:
        if settings.SEED_DEMO_DATA:
            logger.info("SEED_DEMO_DATA=true — seeding demo fixtures (development only).")
            await seed_initial_data(db)
        else:
            logger.info("SEED_DEMO_DATA=false — skipping demo seed (production-safe).")
    finally:
        db.close()
        
    logger.info("interniq Job Discovery Engine ready! Starting background scheduler worker...")
    scheduler_task = asyncio.create_task(background_scheduler_worker(check_interval_seconds=60))
    yield
    logger.info("Shutting down background scheduler worker and interniq Discovery Engine...")
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Intelligent Job Discovery & Opportunity Aggregation Engine for CareerOS",
    version="1.0.0",
    lifespan=lifespan
)

allowed_origins = getattr(settings, 'ALLOWED_ORIGINS', None) or []
if '*' in allowed_origins:
    msg = "Wildcard CORS origin rejected: configure CAREEROS_ALLOWED_ORIGINS with explicit origins."
    if settings.is_production:
        raise RuntimeError(msg)
    logger.warning(msg)
    allowed_origins = [o for o in allowed_origins if o != '*']

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)


@app.middleware("http")
async def request_correlation(request, call_next):
    incoming = (request.headers.get("x-request-id") or "").strip()
    request_id = incoming if re.fullmatch(r"[A-Za-z0-9-]{8,128}", incoming) else uuid.uuid4().hex
    path = request.url.path
    if path in ("/api/health", "/api/ready"):
        # Liveness/readiness: excluded from logs and metrics to keep them cheap.
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response

    bind_request_context(request_id, request.method, path)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration = time.perf_counter() - started
        http_completed(request.method, "unmatched", 500, duration, error=True)
        clear_request_context()
        raise

    duration = time.perf_counter() - started
    try:
        route = getattr(request.scope.get("route"), "path", None) or "unmatched"
    except Exception:
        route = "unmatched"
    route = bounded_route(route)
    bind_request_context(request_id, request.method, route)
    status_code = response.status_code
    error = status_code >= 500
    log = logger.warning if (error or status_code >= 400) else logger.info
    log(
        "http.request.failed" if error else "http.request.completed",
        extra={
            "event": "http.request.failed" if error else "http.request.completed",
            "method": request.method,
            "route": route,
            "status": status_code,
            "duration_ms": round(duration * 1000, 2),
        },
    )
    http_completed(request.method, route, status_code, duration, error=error)
    clear_request_context()
    response.headers["x-request-id"] = request_id
    return response


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    # Baseline security headers (CSP is intentionally deferred to a report-only phase).
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-XSS-Protection", "0")
    if settings.is_production:
        response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
    return response

app.include_router(opportunities_router, prefix="/api")
app.include_router(import_router, prefix="/api")
app.include_router(companies_router, prefix="/api")
app.include_router(sources_router, prefix="/api")
app.include_router(preferences_router, prefix="/api")
app.include_router(candidate_router, prefix="/api")
app.include_router(applications_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")
app.include_router(resumes_router, prefix="/api")
app.include_router(interviews_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(command_center_router, prefix="/api")
app.include_router(searches_router, prefix="/api")
app.include_router(recruiters_router, prefix="/api")
app.include_router(ai_command_router, prefix="/api/ai")
app.include_router(integrations_router, prefix="/api")
app.include_router(email_intelligence_router, prefix="/api")
app.include_router(ai_diagnostics_router, prefix="/api")
app.include_router(auth_router, prefix="/api")

@app.get("/api/health")
def liveness_check():
    """Process is alive - no dependency verification. Returns 200 unconditionally."""
    return {"status": "alive", "service": "interniq-discovery-engine"}


@app.get("/api/ready")
def readiness_check():
    """Dependency readiness. Bounded, read-only, safe to repeat; no infra detail in production."""
    from fastapi.responses import JSONResponse
    from backend.app.services.readiness import is_ready, run_checks

    checks = run_checks()
    ready = is_ready(checks)
    body = {"status": "ready" if ready else "not_ready"}
    if not settings.is_production:
        body["checks"] = checks
    return JSONResponse(status_code=200 if ready else 503, content=body)


_INTERNAL_TOKEN_ENV = "CAREEROS_DIAGNOSTICS_TOKEN"


def _internal_token() -> str | None:
    token = os.environ.get(_INTERNAL_TOKEN_ENV, "").strip()
    return token or None


def _require_internal_token(request: Request) -> None:
    token = _internal_token()
    if token is None:
        # Diagnostics/metrics are disabled unless explicitly configured.
        raise HTTPException(status_code=404, detail="Not found")
    auth = request.headers.get("authorization", "")
    provided = auth[7:] if auth.lower().startswith("bearer ") else ""
    if not provided or not hmac.compare_digest(provided, token):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/api/internal/metrics", include_in_schema=False)
def internal_metrics(request: Request):
    """Bounded-cardinality in-process metrics. Requires CAREEROS_DIAGNOSTICS_TOKEN."""
    from backend.app.observability.metrics import metrics

    _require_internal_token(request)
    return metrics.render()


@app.get("/api/internal/diagnostics", include_in_schema=False)
def internal_diagnostics(request: Request):
    """Sanitized operator snapshot. Requires CAREEROS_DIAGNOSTICS_TOKEN."""
    from backend.app.observability.diagnostics import build_snapshot

    _require_internal_token(request)
    return build_snapshot(app.version)
