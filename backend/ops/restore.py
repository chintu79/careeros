#!/usr/bin/env python3
"""
Operator-controlled CareerOS restore. NEVER runs automatically.

Restore targets are disposable forks ONLY (`careeros_test_<name>`). There is no
production or arbitrary-development restore path in this tool.

  dry-run:  python -m backend.ops.restore --dry-run --backup /srv/backups/<dir> --artifact-dest /tmp/restore-artifacts
  restore:  python -m backend.ops.restore --confirm --backup /srv/backups/<dir>
            --target-url <fork-url> --target <fingerprint> --artifact-dest /tmp/restore-artifacts

The restore validates the manifest and every checksum before creating anything,
never overwrites an existing target without `--force-overwrite` (destructive), and
writes a machine-readable restore report. It does NOT run application migrations;
schema comes entirely from the backup.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.config import settings
from backend.app.services import backup_restore as backup_service
from backend.app.services import migration_guard as guard


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="backend.ops.restore")
    parser.add_argument("--dry-run", action="store_true", help="validate only; writes nothing")
    parser.add_argument("--confirm", action="store_true", help="execute the restore")
    parser.add_argument("--backup", required=True, metavar="BACKUP_DIR", help="backup directory from backend.ops.backup")
    parser.add_argument("--target-url", default=None, help="full URL of a NEW disposable restore target (careeros_test_ prefix required)")
    parser.add_argument("--target", metavar="FINGERPRINT", help="exact target fingerprint from --dry-run")
    parser.add_argument("--artifact-dest", required=True, metavar="DIR", help="destination directory for restored artifacts")
    parser.add_argument("--report", metavar="FILE", help="path for the machine-readable restore report (default: beside the artifact dest)")
    parser.add_argument("--force-overwrite", action="store_true", help="drop/recreate the target DB and clear the artifact dir (destructive)")
    return parser


def run(argv=None, environ=None) -> int:
    args = _parser().parse_args(argv)
    target_url = args.target_url or settings.DATABASE_URL

    if args.dry_run:
        try:
            backup_service.restore_backup(
                args.backup, target_url,
                target_fingerprint=None, artifact_root=args.artifact_dest,
                dry_run=True, report_path=args.report, environ=environ,
            )
            return 0
        except guard.MigrationRefused as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 3
        except Exception as exc:
            print(f"FAILED: restore validation failed: {backup_service.sanitize(str(exc))}", file=sys.stderr)
            return 1

    if not args.confirm:
        print("REFUSED: pass --confirm to execute, or --dry-run to validate (see --help)", file=sys.stderr)
        return 3

    try:
        report = backup_service.restore_backup(
            args.backup, target_url,
            target_fingerprint=args.target, artifact_root=args.artifact_dest,
            dry_run=False, force_overwrite=args.force_overwrite, report_path=args.report, environ=environ,
        )
    except guard.MigrationRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 3
    except backup_service.TargetExists as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}: {backup_service.sanitize(str(exc))}", file=sys.stderr)
        return 1

    print(f"restore complete: target={report['target']['display']} elapsed={report['elapsed_seconds']:.2f}s report={args.report or 'beside artifact dest'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
