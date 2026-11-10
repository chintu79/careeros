"""
Observability regression tests (Phase 3.0.6):
- structured JSON logging + redaction
- request-id correlation & concurrency isolation
- route-template cardinality
- metrics correctness and internal endpoint access control
- scheduler failure instrumentation
- database pool metrics
- diagnostics sanitization
Runs on the disposable fork; production is never touched.
"""

import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.main import app
from backend.app import observability
from backend.app.observability import bind_request_context, clear_request_context, current_request_id
from backend.app.observability.logging_config import JsonFormatter, redact
from backend.app.observability.metrics import metrics, bounded_route
from backend.app.observability.diagnostics import build_snapshot

client = TestClient(app)


# ---------------------------------------------------------------------------
# Request correlation
# ---------------------------------------------------------------------------

def test_request_id_generated_and_returned():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) >= 8


def test_valid_inbound_request_id_is_preserved():
    response = client.get("/api/health", headers={"X-Request-ID": "req-0123456789abcdef"})
    assert response.headers["x-request-id"] == "req-0123456789abcdef"


def test_invalid_inbound_request_id_is_replaced():
    response = client.get("/api/health", headers={"X-Request-ID": "bad id with spaces & junk"})
    assert response.headers["x-request-id"] != "bad id with spaces & junk"
    assert len(response.headers["x-request-id"]) >= 8


