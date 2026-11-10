"""
Safety regression tests for the migration guard, the migration/backfill CLIs and
the migration audit trail.

Rules under test (3.0.4.1):
- --confirm alone can never execute anything.
- production targets require --target <fingerprint>, --authorize-production and
  CAREEROS_MIGRATION_AUTHORIZATION=<fingerprint>.
- unknown targets refuse.
- dry-runs never mutate schema, audit or business data.
- every execution writes a start/finish audit record without credentials.
- fork provisioning failures raise; they never fall back to production.

All mutation tests run against the disposable fork created by conftest.
"""

import uuid

import pytest
from sqlalchemy import text

from backend.app.config import settings
from backend.app.database import engine
from backend.app.services import migration_guard as guard
from backend.app.testing import db_guard
from backend.ops import backfill_matches as backfill_cli
from backend.ops import migrate as migrate_cli

PROD_URL = "postgresql+psycopg://ops_user:s3cret-pass@db.example.com:5432/interniq"
PROD_FP = guard.fingerprint("db.example.com", 5432, "interniq")
UNKNOWN_REMOTE_URL = "postgresql+psycopg://ops_user:s3cret-pass@10.9.9.9:5432/appdb"


def _fork_url() -> str:
    url = settings.DATABASE_URL
    assert "/careeros_test_" in url, "tests must run against the disposable fork"
    return url


def _audit_rows(migration_id: str = None):
    with engine.connect() as conn:
        exists = conn.execute(text("SELECT to_regclass('public.migration_audit_log')")).scalar()
        if not exists:
            return []
        sql = (
            "SELECT migration_id, target_environment, target_kind, target_fingerprint, "
            "target_display, authorization_method, success, applied_changes, "
            "started_at, completed_at, error_summary FROM migration_audit_log"
        )
        if migration_id:
            sql += " WHERE migration_id = :mid"
            rows = conn.execute(text(sql + " ORDER BY id DESC"), {"mid": migration_id}).mappings().all()
        else:
            rows = conn.execute(text(sql + " ORDER BY id DESC")).mappings().all()
    return rows


# ---------------------------------------------------------------------------
# Production-target refusal
# ---------------------------------------------------------------------------

def test_production_target_refused_by_confirm_alone(capsys):
    rc = migrate_cli.run(["--confirm"], database_url=PROD_URL, environ={})
    captured = capsys.readouterr()
    assert rc == 3, captured.err
    assert "REFUSED" in captured.err
    assert "s3cret-pass" not in captured.err
    assert "s3cret-pass" not in captured.out


def test_production_target_requires_separate_authorization(capsys):
    rc = migrate_cli.run(
        ["--confirm", "--target", PROD_FP], database_url=PROD_URL, environ={}
    )
    captured = capsys.readouterr()
    assert rc == 3
    assert "authorize-production" in captured.err
    assert "CAREEROS_MIGRATION_AUTHORIZATION" in captured.err


def test_production_authorization_env_missing(capsys):
    rc = migrate_cli.run(
        ["--confirm", "--target", PROD_FP, "--authorize-production"],
        database_url=PROD_URL,
        environ={},
    )
    captured = capsys.readouterr()
    assert rc == 3
    assert "CAREEROS_MIGRATION_AUTHORIZATION is not set" in captured.err


def test_production_authorization_token_mismatch(capsys):
    rc = migrate_cli.run(
        ["--confirm", "--target", PROD_FP, "--authorize-production"],
        database_url=PROD_URL,
        environ={"CAREEROS_MIGRATION_AUTHORIZATION": "deadbeefdeadbeef"},
    )
    captured = capsys.readouterr()
    assert rc == 3
    assert "does not match" in captured.err


