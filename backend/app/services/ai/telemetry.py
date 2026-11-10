import time
import threading
from typing import Dict, Any, Optional
from datetime import datetime, timezone


class AITelemetryTracker:
    """
    Thread-safe in-memory usage, performance, and failure telemetry
    for Groq and local Ollama inference providers.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._stats = {
            "groq": {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_tokens": 0,
                "success_latency_ms": 0.0,
                "total_latency_ms": 0.0,
                "last_latency_ms": 0.0,
                "last_call_at": None,
                "last_error": None,
                "last_error_at": None
            },
            "ollama": {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_tokens": 0,
                "success_latency_ms": 0.0,
                "total_latency_ms": 0.0,
                "last_latency_ms": 0.0,
                "last_call_at": None,
                "last_error": None,
                "last_error_at": None
            }
        }
        self._task_breakdown: Dict[str, int] = {}

    def record_success(
        self,
        provider: str,
        task_name: str,
        latency_ms: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0
    ) -> None:
        p = provider.lower()
        with self._lock:
            if p not in self._stats:
                self._stats[p] = {
                    "total_requests": 0, "successful_requests": 0, "failed_requests": 0,
                    "total_prompt_tokens": 0, "total_completion_tokens": 0, "total_tokens": 0,
                    "success_latency_ms": 0.0, "total_latency_ms": 0.0, "last_latency_ms": 0.0,
                    "last_call_at": None, "last_error": None, "last_error_at": None
                }
            s = self._stats[p]
            s["total_requests"] += 1
            s["successful_requests"] += 1
            s["total_prompt_tokens"] += prompt_tokens
            s["total_completion_tokens"] += completion_tokens
            s["total_tokens"] += (prompt_tokens + completion_tokens)
            s["success_latency_ms"] += latency_ms
            s["total_latency_ms"] += latency_ms
            s["last_latency_ms"] = round(latency_ms, 2)
            s["last_call_at"] = datetime.now(timezone.utc).isoformat()

            self._task_breakdown[task_name] = self._task_breakdown.get(task_name, 0) + 1

    def record_failure(
        self,
        provider: str,
        task_name: str,
        latency_ms: float,
        error_message: str
    ) -> None:
        p = provider.lower()
        with self._lock:
            if p not in self._stats:
                self._stats[p] = {
                    "total_requests": 0, "successful_requests": 0, "failed_requests": 0,
                    "total_prompt_tokens": 0, "total_completion_tokens": 0, "total_tokens": 0,
                    "success_latency_ms": 0.0, "total_latency_ms": 0.0, "last_latency_ms": 0.0,
                    "last_call_at": None, "last_error": None, "last_error_at": None
                }
            s = self._stats[p]
            s["total_requests"] += 1
            s["failed_requests"] += 1
            s["total_latency_ms"] += latency_ms
            s["last_latency_ms"] = round(latency_ms, 2)
            s["last_error"] = error_message
            s["last_error_at"] = datetime.now(timezone.utc).isoformat()
            s["last_call_at"] = datetime.now(timezone.utc).isoformat()

    def get_metrics(self) -> Dict[str, Any]:
        with self._lock:
            result = {}
            for provider, s in self._stats.items():
                succ = s["successful_requests"]
                total = s["total_requests"]
                avg_lat = round(s["success_latency_ms"] / succ, 2) if succ > 0 else 0.0
                success_rate = round((succ / total * 100), 1) if total > 0 else 100.0

                result[provider] = {
                    "total_requests": total,
                    "successful_requests": succ,
                    "failed_requests": s["failed_requests"],
                    "success_rate_pct": success_rate,
                    "avg_latency_ms": avg_lat,
                    "last_latency_ms": s["last_latency_ms"],
                    "total_tokens": s["total_tokens"],
                    "prompt_tokens": s["total_prompt_tokens"],
                    "completion_tokens": s["total_completion_tokens"],
                    "last_call_at": s["last_call_at"],
                    "last_error": s["last_error"],
                    "last_error_at": s["last_error_at"]
                }
            result["task_breakdown"] = dict(self._task_breakdown)
            return result

    def reset(self) -> None:
        with self._lock:
            for s in self._stats.values():
                s["total_requests"] = 0
                s["successful_requests"] = 0
                s["failed_requests"] = 0
                s["total_prompt_tokens"] = 0
                s["total_completion_tokens"] = 0
                s["total_tokens"] = 0
                s["total_latency_ms"] = 0.0
                s["last_latency_ms"] = 0.0
                s["last_call_at"] = None
                s["last_error"] = None
                s["last_error_at"] = None
            self._task_breakdown.clear()


telemetry = AITelemetryTracker()
