"""
CareerOS observability (Phase 3.0.6).

Structured JSON logging, correlation context, bounded-cardinality metrics and a
sanitized diagnostics snapshot. No external services, no database writes, no PII.
"""
from backend.app.observability.context import (
    bind_request_context,
    clear_request_context,
    current_request_id,
    current_request_meta,
)
from backend.app.observability.metrics import metrics
from backend.app.observability.logging_config import configure_logging, get_logger, redact

__all__ = [
    "bind_request_context",
    "clear_request_context",
    "current_request_id",
    "current_request_meta",
    "metrics",
    "configure_logging",
    "get_logger",
    "redact",
]
