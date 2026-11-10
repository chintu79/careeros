"""
Sanitized operator diagnostics snapshot (Phase 3.0.6).

Never includes: connection strings, hosts, usernames, candidate ids, emails,
query parameters, stack frames, or file contents. Safe to paste into a ticket.
"""

import os
from typing import Any, Dict

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from backend.app.config import settings


def _db_state() -> str:
    try:
        engine = create_engine(
            settings.DATABASE_URL,
            poolclass=NullPool,
            connect_args={"connect_timeout": 2, "options": "-c statement_timeout=2000"},
        )
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return "ok"
        finally:
            engine.dispose()
    except Exception:
        return "unreachable"


def _storage_state() -> str:
    try:
        from backend.app.services import readiness

        return readiness.check_storage().get("storage:resumes", "error")
    except Exception:
        return "error"


def _scheduler_state() -> Dict[str, Any]:
    try:
        from backend.app.services.discovery_scheduler import SCHEDULER_STATE

        return {
            "is_enabled": SCHEDULER_STATE.get("is_enabled"),
            "jobs_executed": SCHEDULER_STATE.get("jobs_executed", 0),
            "failure_count": SCHEDULER_STATE.get("failure_count", 0),
            "last_success_at": SCHEDULER_STATE.get("last_success_at"),
            "last_failure_at": SCHEDULER_STATE.get("last_failure_at"),
            "running": bool(SCHEDULER_STATE.get("is_running_cycle")),
        }
    except Exception:
        return {"state": "unavailable"}


def _metrics_availability() -> Dict[str, Any]:
    from backend.app.observability.metrics import metrics

    snapshot = metrics.snapshot()
    return {
        "counters": len(snapshot["counters"]),
        "uptime_seconds": snapshot["uptime_seconds"],
        "available": True,
    }


def build_snapshot(app_version: str) -> Dict[str, Any]:
    from backend.app.observability.metrics import metrics

    return {
        "service": "interniq-discovery-engine",
        "version": app_version,
        "environment": os.environ.get("ENVIRONMENT", "development").lower(),
        "application": {
            "uptime_seconds": metrics.snapshot()["uptime_seconds"],
        },
        "dependencies": {
            "database": _db_state(),
            "scheduler": _scheduler_state(),
            "storage": _storage_state(),
        },
        "metrics": _metrics_availability(),
        "recent_errors": metrics.error_counters(),
        "notes": "no host, port, connection string, credentials or candidate data are included in this snapshot",
    }
