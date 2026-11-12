#!/usr/bin/env python3
"""
Self-host first-boot bootstrap (Phase 3.1.0).

Idempotently creates the CareerOS schema on an empty PostgreSQL database and exits.
Meant to run at container start inside the bundled self-host compose. Never used in
production against a non-empty database: if the base table `resume_documents` already
exists, it is a no-op. Refuses to run when DATABASE_URL is unset.

Usage:
  python -m backend.ops.bootstrap           # initialize if empty; exit 0 on success/noop
  python -m backend.ops.bootstrap --verify  # print schema state, never write
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy import create_engine, text

from backend.app.config import settings
from backend.app.services.database_migration import run_database_migrations

MANDATORY_TABLE = "resume_documents"


def _engine():
    url = os.environ.get("DATABASE_URL") or settings.DATABASE_URL
    if not url:
        raise SystemExit("FATAL: DATABASE_URL is not configured — refusing to bootstrap.")
    return create_engine(url, pool_pre_ping=True)


def _schema_state(engine):
    with engine.connect() as conn:
        tables = {r[0] for r in conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))}
    return tables


def main() -> int:
    parser = argparse.ArgumentParser(prog="backend.ops.bootstrap")
    parser.add_argument("--verify", action="store_true", help="read-only; print schema state; never writes")
    args = parser.parse_args()

    engine = _engine()
    tables = _schema_state(engine)
    if MANDATORY_TABLE in tables:
        print(f"schema already present ({len(tables)} tables); nothing to do")
        return 0

    if args.verify:
        print(f"schema NOT initialized ({len(tables)} tables found; expected empty or missing {MANDATORY_TABLE!r})")
        return 1

    print(f"schema empty ({len(tables)} tables); running migrations…")

    # pgvector dependency — required by the embedding column definitions the migrations emit.
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    run_database_migrations(engine)
    tables_after = _schema_state(engine)
    if MANDATORY_TABLE not in tables_after:
        raise SystemExit(f"FATAL: migrations ran but {MANDATORY_TABLE!r} is still missing — refusing to start.")
    print(f"schema initialized: {len(tables_after)} tables")
    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
