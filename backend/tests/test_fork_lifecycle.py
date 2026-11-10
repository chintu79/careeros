"""
Deterministic disposable-fork lifecycle regression tests (Phase 3.0.5.1).

Uses schema-only forks where the data does not matter to keep the suite fast, and a
full-clone fork only where it is needed. Every fork created here is cleaned up by the
tests themselves and verified afterwards; nothing is silently skipped.
"""

import json
import os
import subprocess
import sys
import tempfile

import pytest
from sqlalchemy import create_engine, text

from backend.app.config import settings
from backend.app.testing import db_guard
from backend.app.testing import fork_lifecycle
from backend.app.testing.db_guard import TEST_DB_PREFIX, parse_pg_url
from backend.app.testing.fork_lifecycle import OwnedFork

@pytest.fixture(autouse=True)
def clean_fork_registry(tmp_path, monkeypatch):
    marker_dir = tmp_path / "fork-markers"
    monkeypatch.setenv("CAREEROS_FORK_MARKER_DIR", str(marker_dir))
    yield
    # Best-effort sweep of any markers this test left behind (non-destructive check).
    leftovers = list(marker_dir.glob(f"{TEST_DB_PREFIX}*.json")) if marker_dir.exists() else []
    for marker in leftovers:
        try:
            data = json.loads(marker.read_text())
        except Exception:
            data = {}
        name = data.get("database", marker.stem)
        prod = parse_pg_url(settings.ORIGINAL_DATABASE_URL)
        if fork_lifecycle.database_exists(prod, name):
            # The test must have cleaned its own fork; if it didn't, dispose and drop.
            try:
                OwnedFork(f"postgresql+psycopg://{prod.username}:{prod.password}@{prod.hostname}:{prod.port or 5432}/{name}", name, prod).cleanup(reason="test sweep")
            except Exception:
                pass
        try:
            marker.unlink()
        except OSError:
            pass


@pytest.fixture()
def original_prod_url():
    return settings.ORIGINAL_DATABASE_URL


def _exists(name):
    prod = parse_pg_url(settings.ORIGINAL_DATABASE_URL)
    return fork_lifecycle.database_exists(prod, name)


def test_provision_and_cleanup_success(original_prod_url):
    fork = fork_lifecycle.provision(original_prod_url, schema_only=True)
    assert fork.name.startswith(TEST_DB_PREFIX)
    assert _exists(fork.name)
    assert fork_lifecycle.read_marker(fork.name)["database"] == fork.name

    report = fork.cleanup(reason="test")
    assert report["success"] is True
    assert report["error"] is None
    assert not _exists(fork.name)
    assert not fork_lifecycle._marker_path(fork.name).exists()


def test_cleanup_is_idempotent(original_prod_url):
    fork = fork_lifecycle.provision(original_prod_url, schema_only=True)
    first = fork.cleanup(reason="test")
    second = fork.cleanup(reason="test")
    assert first["success"] is True
    assert second["success"] is True
    assert _exists(fork.name) is False


def test_cleanup_after_exception_in_workflow(original_prod_url):
    fork = fork_lifecycle.provision(original_prod_url, schema_only=True)
    try:
        raise ValueError("simulated workflow failure")
    except ValueError:
        report = fork.cleanup(reason="exception cleanup")
    assert report["success"] is True
    assert not _exists(fork.name)


def test_cleanup_with_active_owned_connection(original_prod_url):
    fork = fork_lifecycle.provision(original_prod_url, schema_only=True)
    engine = create_engine(fork.url)
    conn = engine.connect()
    conn.execute(text("SELECT 1"))
    report = fork.cleanup(reason="connection held")
    assert report["success"] is True
    assert report["remaining_connections"] == 0
    assert not _exists(fork.name)


def test_cleanup_with_multiple_owned_engines(original_prod_url):
    fork = fork_lifecycle.provision(original_prod_url, schema_only=True)
    engines = [create_engine(fork.url) for _ in range(3)]
    conns = [e.connect() for e in engines]
    for c in conns:
        c.execute(text("SELECT 1"))
    report = fork.cleanup(reason="multiple engines")
    assert report["success"] is True
    assert not _exists(fork.name)


def test_cleanup_never_touches_unrelated_forks(original_prod_url):
    fork_a = fork_lifecycle.provision(original_prod_url, schema_only=True)
    fork_b = fork_lifecycle.provision(original_prod_url, schema_only=True)
    engine_b = create_engine(fork_b.url)
    conn_b = engine_b.connect()
    try:
        report = fork_a.cleanup(reason="fork A teardown")
        assert report["success"] is True
        assert not _exists(fork_a.name)
        # Fork B and its connection are completely untouched.
        assert conn_b.execute(text("SELECT 1")).scalar() == 1
        assert _exists(fork_b.name)
    finally:
        engine_b.dispose()
        fork_b.cleanup(reason="fork B teardown")


