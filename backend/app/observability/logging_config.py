"""
Structured JSON logging with redaction.

Every record emitted by this process is a single JSON object containing:
  ts, level, service, environment, request_id (when in request scope), event, logger.

Untrusted/sensitive material is stripped recursively:
  - keys whose name looks like a secret (password/token/secret/key/authorization/cookie/credential),
  - connection strings embedded in values (scheme://user:pass@host -> scheme://***@host).
"""

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Mapping

REDACT_KEYS = {
    "password", "passwd", "secret", "token", "api_key", "apikey", "access_token",
    "refresh_token", "authorization", "cookie", "set-cookie", "private_key",
    "client_secret", "credential", "credentials", "dsn", "database_url",
    "db_url", "connection_string", "connection_str",
}

_CONNECTION_STRING = re.compile(r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]{0,40}://)(?P<userinfo>[^/@\s:]{1,256}:[^/@\s]{1,256}@)")
_QUERY_VALUE = re.compile(r"([?&](?:access_token|token|key|secret|password|auth)=)[^&\s]{1,512}", re.IGNORECASE)


def _redact_scalar(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return value
    value = _CONNECTION_STRING.sub(lambda m: f"{m.group('scheme')}***@", value)
    value = _QUERY_VALUE.sub(lambda m: f"{m.group(1)}***", value)
    return value


def redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): ("***" if str(key).lower().replace("-", "_") in REDACT_KEYS else redact(item))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return _redact_scalar(value)


def _safe_extra(record: logging.LogRecord) -> Mapping[str, Any]:
    reserved = {
        "args", "asctime", "created", "exc_info", "exc_text", "filename", "funcName",
        "levelname", "levelno", "lineno", "module", "msecs", "message", "msg",
        "name", "pathname", "process", "processName", "relativeCreated",
        "thread", "threadName", "stack_info", "taskName",
    }
    extras = {k: v for k, v in record.__dict__.items() if k not in reserved and not k.startswith("_")}
    return redact(extras)


class JsonFormatter(logging.Formatter):
    SERVICE = "interniq-discovery-engine"

    def formatTime(self, record, datefmt=None):  # noqa: N802
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    def format(self, record: logging.LogRecord) -> str:
        from backend.app.observability.context import current_request_id

        try:
            request_id = current_request_id()
        except Exception:
            request_id = None

        try:
            environment = os.environ.get("ENVIRONMENT", "development").lower()
        except Exception:
            environment = "development"

        event = getattr(record, "event", None) or record.getMessage()
        payload = {
            "ts": self.formatTime(record, None),
            "level": record.levelname,
            "service": self.SERVICE,
            "environment": environment,
            "event": redact(str(event)),
            "logger": record.name,
        }
        if request_id:
            payload["request_id"] = request_id
        payload.update(_safe_extra(record))
        if record.exc_info:
            exc = self.formatException(record.exc_info)
            payload["exception"] = redact(exc)
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_logging(level: str | None = None) -> None:
    resolved = (level or os.environ.get("CAREEROS_LOG_LEVEL", "INFO")).upper()
    handler = logging.StreamHandler(sys.stdout)  # type: ignore[name-defined]
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(resolved)
    # Library transport logs are noise at INFO (they can include full URLs).
    for name in ("uvicorn", "uvicorn.access", "httpx", "httpcore", "urllib3"):
        child = logging.getLogger(name)
        child.handlers = [handler]
        child.propagate = False
        child.setLevel("WARNING")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