def test_production_authorization_cannot_bypass_engine_binding(capsys):
    """Even a fully authorized CLI cannot run if the engine binds another database."""
    rc = migrate_cli.run(
        ["--confirm", "--target", PROD_FP, "--authorize-production"],
        database_url=PROD_URL,
        environ={"CAREEROS_MIGRATION_AUTHORIZATION": PROD_FP},
    )
    captured = capsys.readouterr()
    assert rc == 3
    assert "engine binding does not match" in captured.err
    assert "s3cret-pass" not in captured.err


def test_production_token_matches_target_only(capsys):
    """A token for a different production database must not authorize this one."""
    other_fp = guard.fingerprint("db.example.com", 5432, "other_prod")
    rc = migrate_cli.run(
        ["--confirm", "--target", PROD_FP, "--authorize-production"],
        database_url=PROD_URL,
        environ={"CAREEROS_MIGRATION_AUTHORIZATION": other_fp},
    )
    assert rc == 3
    assert "does not match" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Target verification / unknown targets
# ---------------------------------------------------------------------------

def test_confirm_without_target_is_refused_on_test_target(capsys):
    rc = migrate_cli.run(["--confirm"], database_url=_fork_url(), environ={})
    captured = capsys.readouterr()
    assert rc == 3
    assert "explicit target verification required" in captured.err


def test_incorrect_target_confirmation_is_refused(capsys):
    rc = migrate_cli.run(
        ["--confirm", "--target", "0000000000000000"],
        database_url=_fork_url(),
        environ={},
    )
    assert rc == 3
    assert "target fingerprint mismatch" in capsys.readouterr().err


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///tmp/opencode/not-postgres.db",
        "postgresql+psycopg://u:p@db.example.com:5432/",
        "",
    ],
)
def test_unrecognized_target_is_refused(capsys, url):
    rc = migrate_cli.run(["--confirm", "--target", PROD_FP], database_url=url, environ={})
    assert rc == 3
    assert "REFUSED" in capsys.readouterr().err


def test_unknown_remote_host_is_classified_as_production():
    target = guard.resolve_target(UNKNOWN_REMOTE_URL, "development")
    assert target.kind == "production"
    with pytest.raises(guard.MigrationRefused):
        guard.authorize(
            target, confirm=True, target_fingerprint=target.fingerprint,
            authorize_production=False, environ={},
        )


def test_local_development_target_requires_confirm_and_target():
    target = guard.resolve_target(
        "postgresql+psycopg://u:p@localhost:5432/careeros_dev", "development"
    )
    assert target.kind == "development"
    with pytest.raises(guard.MigrationRefused):
        guard.authorize(
            target, confirm=False, target_fingerprint=target.fingerprint,
            authorize_production=False, environ={},
        )
    method = guard.authorize(
        target, confirm=True, target_fingerprint=target.fingerprint,
        authorize_production=False, environ={},
    )
    assert method == "confirm+target"


def test_fork_provisioning_failure_raises_and_never_falls_back(monkeypatch):
    class Failed:
        returncode = 1
        stdout = ""
        stderr = "simulated psql failure"

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return Failed()

    monkeypatch.setattr(db_guard.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="Command failed"):
        db_guard.make_disposable_pg_database(PROD_URL)
    # It failed at CREATE DATABASE; no production URL can be returned from this path.
    assert calls and calls[0][0] == "psql"


def test_test_database_prefix_and_host_checks_intact():
    with pytest.raises(RuntimeError, match="must start with"):
        db_guard.assert_disposable_pg_url(
            "postgresql+psycopg://u:p@db.example.com:5432/interniq",
            "postgresql+psycopg://u:p@db.example.com:5432/interniq",
        )
    with pytest.raises(RuntimeError, match="same host"):
        db_guard.assert_disposable_pg_url(
            "postgresql+psycopg://u:p@otherhost:5432/careeros_test_abc",
            "postgresql+psycopg://u:p@db.example.com:5432/interniq",
        )
    parsed = db_guard.assert_disposable_pg_url(
        "postgresql+psycopg://u:p@db.example.com:5432/careeros_test_abc",
        "postgresql+psycopg://u:p@db.example.com:5432/interniq",
    )
    assert parsed.path.lstrip("/") == "careeros_test_abc"


