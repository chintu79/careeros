#!/usr/bin/env python3
"""
Explicit schema-migration CLI. NEVER runs automatically.

Safety model (see backend/app/services/migration_guard.py):
  dry-run:   python -m backend.ops.migrate --dry-run
             Prints the sanitized target fingerprint; no connection, no DDL.
  test/dev:  python -m backend.ops.migrate --confirm --target <fingerprint>
  production:
             python -m backend.ops.migrate --confirm --target <fingerprint> \
                 --authorize-production
             plus CAREEROS_MIGRATION_AUTHORIZATION=<fingerprint> in the environment.

Any other combination exits non-zero without touching the database.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.config import settings
from backend.app.services import migration_guard as guard

MIGRATION_ID = "schema-migrations"


def _load_engine():
    # Imported lazily so dry-run/refusal paths cannot open a database connection.
    from backend.app.database import engine
    return engine


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="backend.ops.migrate")
    parser.add_argument("--dry-run", action="store_true", help="print target and plan only")
    parser.add_argument("--confirm", action="store_true", help="execute the migration")
    parser.add_argument("--target", metavar="FINGERPRINT", help="exact target fingerprint from --dry-run")
    parser.add_argument(
        "--authorize-production", action="store_true",
        help="required for production targets, together with CAREEROS_MIGRATION_AUTHORIZATION",
    )
    return parser


def run(argv=None, database_url: str = None, environ=None) -> int:
    args = _parser().parse_args(argv)
    url = database_url or settings.DATABASE_URL
    try:
        target = guard.resolve_target(url, getattr(settings, "ENVIRONMENT", None))

        if args.dry_run:
            print(f"target: {target.display}")
            print("plan: apply idempotent schema DDL only (advisory lock 42000101).")
            print("plan: no business-data backfill; no candidate_rows are written.")
            print("execute with: --confirm --target %s%s" % (
                target.fingerprint,
                " --authorize-production  (and CAREEROS_MIGRATION_AUTHORIZATION)" if target.kind == "production" else "",
            ))
            return 0

        auth = guard.authorize(
            target,
            confirm=args.confirm,
            target_fingerprint=args.target,
            authorize_production=args.authorize_production,
            environ=environ,
        )
    except guard.MigrationRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 3

    engine = _load_engine()

    def action():
        from backend.app.services.database_migration import run_database_migrations
        run_database_migrations(engine)
        return {}

    try:
        result = guard.execute_authorized(
            engine, migration_id=MIGRATION_ID, target=target,
            authorization_method=auth, action=action,
        )
    except guard.MigrationRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}: {guard.sanitize(str(exc))}", file=sys.stderr)
        return 1

    print(f"migrations complete; audit_id={result['audit_id']} changes={result['applied_changes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
