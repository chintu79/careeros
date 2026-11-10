#!/usr/bin/env python3
"""
Operator-controlled CareerOS backup. NEVER runs automatically.

Safety model (see backend/app/services/backup_restore.py):
  dry-run:  python -m backend.ops.backup --dry-run --dest-root /srv/backups
            Prints the sanitized source fingerprint and artifact inventory; writes nothing.
  verify:   python -m backend.ops.backup --verify --backup /srv/backups/<backup-dir>
            Re-hashes every file, checks the manifest and checksums; writes nothing.
  create:   python -m backend.ops.backup --confirm --target <fingerprint> --dest-root /srv/backups
            Production sources additionally need --authorize-production and
            CAREEROS_MIGRATION_AUTHORIZATION=<fingerprint>.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.config import settings
from backend.app.services import backup_restore as backup_service
from backend.app.services import migration_guard as guard

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_ARTIFACT_DIR = os.path.join(REPO_ROOT, "backend", "storage", "resumes")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="backend.ops.backup")
    parser.add_argument("--dry-run", action="store_true", help="print source fingerprint and artifact inventory; writes nothing")
    parser.add_argument("--confirm", action="store_true", help="create the backup")
    parser.add_argument("--verify", metavar="BACKUP_DIR", help="verify an existing backup directory; writes nothing")
    parser.add_argument("--target", metavar="FINGERPRINT", help="exact source fingerprint from --dry-run")
    parser.add_argument("--artifact-dir", default=DEFAULT_ARTIFACT_DIR, help="artifact root to include (default: backend/storage/resumes)")
    parser.add_argument("--dest-root", help="directory under which the timestamped backup is created")
    parser.add_argument("--authorize-production", action="store_true",
                        help="required for production sources, with CAREEROS_MIGRATION_AUTHORIZATION")
    return parser


def run(argv=None, database_url: str = None, environ=None) -> int:
    args = _parser().parse_args(argv)

    if args.verify:
        try:
            result = backup_service.verify_backup(args.verify)
        except Exception as exc:
            print(f"FAILED: backup verification failed: {backup_service.sanitize(str(exc))}", file=sys.stderr)
            return 1
        print(f"OK: {result['files_checked']} artifact checksums + dump checksum verified ({result['backup_path']})")
        return 0

    if not args.dest_root:
        print("REFUSED: --dest-root is required (choose a filesystem outside the repo, e.g. /srv/backups)", file=sys.stderr)
        return 2

    url = database_url or settings.DATABASE_URL

    if args.dry_run:
        try:
            backup_service.create_backup(
                url, artifact_dir=args.artifact_dir, dest_root=args.dest_root, dry_run=True,
            )
            return 0
        except guard.MigrationRefused as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 3

    if not args.confirm:
        print("REFUSED: pass --confirm to execute, or --dry-run to preview, or --verify <dir>", file=sys.stderr)
        return 3

    try:
        result = backup_service.create_backup(
            url,
            artifact_dir=args.artifact_dir,
            dest_root=args.dest_root,
            target_fingerprint=args.target,
            authorize_production=args.authorize_production,
            environ=environ,
        )
    except guard.MigrationRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}: {backup_service.sanitize(str(exc))}", file=sys.stderr)
        return 1

    print(
        "backup complete: "
        f"{result['backup_path']} ({result['database_bytes']} dump bytes, "
        f"{result['artifact_files']} artifacts, {result['artifact_bytes']} bytes)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
