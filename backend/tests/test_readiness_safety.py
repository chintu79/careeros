"""
Readiness/liveness safety regression tests (3.0.4.1).

- Liveness never touches the database or filesystem.
- Readiness is bounded, repeatable, and leaves no probe artifacts.
- Scheduler checks read state only and never trigger a discovery cycle.
- Optional AI providers never gate readiness.
- Production responses expose no internal check details.
"""

import os
import time
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.main import app
from backend.app.services import discovery_scheduler
from backend.app.services import readiness

client = TestClient(app)


@pytest.fixture
def ready_environment(monkeypatch):
    """Strong secrets + initialized scheduler; restore global state afterwards."""
    monkeypatch.setattr(settings, "SECRET_KEY", "s" * 40)
    monkeypatch.setattr(settings, "CAREEROS_TOKEN_SECRET", None)
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")
    state = discovery_scheduler.SCHEDULER_STATE
    previous = dict(state)
    state["last_check_at"] = datetime.utcnow().isoformat()
    try:
        yield state
    finally:
        state.clear()
        state.update(previous)


def _probe_files(directory: str) -> set:
    try:
        return {name for name in os.listdir(directory) if name.startswith(".readiness-")}
    except FileNotFoundError:
        return set()


def test_liveness_is_fast_and_dependency_free(monkeypatch):
    storage = readiness._storage_dir()
    before = _probe_files(storage)
    # Point readiness at a dead database; liveness must not care.
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:1/nodb")
    started = time.monotonic()
    response = client.get("/api/health")
    elapsed = time.monotonic() - started
    assert response.status_code == 200
    assert response.json()["status"] == "alive"
    assert elapsed < 2.0
    assert _probe_files(storage) == before


def test_readiness_ready_when_dependencies_are_healthy(ready_environment):
    checks = readiness.run_checks()
    assert checks["database"] == "ok"
    assert checks["extension:vector"] == "ok"
    assert checks["secret:SECRET_KEY"] == "ok"
    assert checks["storage:resumes"] == "ok"
    assert checks["scheduler"] == "ok"
    assert readiness.is_ready(checks) is True


def test_repeated_readiness_probes_leave_no_artifacts(ready_environment):
    storage = readiness._storage_dir()
    assert _probe_files(storage) == set()
    for _ in range(5):
        checks = readiness.run_checks()
        assert readiness.is_ready(checks) is True
    assert _probe_files(storage) == set()


def test_storage_probe_cleans_up_after_itself(tmp_path, monkeypatch):
    monkeypatch.setattr(readiness, "_storage_dir", lambda: str(tmp_path))
    for _ in range(3):
        assert readiness.check_storage() == {"storage:resumes": "ok"}
    assert list(tmp_path.iterdir()) == []


def test_storage_failure_is_reported(monkeypatch, tmp_path):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    monkeypatch.setattr(readiness, "_storage_dir", lambda: str(blocker / "sub"))
    checks = readiness.check_storage()
    assert checks == {"storage:resumes": "error"}
    assert readiness.is_ready(checks) is False


def test_scheduler_readiness_reads_state_without_triggering_work(monkeypatch):
    state = discovery_scheduler.SCHEDULER_STATE
    previous = dict(state)
    triggered = []

    def forbidden(*args, **kwargs):
        triggered.append(True)
        raise AssertionError("readiness must not trigger discovery work")

    monkeypatch.setattr(discovery_scheduler, "run_connector_sync", forbidden)
    try:
        state["last_check_at"] = None
        assert readiness.check_scheduler() == {"scheduler": "starting"}
        assert readiness.is_ready({"scheduler": "starting"}) is False

        state["last_check_at"] = datetime.utcnow().isoformat()
        assert readiness.check_scheduler() == {"scheduler": "ok"}
        assert readiness.is_ready({"scheduler": "ok"}) is True
    finally:
        state.clear()
        state.update(previous)
    assert triggered == []


def test_optional_ai_provider_outage_does_not_gate(ready_environment, monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")
    checks = readiness.run_checks()
    assert checks["optional:groq"] == "not_configured"
    assert readiness.is_ready(checks) is True

    # A configured but unreachable provider is still optional: readiness does not call it.
    monkeypatch.setattr(settings, "GROQ_API_KEY", "configured-but-provider-down")
    checks = readiness.run_checks()
    assert checks["optional:groq"] == "configured"
    assert readiness.is_ready(checks) is True


def test_database_outage_degrades_readiness_but_not_liveness(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:1/nodb")
    started = time.monotonic()
    checks = readiness.run_checks()
    elapsed = time.monotonic() - started
    assert checks["database"] == "error"
    assert checks["extensions"] == "error"
    assert readiness.is_ready(checks) is False
    assert elapsed < 5.0
    assert client.get("/api/health").status_code == 200


def test_readiness_endpoint_returns_500_family_when_not_ready(monkeypatch):
    monkeypatch.setattr(readiness, "run_checks", lambda: {"database": "error"})
    response = client.get("/api/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


def test_readiness_endpoint_ready_payload_in_development(monkeypatch):
    monkeypatch.setattr(readiness, "run_checks", lambda: {"database": "ok", "optional:groq": "configured"})
    response = client.get("/api/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"


def test_production_readiness_hides_internal_details(monkeypatch):
    # main.py imports the singleton at module scope; only is_production is consulted here.
    monkeypatch.setattr("backend.app.main.settings", SimpleNamespace(is_production=True))
    monkeypatch.setattr(readiness, "run_checks", lambda: {"database": "error", "storage:resumes": "error"})
    response = client.get("/api/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
    assert "checks" not in response.text
    assert "database" not in response.text
