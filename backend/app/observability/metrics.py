"""
Bounded-cardinality, in-process metrics (Phase 3.0.6).

Deliberately dependency-free. Counters/gauges are plain numbers; duration
summaries store {count, sum_seconds}. No label ever contains a candidate id,
email, raw URL, opportunity id or any other unbounded value.
"""

import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}
_DURATION_BUCKETS = (0.025, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
_SAFE_TEMPLATE = re.compile(r"^[a-zA-Z0-9_/\-\.{}]{1,120}$")


def bounded_method(method: Optional[str]) -> str:
    value = (method or "").upper()
    return value if value in ALLOWED_METHODS else "OTHER"


def bounded_route(template: Optional[str]) -> str:
    value = (template or "").strip()
    if not value or not _SAFE_TEMPLATE.match(value):
        return "other"
    return value[:120]


def status_class(status: int) -> str:
    try:
        bucket = int(status) // 100
    except Exception:
        return "other"
    return f"{bucket}xx" if 1 <= bucket <= 5 else "other"


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started = time.time()
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._summaries: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    def _key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        if not labels:
            return name
        rendered = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{rendered}}}"

    def inc(self, name: str, labels: Optional[Dict[str, str]] = None, amount: int = 1) -> None:
        with self._lock:
            key = self._key(name, labels)
            self._counters[key] = self._counters.get(key, 0) + int(amount)

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        with self._lock:
            self._gauges[self._key(name, labels)] = float(value)

    def observe(self, name: str, seconds: float, labels: Optional[Dict[str, str]] = None) -> None:
        with self._lock:
            key = self._key(name, labels)
            summary = self._summaries.get(key)
            if summary is None:
                summary = {"count": 0, "sum_seconds": 0.0, "buckets": {str(b): 0 for b in _DURATION_BUCKETS}}
                self._summaries[key] = summary
            summary["count"] += 1
            summary["sum_seconds"] = round(summary["sum_seconds"] + seconds, 6)
            for bucket in _DURATION_BUCKETS:
                if seconds <= bucket:
                    summary["buckets"][str(bucket)] += 1

    # ------------------------------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            payload = {
                "uptime_seconds": round(time.time() - self._started, 3),
                "counters": dict(sorted(self._counters.items())),
                "gauges": dict(sorted(self._gauges.items())),
                "summaries": dict(sorted(self._summaries.items())),
                "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        return payload

    def db_pool_gauges(self) -> Dict[str, float]:
        """Live pool utilization; never touches the network."""
        try:
            from backend.app.database import engine

            pool = engine.pool
            stats = {}
            for attr, key in (("size", "db_pool_size"), ("checkedout", "db_pool_checked_out"), ("overflow", "db_pool_overflow")):
                try:
                    value = getattr(pool, attr)() if callable(getattr(pool, attr, None)) else None  # type: ignore[arg-type]
                except Exception:
                    value = None
                if value is not None:
                    # QueuePool.overflow() may return a meaningless negative; only non-negative values are useful.
                    stats[key] = max(0.0, float(value))
            return stats
        except Exception:
            return {}

    def render(self) -> Dict[str, Any]:
        payload = self.snapshot()
        try:
            for key, value in self.db_pool_gauges().items():
                payload["gauges"][key] = value
        except Exception:
            pass
        return payload

    def error_counters(self) -> Dict[str, int]:
        with self._lock:
            return {k: v for k, v in self._counters.items() if k.startswith("http_5xx") or k.startswith("scheduler_job_failures")
                    or k.startswith("resume_generation_total") or k.startswith("opportunity_ingestion_runs_total")
                    or k.startswith("matching_evaluations_total") or k.startswith("db_pool_checkout_failures_total")}


metrics = MetricsRegistry()


def http_completed(method: str, route: str, status: int, duration_seconds: float, error: bool = False) -> None:
    metrics.inc("http_requests_total", {"method": bounded_method(method), "route": bounded_route(route), "status_class": status_class(status)})
    metrics.observe("http_request_duration_seconds", duration_seconds,
                    {"method": bounded_method(method), "route": bounded_route(route)})
    metrics.set_gauge("uptime_seconds", time.time() - metrics._started)
    if error or status >= 500:
        metrics.inc("http_5xx_total", {"method": bounded_method(method), "route": bounded_route(route)})
