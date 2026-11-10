"""
Readiness checks: bounded, read-only, and safe to run repeatedly.

- Database: short-lived NullPool engine, 3s connect timeout, 3s statement timeout.
- Extensions: queried on the same bounded connection.
- Storage: NamedTemporaryFile inside the storage dir; deleted on context exit.
- Scheduler: reads SCHEDULER_STATE only; never triggers a cycle.
- Optional AI providers: reported but never block readiness.

No credentials, hosts or connection strings are returned to callers.
"""
import logging
import os
import tempfile

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from backend.app.config import settings

logger = logging.getLogger("interniq")

_OPTIONAL_PREFIX = "optional:"
CONNECT_TIMEOUT_SECONDS = 3
STATEMENT_TIMEOUT_MS = 3000


def _storage_dir() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "storage", "resumes"))


def check_database() -> dict:
    """Connectivity + required extensions, bounded in time and resources."""
    engine = None
    try:
        engine = create_engine(
            settings.DATABASE_URL,
            poolclass=NullPool,
            connect_args={
                "connect_timeout": CONNECT_TIMEOUT_SECONDS,
                "options": f"-c statement_timeout={STATEMENT_TIMEOUT_MS}",
            },
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            extensions = {row[0] for row in conn.execute(text("SELECT extname FROM pg_extension"))}
        return {
            "database": "ok",
            "extension:vector": "ok" if "vector" in extensions else "missing",
        }
    except Exception as exc:
        logger.warning("readiness: database check failed: %s", type(exc).__name__)
        return {"database": "error", "extensions": "error"}
    finally:
        if engine is not None:
            engine.dispose()


def check_storage() -> dict:
    """Probe write access with a temporary file that is always removed."""
    try:
        directory = _storage_dir()
        os.makedirs(directory, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix=".readiness-", dir=directory, delete=True) as probe:
            probe.write(b"ok")
            probe.flush()
        return {"storage:resumes": "ok"}
    except Exception as exc:
        logger.warning("readiness: storage check failed: %s", type(exc).__name__)
        return {"storage:resumes": "error"}


def check_scheduler() -> dict:
    """Inspect scheduler state; never start or trigger a cycle."""
    try:
        from backend.app.services.discovery_scheduler import SCHEDULER_STATE
        return {"scheduler": "ok" if SCHEDULER_STATE.get("last_check_at") else "starting"}
    except Exception as exc:
        logger.warning("readiness: scheduler check failed: %s", type(exc).__name__)
        return {"scheduler": "error"}


_INSECURE_SECRETS = {
    "careeros-secure-signing-secret-key-2026", "secret", "changeme",
    "password", "default", "admin", "test", "12345678",
}


def _secret_ok(value) -> bool:
    value = (value or "").strip()
    return len(value) >= 32 and value.lower() not in _INSECURE_SECRETS


def check_secrets() -> dict:
    """Required secrets valid; optional providers reported without gating."""
    token_ok = settings.CAREEROS_TOKEN_SECRET is None or _secret_ok(settings.CAREEROS_TOKEN_SECRET)
    return {
        "secret:SECRET_KEY": "ok" if _secret_ok(settings.SECRET_KEY) else "missing",
        "secret:CAREEROS_TOKEN_SECRET": "ok" if token_ok else "insecure",
        f"{_OPTIONAL_PREFIX}groq": "configured" if bool(settings.GROQ_API_KEY) else "not_configured",
    }


def run_checks() -> dict:
    checks = {}
    checks.update(check_database())
    checks.update(check_secrets())
    checks.update(check_storage())
    checks.update(check_scheduler())
    return checks


def is_ready(checks: dict) -> bool:
    return all(value == "ok" for key, value in checks.items() if not key.startswith(_OPTIONAL_PREFIX))
