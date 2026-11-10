"""
Unit/integration tests for the disposable PostgreSQL test-database guard and
lifecycle. Runs inside the disposable fork created by conftest; never touches
the production database.
"""

import os
import uuid

import sqlalchemy as sa

import pytest

from backend.app.config import settings
from backend.app.testing import db_guard
from backend.app.testing.db_guard import (
    TEST_DB_PREFIX,
    assert_disposable_pg_url,
    is_test_database_name,
    parse_pg_url,
    cleanup_stale_test_databases,
)


def _original_prod_url() -> str:
    return getattr(settings, "ORIGINAL_DATABASE_URL", None) or settings.DATABASE_URL


def test_parse_pg_url_postgresql():
    u = parse_pg_url("postgresql+psycopg://u:p@dbhost:5432/mytestdb")
    assert u.hostname == "dbhost"
    assert u.port == 5432
    assert u.path.lstrip("/") == "mytestdb"


def test_parse_pg_url_rejects_sqlite():
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        parse_pg_url("sqlite:///tmp/careeros-test.db")


def test_is_test_database_name():
    assert is_test_database_name("careeros_test_abc123") is True
    assert is_test_database_name("") is False
    assert is_test_database_name("interniq") is False


def test_guard_accepts_valid_test_url():
    u = assert_disposable_pg_url(
        "postgresql+psycopg://u:p@dbhost:5432/careeros_test_abc123",
        "postgresql+psycopg://u:p@dbhost:5432/interniq",
    )
    assert u.hostname == "dbhost"


def test_guard_refuses_identical_urls():
    with pytest.raises(RuntimeError):
        assert_disposable_pg_url(
            "postgresql+psycopg://u:p@dbhost:5432/interniq",
            "postgresql+psycopg://u:p@dbhost:5432/interniq",
        )


def test_guard_refuses_cross_host():
    with pytest.raises(RuntimeError, match="same host"):
        assert_disposable_pg_url(
            "postgresql+psycopg://u:p@otherhost:5432/careeros_test_abc",
            "postgresql+psycopg://u:p@dbhost:5432/interniq",
        )


def test_guard_refuses_wrong_prefix():
    with pytest.raises(RuntimeError, match="must start with"):
        assert_disposable_pg_url(
            "postgresql+psycopg://u:p@dbhost:5432/interniq_test",
            "postgresql+psycopg://u:p@dbhost:5432/interniq",
        )


def test_database_url_is_a_test_database():
    test_url = os.environ.get("DATABASE_URL", "")
    assert test_url.startswith(("postgresql://", "postgresql+psycopg://"))
    test_name = test_url.rsplit("/", 1)[-1]
    assert test_name.startswith(TEST_DB_PREFIX), f"DATABASE_URL points at non-test database: {test_name}"
    assert test_name != _original_prod_url().rsplit("/", 1)[-1]


def test_prod_database_under_test_url_is_different():
    prod_name = _original_prod_url().rsplit("/", 1)[-1]
    test_name = os.environ["DATABASE_URL"].rsplit("/", 1)[-1]
    assert prod_name != test_name


def test_schema_is_valid_in_disposable_database():
    from backend.app.database import engine
    with engine.connect() as conn:
        res = conn.execute(sa.text(
            "select table_name from information_schema.tables where table_schema='public'"
        ))
        tables = {r[0] for r in res}
    required = {"candidate_profiles", "application_records", "resume_documents"}
    assert required <= tables, f"fork missing tables: {required - tables}"


def test_cleanup_dry_run_does_not_drop():
    """--dry-run must list only; the current fork (with open connections) is never eligible."""
    verdicts = cleanup_stale_test_databases(_original_prod_url(), confirm=False)
    conns_name = os.environ["DATABASE_URL"].rsplit("/", 1)[-1]
    related = [v for v in verdicts if conns_name in v]
    assert related, "current fork not listed in cleanup plan"
    assert all(v.startswith("skip") for v in related), "current fork must not be eligible (active connections)"