def test_request_id_concurrency_isolation():
    ids = [f"req-{n:08x}" for n in range(32)]
    barrier = threading.Barrier(len(ids))

    def worker(expected):
        bind_request_context(expected, "GET", "/api/test")
        barrier.wait()
        try:
            assert current_request_id() == expected
        finally:
            clear_request_context()

    threads = [threading.Thread(target=worker, args=(rid,)) for rid in ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert clear_request_context() is None


def test_request_id_in_api_response_for_protected_route():
    response = client.get("/api/opportunities/12345")
    # Auth override from conftest supplies user_id=1 for most functional suites.
    assert "x-request-id" in response.headers


# ---------------------------------------------------------------------------
# Logging redaction
# ---------------------------------------------------------------------------

def test_redact_masks_secret_keys_and_connection_strings():
    dirty = {
        "password": "supersecret",
        "nested": {"api_key": "abc123", "safe": "keep"},
        "url": "postgresql+psycopg://ops:dbpass@db.example.com:5432/interniq",
        "query": "https://example.com/page?access_token=leaktoken&keep=1",
        "Authorization": "Bearer abc.def.ghi",
    }
    cleaned = redact(dirty)
    assert cleaned["password"] == "***"
    assert cleaned["nested"]["api_key"] == "***"
    assert cleaned["nested"]["safe"] == "keep"
    assert "dbpass" not in json.dumps(cleaned)
    assert "abc123" not in json.dumps(cleaned)
    assert "leaktoken" not in json.dumps(cleaned)
    assert cleaned["Authorization"] == "***"
    assert "postgresql+psycopg://***@" in cleaned["url"]
    assert "keep=1" in cleaned["query"]


def test_redact_exception_text_never_leaks_credentials():
    exc_text = "OperationalError: could not connect to postgresql://u:supersecretpw@db.example.com:5432/interniq"
    cleaned = redact(exc_text)
    assert "supersecretpw" not in cleaned
    assert "://***@" in cleaned


def test_json_formatter_emits_structured_record():
    record = logging.LogRecord("interniq.test", logging.INFO, "test.py", 10, "test message body", (), None)
    record.event = "test_event"
    record.extra_number = 42
    line = JsonFormatter().format(record)
    payload = json.loads(line)
    for key in ("ts", "level", "service", "environment", "event", "logger"):
        assert key in payload
    assert payload["service"] == "interniq-discovery-engine"
    assert payload["environment"] == os.environ.get("ENVIRONMENT", "development").lower()
    assert payload["event"] == "test_event"
    assert payload["extra_number"] == 42


def test_json_formatter_redacts_extras():
    record = logging.LogRecord("interniq.test", logging.ERROR, "test.py", 10, "msg", (), None)
    record.event = "op"
    record.extra = {"password": "pw-value", "dsn": "postgresql://u:p@h/db"}
    line = JsonFormatter().format(record)
    assert "pw-value" not in line


# ---------------------------------------------------------------------------
# Metrics correctness & cardinality
# ---------------------------------------------------------------------------

def test_metrics_count_and_duration_records():
    before = dict(metrics.snapshot()["counters"])
    metrics.inc("http_requests_total", {"method": "GET", "route": "/api/test", "status_class": "2xx"})
    metrics.observe("http_request_duration_seconds", 0.05, {"method": "GET", "route": "/api/test"})
    after = metrics.snapshot()
    assert after["counters"]["http_requests_total{method=GET,route=/api/test,status_class=2xx}"] == before.get(
        "http_requests_total{method=GET,route=/api/test,status_class=2xx}", 0) + 1
    summary = after["summaries"]["http_request_duration_seconds{method=GET,route=/api/test}"]
    assert summary["count"] >= 1
    assert summary["sum_seconds"] >= 0.05


def test_bounded_route_rejects_unbounded_values():
    assert bounded_route("/api/opportunities/{opportunity_id}") == "/api/opportunities/{opportunity_id}"
    assert bounded_route("/raw/data?leak=yes") == "other"
    assert bounded_route("/totally/not valid!") == "other"


def test_route_template_used_not_raw_id(monkeypatch):
    """The /api/opportunities/{id} route must be logged/metriced as the template."""
    client.get("/api/opportunities/424242")
    keys = list(metrics.snapshot()["counters"].keys())
    assert not any("/api/opportunities/424242" in key for key in keys)
    assert any("route=/opportunities/{id}" in key for key in keys)


# ---------------------------------------------------------------------------
# Internal endpoints & access control
# ---------------------------------------------------------------------------

def test_internal_metrics_disabled_without_token(monkeypatch):
    monkeypatch.delenv("CAREEROS_DIAGNOSTICS_TOKEN", raising=False)
    response = client.get("/api/internal/metrics")
    assert response.status_code == 404
    response = client.get("/api/internal/diagnostics")
    assert response.status_code == 404


def test_internal_metrics_requires_bearer(monkeypatch):
    monkeypatch.setenv("CAREEROS_DIAGNOSTICS_TOKEN", "test-operator-token-0123456789")
    assert client.get("/api/internal/metrics").status_code == 401
    assert client.get("/api/internal/diagnostics").status_code == 401
    response = client.get("/api/internal/metrics", headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401


def test_internal_metrics_and_diagnostics_happy_path(monkeypatch):
    monkeypatch.setenv("CAREEROS_DIAGNOSTICS_TOKEN", "test-operator-token-0123456789")
    response = client.get("/api/internal/metrics", headers={"Authorization": "Bearer test-operator-token-0123456789"})
    assert response.status_code == 200
    body = response.json()
    assert "counters" in body and "gauges" in body and "summaries" in body
    diag = client.get("/api/internal/diagnostics", headers={"Authorization": "Bearer test-operator-token-0123456789"})
    assert diag.status_code == 200
    diag_text = diag.text
    for banned in ("postgresql", "://", "password", "DATABASE_URL", "54322"):
        assert banned not in diag_text
    diag_json = diag.json()
    assert diag_json["service"] == "interniq-discovery-engine"
    assert "dependencies" in diag_json and "metrics" in diag_json


# ---------------------------------------------------------------------------
# Scheduler instrumentation
# ---------------------------------------------------------------------------

def test_scheduler_success_and_failure_instrumentation(monkeypatch):
    from backend.app.services import discovery_scheduler

    async def ok_impl(source_name, db=None, timeout=30.0):
        return {"ok": True}

    async def boom_impl(source_name, db=None, timeout=30.0):
        raise RuntimeError("sync exploded without credentials")

    before_fail = discovery_scheduler.SCHEDULER_STATE["failure_count"]
    monkeypatch.setattr(discovery_scheduler, "_run_connector_sync_impl", ok_impl)
    discovery_scheduler.SCHEDULER_STATE["is_running_cycle"] = False
    import asyncio
    result = asyncio.run(discovery_scheduler.run_connector_sync("test-source", timeout=5))
    assert result == {"ok": True}
    assert discovery_scheduler.SCHEDULER_STATE["last_success_at"] is not None

    monkeypatch.setattr(discovery_scheduler, "_run_connector_sync_impl", boom_impl)
    with pytest.raises(RuntimeError):
        asyncio.run(discovery_scheduler.run_connector_sync("test-source", timeout=5))
    assert discovery_scheduler.SCHEDULER_STATE["failure_count"] == before_fail + 1
    assert discovery_scheduler.SCHEDULER_STATE["last_failure_at"] is not None
    run_failures = metrics.snapshot()["counters"].get("scheduler_job_failures_total{job=connector_sync}", 0)
    ingestion_failures = metrics.snapshot()["counters"].get("opportunity_ingestion_runs_total{outcome=failure}", 0)
    assert run_failures >= 1 and ingestion_failures >= 1


# ---------------------------------------------------------------------------
# Database pool metrics
# ---------------------------------------------------------------------------

def test_pool_gauges_and_checkout_counters():
    from backend.app.database import SessionLocal, engine
    from sqlalchemy import text

    before = metrics.snapshot()["counters"].get("db_pool_checkouts_total", 0)
    session = SessionLocal()
    session.execute(text("SELECT 1"))
    session.close()
    after = metrics.snapshot()["counters"].get("db_pool_checkouts_total", 0)
    assert after >= before + 1
    pool_stats = metrics.db_pool_gauges()
    assert pool_stats.get("db_pool_size", 0) >= 0
    assert "db_pool_checked_out" in metrics.render()["gauges"]


def test_get_db_checkout_failure_counter(monkeypatch):
    import backend.app.database as db_module

    real = db_module.SessionLocal

    def explode():
        raise RuntimeError("pool exhausted for test")

    monkeypatch.setattr(db_module, "SessionLocal", explode)
    from backend.app.observability.metrics import metrics as test_metrics

    before = test_metrics.snapshot()["counters"].get("db_pool_checkout_failures_total", 0)
    try:
        next(db_module.get_db())
    except Exception:
        pass
    after = test_metrics.snapshot()["counters"].get("db_pool_checkout_failures_total", 0)
    assert after >= before + 1
    monkeypatch.setattr(db_module, "SessionLocal", real)


# ---------------------------------------------------------------------------
# Rate limit instrumentation
# ---------------------------------------------------------------------------

def test_rate_limit_rejection_is_counted(monkeypatch):
    import backend.app.services.rate_limit as rl

    def false_check(db, key, rule):
        return False, 0.0, 42

    monkeypatch.setattr(rl, "_take", false_check)
    try:
        asyncio = __import__("asyncio")

        async def invoke():
            dependency = rl.rate_limited("ai")
            from fastapi import HTTPException
            try:
                await dependency(type("R", (), {})(), object(), 1)  # type: ignore[arg-type]
                return False
            except HTTPException as exc:
                return exc.status_code == 429

        rejected = asyncio.run(invoke())
        assert rejected
        total = metrics.snapshot()["counters"].get("rate_limit_rejections_total{policy=ai,scope=user}", 0)
        assert total >= 1
    finally:
        pass
