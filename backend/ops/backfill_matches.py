#!/usr/bin/env python3
"""
Explicit candidate_opportunity_matches back-fill. NEVER runs automatically.

Safety model (see backend/app/services/migration_guard.py):
  dry-run:   python -m backend.ops.backfill_matches --dry-run
             Read-only count + sanitized target fingerprint. No writes.
  test/dev:  python -m backend.ops.backfill_matches --confirm --target <fingerprint>
  production:
             python -m backend.ops.backfill_matches --confirm --target <fingerprint> \
                 --authorize-production
             plus CAREEROS_MIGRATION_AUTHORIZATION=<fingerprint> in the environment.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.config import settings
from backend.app.services import migration_guard as guard

MIGRATION_ID = "backfill-candidate-opportunity-matches"


def _load_engine():
    from backend.app.database import engine
    return engine


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="backend.ops.backfill_matches")
    parser.add_argument("--dry-run", action="store_true", help="read-only row count only")
    parser.add_argument("--confirm", action="store_true", help="execute the back-fill")
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
    except guard.MigrationRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 3

    engine = _load_engine()
    try:
        guard.assert_engine_matches_target(engine, target)
    except guard.MigrationRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 3

    from backend.app.services.database_migration import ops_backfill_candidate_matches

    if args.dry_run:
        try:
            n = ops_backfill_candidate_matches(engine, dry_run=True)
        except Exception as exc:
            print(f"FAILED: {type(exc).__name__}: {guard.sanitize(str(exc))}", file=sys.stderr)
            return 1
        print(f"target: {target.display}")
        print(f"dry-run: would create {n} candidate_opportunity_matches rows (no writes)")
        return 0

    try:
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

    def action():
        return {"rows_created": ops_backfill_candidate_matches(engine, dry_run=False)}

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

    print(f"backfill complete; audit_id={result['audit_id']} changes={result['applied_changes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
