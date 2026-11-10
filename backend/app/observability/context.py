"""
Per-request correlation state. Backed by contextvars so concurrent tasks stay isolated.
"""
import contextvars
from typing import Mapping, Optional, Tuple

_request_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)
_request_meta: contextvars.ContextVar[Tuple[str, str]] = contextvars.ContextVar("request_meta", default=("", ""))


def bind_request_context(request_id: str, method: str, route: str) -> None:
    _request_id.set(request_id)
    _request_meta.set((method, route))


def clear_request_context() -> None:
    _request_id.set(None)
    _request_meta.set(("", ""))


def current_request_id() -> Optional[str]:
    return _request_id.get()


def current_request_meta() -> Tuple[str, str]:
    return _request_meta.get()
