import pytest
import asyncio
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.discovery_scheduler import (
    get_scheduler_status,
    toggle_scheduler_state,
    fetch_with_retry,
    ACTIVE_SYNC_LOCKS
)

client = TestClient(app)


def test_scheduler_status_endpoint():
    """Verify scheduler status API reports background worker configuration."""
    resp = client.get("/api/sources/scheduler/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "is_enabled" in data
    assert "check_interval_seconds" in data
    assert "default_sync_interval_hours" in data
    assert "active_locks" in data


def test_scheduler_toggle_endpoint():
    """Verify pausing and re-enabling the background synchronization worker."""
    # Pause
    res_pause = client.post("/api/sources/scheduler/toggle?enabled=false")
    assert res_pause.status_code == 200
    assert res_pause.json()["is_enabled"] is False

    status_paused = client.get("/api/sources/scheduler/status").json()
    assert status_paused["is_enabled"] is False

    # Resume
    res_resume = client.post("/api/sources/scheduler/toggle?enabled=true")
    assert res_resume.status_code == 200
    assert res_resume.json()["is_enabled"] is True

    status_resumed = client.get("/api/sources/scheduler/status").json()
    assert status_resumed["is_enabled"] is True


@pytest.mark.asyncio
async def test_fetch_with_retry_exponential_backoff():
    """Verify exponential backoff retries on transient errors and succeeds on recovery."""
    attempts = 0

    async def transient_fail():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            import httpx
            raise httpx.ConnectError("Transient connection drop")
        return [{"title": "Success on attempt 3"}]

    result = await fetch_with_retry(transient_fail, max_retries=3, base_delay=0.01)
    assert len(result) == 1
    assert result[0]["title"] == "Success on attempt 3"
    assert attempts == 3


@pytest.mark.asyncio
async def test_overlapping_job_lock_protection():
    """Verify simultaneous executions for the same source are locked and rejected."""
    source_key = "test_source_lock"
    ACTIVE_SYNC_LOCKS.add(source_key)
    try:
        from backend.app.services.discovery_scheduler import run_connector_sync
        res = await run_connector_sync("test_source_lock")
        assert res["status"] == "already_running"
    finally:
        ACTIVE_SYNC_LOCKS.discard(source_key)