def test_engine_binding_assertion_refuses_foreign_target():
    foreign = guard.MigrationTarget(
        host="db.example.com", port=5432, database="interniq",
        environment="production", kind="production", fingerprint=PROD_FP,
    )
    with pytest.raises(guard.MigrationRefused, match="engine binding"):
        guard.assert_engine_matches_target(engine, foreign)


# ---------------------------------------------------------------------------
# Dry-run guarantees
# ---------------------------------------------------------------------------

def test_dry_run_prints_fingerprint_without_credentials(capsys):
    rc = migrate_cli.run(["--dry-run"], database_url=PROD_URL, environ={})
    captured = capsys.readouterr()
    assert rc == 0
    assert PROD_FP in captured.out
    assert "interniq@db.example.com:5432" in captured.out
    assert "s3cret-pass" not in captured.out
    assert "ops_user" not in captured.out


def test_migration_dry_run_does_not_mutate_fork():
    fork = _fork_url()
    target = guard.resolve_target(fork, settings.ENVIRONMENT)
    before_schema = guard._schema_snapshot(engine)
    before_audit = len(_audit_rows())

    rc = migrate_cli.run(["--dry-run"], database_url=fork, environ={})

    assert rc == 0
    assert guard._schema_snapshot(engine) == before_schema
    assert len(_audit_rows()) == before_audit


def test_backfill_dry_run_does_not_write_rows():
    fork = _fork_url()
    with engine.connect() as conn:
        before = conn.execute(text("SELECT count(*) FROM candidate_opportunity_matches")).scalar()
        audit_before = len(_audit_rows())

    rc = backfill_cli.run(["--dry-run"], database_url=fork, environ={})

    with engine.connect() as conn:
        after = conn.execute(text("SELECT count(*) FROM candidate_opportunity_matches")).scalar()
    assert rc == 0
    assert after == before
    assert len(_audit_rows()) == audit_before


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------

def test_isolated_test_migration_succeeds_and_is_audited():
    fork = _fork_url()
    target = guard.resolve_target(fork, settings.ENVIRONMENT)
    rc = migrate_cli.run(
        ["--confirm", "--target", target.fingerprint], database_url=fork, environ={}
    )
    assert rc == 0

    rows = _audit_rows("schema-migrations")
    assert rows, "migration execution left no audit record"
    row = rows[0]
    assert row["target_environment"] == "test"
    assert row["target_kind"] == "test"
    assert row["target_fingerprint"] == target.fingerprint
    assert row["authorization_method"] == "confirm+target"
    assert row["success"] is True
    assert row["started_at"] is not None
    assert row["completed_at"] is not None
    assert row["target_display"].startswith(f"{target.database}@{target.host}:{target.port}")
    assert "s3cret" not in row["target_display"]


def test_audit_records_failed_execution():
    fork = _fork_url()
    target = guard.resolve_target(fork, settings.ENVIRONMENT)
    auth = guard.authorize(
        target, confirm=True, target_fingerprint=target.fingerprint,
        authorize_production=False, environ={},
    )
    migration_id = f"failure-test-{uuid.uuid4().hex[:8]}"

    def boom():
        raise RuntimeError("simulated migration failure")

    with pytest.raises(RuntimeError):
        guard.execute_authorized(
            engine, migration_id=migration_id, target=target,
            authorization_method=auth, action=boom,
        )

    rows = _audit_rows(migration_id)
    assert rows
    row = rows[0]
    assert row["success"] is False
    assert row["completed_at"] is not None
    assert "simulated migration failure" in row["error_summary"]


def test_sanitize_strips_connection_credentials():
    dirty = "OperationalError: failed postgresql://ops_user:s3cret-pass@db.example.com:5432/interniq"
    cleaned = guard.sanitize(dirty)
    assert "s3cret-pass" not in cleaned
    assert "://***@" in cleaned