def test_cleanup_refuses_non_prefixed_database():
    fork = OwnedFork(
        "postgresql+psycopg://u:p@localhost:5432/interniq",
        "interniq",
        parse_pg_url("postgresql+psycopg://u:p@localhost:5432/postgres"),
    )
    report = fork.cleanup(reason="must refuse")
    assert report["success"] is False
    assert "prefix" in report["error"]


def test_cleanup_refuses_unverified_ownership(original_prod_url, monkeypatch):
    fork = fork_lifecycle.provision(original_prod_url, schema_only=True)
    monkeypatch.setattr(db_guard, "_database_owner", lambda prod, name: "someone_else")
    report = fork.cleanup(reason="ownership unverified")
    assert report["success"] is False
    assert _exists(fork.name)  # untouched
    monkeypatch.undo()
    final = fork.cleanup(reason="ownership verified")
    assert final["success"] is True
    assert not _exists(fork.name)


def test_cleanup_failure_is_actionable(original_prod_url, monkeypatch):
    fork = fork_lifecycle.provision(original_prod_url, schema_only=True)
    boom = RuntimeError("boom without credentials")

    def explode(prod, name):
        raise boom

    monkeypatch.setattr(db_guard, "drop_test_database", explode)
    report = fork.cleanup(reason="failure reporting")
    assert report["success"] is False
    assert "guarded_drop" in report["error"]
    assert "boom without credentials" in report["error"]
    assert "postgresql" not in report["error"]
    assert "recovery" in report and "fork_lifecycle --recover" in report["recovery"]
    assert fork_lifecycle._marker_path(fork.name).exists()  # kept for recovery
    monkeypatch.undo()
    final = fork.cleanup(reason="post-failure recovery")
    assert final["success"] is True


def test_partial_provisioning_failure_drops_fork(original_prod_url, monkeypatch):
    """pg_dump failure after CREATE DATABASE must drop the partially created fork."""
    class Failed:
        returncode = 1
        stdout = ""
        stderr = "simulated pg_dump failure"

    real_run = subprocess.run

    def fake_run(cmd, **kwargs):
        if cmd and cmd[0] == "pg_dump":
            return Failed()
        return real_run(cmd, **kwargs)

    before = set()
    engine = create_engine(original_prod_url)
    try:
        with engine.connect() as conn:
            before = {row[0] for row in conn.execute(text("SELECT datname FROM pg_database"))}
    finally:
        engine.dispose()

    monkeypatch.setattr(db_guard.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="Command failed"):
        db_guard.make_disposable_pg_database(original_prod_url)
    monkeypatch.undo()

    engine = create_engine(original_prod_url)
    try:
        with engine.connect() as conn:
            after = {row[0] for row in conn.execute(text("SELECT datname FROM pg_database"))}
    finally:
        engine.dispose()
    assert after == before
    assert list(__import__("pathlib").Path(tempfile.gettempdir()).glob("careeros-test-backup-*.dump")) == []


def test_interrupted_workflow_recovery(tmp_path, monkeypatch, original_prod_url):
    monkeypatch.setenv("CAREEROS_FORK_MARKER_DIR", str(tmp_path / "markers"))
    prod = parse_pg_url(original_prod_url)
    child = f"""
import os, sys
sys.path.insert(0, "/home/krishna/Desktop/interniq")
from backend.app.testing import fork_lifecycle
fork = fork_lifecycle.provision({original_prod_url!r}, schema_only=True)
print(f"FORK:{{fork.name}}", flush=True)
import sqlalchemy
engine = sqlalchemy.create_engine(fork.url)
conn = engine.connect()
os._exit(1)
"""
    result = subprocess.run(
        [sys.executable, "-c", child],
        env=dict(os.environ, CAREEROS_FORK_MARKER_DIR=str(tmp_path / "markers")),
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 1
    fork_name = next(line[5:] for line in result.stdout.splitlines() if line.startswith("FORK:"))
    assert _exists(fork_name)
    # Simulated crash left everything behind; recovery must drop it deterministically.
    recover_report = fork_lifecycle.recover_stale_forks(confirm=True)
    assert any(entry["database"] == fork_name and entry["dropped"] for entry in recover_report)
    assert not _exists(fork_name)


def test_recovery_refuses_marker_without_server_match(tmp_path, monkeypatch, original_prod_url):
    monkeypatch.setenv("CAREEROS_FORK_MARKER_DIR", str(tmp_path / "markers"))
    marker = fork_lifecycle._marker_path(f"{TEST_DB_PREFIX}zzmarker")
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({
        "database": f"{TEST_DB_PREFIX}zzmarker",
        "host": "other-host.example.com",
        "port": 5432,
        "username": "someoneelse",
        "tool": fork_lifecycle.TOOL,
        "created_utc": "2026-11-09T00:00:00Z",
    }))
    report = fork_lifecycle.recover_stale_forks(confirm=True)
