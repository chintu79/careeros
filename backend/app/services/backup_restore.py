"""
Backup and restore for CareerOS (Phase 3.0.5).

Design invariants:
- Every command resolves its target first; a bare confirmation is never enough.
- Restore targets must be disposable forks (`careeros_test_` prefix). There is no
  production-restore path in this phase.
- Backup sources follow the migration-guard classification; production sources require the
  same double gate (`--authorize-production` + `CAREEROS_MIGRATION_AUTHORIZATION`).
- No fallback: if a target is unavailable or unrecognized, the tool fails; it never
  silently operates on another database.
- The database snapshot is a single `pg_dump` transaction (consistent). Filesystem
  artifacts are hashed before the dump starts and again after it finishes; if the tree
  changed during the snapshot the whole backup is rejected and the staging directory
  is removed.
- No credentials are logged. Manifests carry the sanitized target display only.
"""

from __future__ import annotations

import hashlib
import getpass
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, text

from backend.app.testing.db_guard import TEST_DB_PREFIX, _psql, parse_pg_url
from backend.app.services.migration_guard import (
    MigrationRefused,
    resolve_target,
    sanitize,
)

BACKUP_FORMAT_VERSION = 1
TOOL = "careeros-backup/3.0.5"
DUMP_FILENAME = "dump.pgcustom"
ARTIFACTS_DIRNAME = "artifacts"
MANIFEST_FILENAME = "manifest.json"
CHECKSUMS_FILENAME = "checksums.sha256"
REPORT_PREFIX = "restore-report-"
STAGING_PREFIX = ".staging-"

_CHUNK = 1024 * 1024


class BackupError(RuntimeError):
    """Unrecoverable but reportable failure (bad backup, corrupt data, unsafe state)."""


class TargetExists(BackupError):
    """The explicit restore target already exists and no destructive override was given."""


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _inventory_tree(root: Path) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    if not root.exists():
        return entries
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            entries.append({
                "rel_path": rel,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            })
    return entries


def _schema_stats(engine) -> Dict[str, Any]:
    with engine.connect() as conn:
        tables = conn.execute(text(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
        )).scalar()
        indexes = conn.execute(text(
            "SELECT count(*) FROM pg_indexes WHERE schemaname='public'"
        )).scalar()
        extensions = sorted(row[0] for row in conn.execute(text(
            "SELECT extname FROM pg_extension"
        )))
    return {"tables": int(tables), "indexes": int(indexes), "extensions": extensions}


def _counts_and_files(artifact_root: Path):
    files = _inventory_tree(artifact_root)
    total_bytes = sum(item["size"] for item in files)
    return files, total_bytes


def _referenced_artifact_basenames(engine) -> List[str]:
    """Basenames of pdf_path values in the well-known artifact-bearing tables (read-only)."""
    names: set[str] = set()
    with engine.connect() as conn:
        tables = {r[0] for r in conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        ))}
        for table in ("resume_documents", "resume_versions"):
            if table not in tables:
                continue
            column = conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=:table AND column_name='pdf_path'"
            ), {"table": table}).scalar()
            if not column:
                continue
            rows = conn.execute(text(
                f"SELECT pdf_path FROM {table} WHERE pdf_path IS NOT NULL"
            )).scalars()
            for value in rows:
                if value:
                    names.add(os.path.basename(str(value)))
    return sorted(names)


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _maintenance_sql(parsed_url, sql: str, check: bool = True):
    return _psql(parsed_url, "postgres", sql, check=check)


def _target_exists(parsed_url, database: str) -> bool:
    output = _maintenance_sql(parsed_url, f"SELECT 1 FROM pg_database WHERE datname = {_sql_literal(database)}", check=False)
    return output.stdout.strip() == "1"


def _create_database(parsed_url, database: str) -> None:
    _maintenance_sql(parsed_url, f'CREATE DATABASE "{database.replace(chr(34), chr(34) * 2)}"')


def _drop_database(parsed_url, database: str) -> None:
    _maintenance_sql(parsed_url, f'DROP DATABASE IF EXISTS "{database.replace(chr(34), chr(34) * 2)}"')


def database_url_for(parsed_url, database: str) -> str:
    return (
        f"postgresql+psycopg://{parsed_url.username}:{parsed_url.password}"
        f"@{parsed_url.hostname}:{parsed_url.port or 5432}/{database}"
    )


def _hash_tree(root: Path) -> Dict[str, str]:
    return {item["rel_path"]: item["sha256"] for item in _inventory_tree(root)}


def _remove_tree(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def _write_manifest_and_checksums(staging: Path, manifest: Dict[str, Any]) -> None:
    manifest_path = staging / MANIFEST_FILENAME
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines: List[str] = []
    for item in _inventory_tree(staging / ARTIFACTS_DIRNAME):
        lines.append(f"{item['sha256']}  {ARTIFACTS_DIRNAME}/{item['rel_path']}")
    dump_path = staging / DUMP_FILENAME
    lines.append(f"{sha256_file(dump_path)}  {DUMP_FILENAME}")
    lines.append(f"{sha256_file(manifest_path)}  {MANIFEST_FILENAME}")
    (staging / CHECKSUMS_FILENAME).write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

def create_backup(
    database_url: str,
    *,
    artifact_dir: str,
    dest_root: str,
    dry_run: bool = False,
    target_fingerprint: Optional[str] = None,
    authorize_production: bool = False,
    environ: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    target = resolve_target(database_url, os.environ.get("ENVIRONMENT"))
    source_display = target.display

    artifact_path = Path(artifact_dir).expanduser().resolve()
    dest = Path(dest_root).expanduser().resolve()

    if dry_run:
        files, total_bytes = _counts_and_files(artifact_path)
        print(f"source: {source_display}")
        print(f"artifact_dir: {artifact_path} ({len(files)} files, {total_bytes} bytes)")
        print(f"dest: {dest}")
        print("plan: snapshot artifacts -> pg_dump -> re-hash artifacts -> manifest+sha256 -> atomic rename")
        print("no files will be written during a dry-run")
        return {"dry_run": True, "source": source_display}

    # Explicit authorization gate (same shape as migrations).
    import backend.app.services.migration_guard as guard

    guard.authorize(
        target,
        confirm=True,
        target_fingerprint=target_fingerprint,
        authorize_production=authorize_production,
        environ=environ,
    )

    if not artifact_path.is_dir():
        raise BackupError(f"artifact directory does not exist or is not a directory: {artifact_path}")

    dest.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=dest))
    engine = create_engine(database_url)
    final_path: Optional[Path] = None
    started = now_utc_iso()
    try:
        artifact_dest = staging / ARTIFACTS_DIRNAME
        shutil.copytree(artifact_path, artifact_dest)
        before = _hash_tree(artifact_dest)

        schema_stats = _schema_stats(engine)

        dump_path = staging / DUMP_FILENAME
        parsed = parse_pg_url(database_url)
        dump = subprocess.run(
            [
                "pg_dump", "--format=custom", "--no-owner", "--no-privileges",
                "-h", parsed.hostname or "localhost", "-p", str(parsed.port or 5432),
                "-U", parsed.username or "postgres", "-d", parsed.path.lstrip("/"),
                "-f", str(dump_path),
            ],
            env=dict(os.environ, PGPASSWORD=parsed.password or ""),
            capture_output=True,
            text=True,
            timeout=600,
        )
        if dump.returncode != 0:
            raise BackupError(f"pg_dump failed: {sanitize(dump.stderr.strip())[:400]}")

        after = _hash_tree(artifact_dest)
        if before != after:
            changed = sorted(set(before) ^ set(after) | {k for k in before if before.get(k) != after.get(k)})
            raise BackupError(
                f"artifact set changed during database snapshot ({len(changed)} paths); aborting backup"
            )

        final_name = f"{target.fingerprint}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        files, total_bytes = _counts_and_files(artifact_dest)
        manifest = {
            "format_version": BACKUP_FORMAT_VERSION,
            "tool": TOOL,
            "created_utc": started,
            "operator": getpass.getuser()[:120],
            "source": {
                "display": source_display,
                "environment": target.environment,
                "kind": target.kind,
                "fingerprint": target.fingerprint,
            },
            "database": {
                "format": "pg_dump/custom",
                "file": DUMP_FILENAME,
                **schema_stats,
                "size_bytes": dump_path.stat().st_size,
                "sha256": sha256_file(dump_path),
            },
            "artifacts": {
                "root": ARTIFACTS_DIRNAME,
                "file_count": len(files),
                "total_bytes": total_bytes,
                "files": files,
            },
            "consistency": "artifacts_stable_across_dump",
        }
        _write_manifest_and_checksums(staging, manifest)

        final_path = dest / final_name
        os.replace(staging, final_path)
        return {
            "dry_run": False,
            "backup_path": str(final_path),
            "manifest": final_path / MANIFEST_FILENAME,
            "source": source_display,
            "database_bytes": manifest["database"]["size_bytes"],
            "artifact_files": len(files),
            "artifact_bytes": total_bytes,
        }
    except Exception:
        if final_path is None:
            _remove_tree(staging)
        raise
    finally:
        engine.dispose()


def verify_backup(backup_dir: str) -> Dict[str, Any]:
    root = Path(backup_dir).expanduser().resolve()
    manifest_path = root / MANIFEST_FILENAME
    if not root.is_dir() or not manifest_path.is_file():
        raise BackupError(f"backup is not a complete staging directory: {root}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems: List[str] = []
    if manifest.get("format_version") != BACKUP_FORMAT_VERSION:
        problems.append(f"unsupported format_version {manifest.get('format_version')!r}")

    files = manifest.get("artifacts", {}).get("files", [])
    expected = {item["rel_path"]: item for item in files}
    actual_files = _inventory_tree(root / ARTIFACTS_DIRNAME)
    actual = {item["rel_path"]: item for item in actual_files}

    for rel_path, item in expected.items():
        found = actual.get(rel_path)
        if found is None:
            problems.append(f"missing artifact: {rel_path}")
        elif found["sha256"] != item["sha256"] or found["size"] != item["size"]:
            problems.append(f"corrupt artifact: {rel_path}")
    for rel_path in sorted(set(actual) - set(expected)):
        problems.append(f"unexpected artifact: {rel_path}")

    dump_path = root / DUMP_FILENAME
    if not dump_path.is_file():
        problems.append(f"missing dump: {DUMP_FILENAME}")
    else:
        expected_dump = manifest.get("database", {}).get("sha256")
        if expected_dump and sha256_file(dump_path) != expected_dump:
            problems.append(f"corrupt dump: {DUMP_FILENAME}")
        if manifest["database"].get("size_bytes") and dump_path.stat().st_size != manifest["database"]["size_bytes"]:
            problems.append("dump size mismatch")

    result = {
        "ok": not problems,
        "backup_path": str(root),
        "files_checked": len(files),
        "artifact_files": len(actual),
        "problems": problems,
    }
    if problems:
        raise BackupError("; ".join(problems[:20]))
    return result


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------

def _restore_target_requires_test_kind(target) -> None:
    if target.kind != "test":
        raise MigrationRefused(
            f"restore targets must be disposable test databases (name starts with {TEST_DB_PREFIX!r}); got {target.display}"
        )


def restore_backup(
    backup_dir: str,
    target_url: str,
    *,
    target_fingerprint: Optional[str],
    artifact_root: str,
    dry_run: bool = False,
    force_overwrite: bool = False,
    environ: Optional[Dict[str, str]] = None,
    report_path: Optional[str] = None,
) -> Dict[str, Any]:
    target = resolve_target(target_url, os.environ.get("ENVIRONMENT"))
    _restore_target_requires_test_kind(target)
    root = Path(backup_dir).expanduser().resolve()
    artifact_dest = Path(artifact_root).expanduser().resolve()

    if dry_run:
        # Validate read-only; never create anything.
        verify_backup(str(root))
        manifest = json.loads((root / MANIFEST_FILENAME).read_text(encoding="utf-8"))
        print(f"backup: {root}")
        print(f"target: {target.display}")
        print(f"artifact_dest: {artifact_dest}")
        print(f"plan: create target DB -> pg_restore ({manifest['database']['sha256'][:12]}...) -> copy {manifest['artifacts']['file_count']} artifacts -> verify")
        print("no files will be written during a dry-run")
        return {"dry_run": True, "target": target.display}

    expected_fp = target.fingerprint
    if not target_fingerprint or target_fingerprint.strip().lower() != expected_fp:
        raise MigrationRefused(f"target fingerprint mismatch: expected {expected_fp!r} for {target.display}")

    report = {
        "restored_at": now_utc_iso(),
        "backup": str(root),
        "target": {"display": target.display, "fingerprint": target.fingerprint},
        "operator": getpass.getuser()[:120],
        "steps": [],
        "success": False,
        "elapsed_seconds": None,
        "error": None,
    }
    report_path = report_path or str(artifact_dest.parent / f"{REPORT_PREFIX}{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json")

    def record(step: str, ok: bool, detail: str = ""):
        report["steps"].append({"step": step, "ok": ok, "detail": detail})
        if not ok:
            raise BackupError(f"{step}: {detail}")

    def refuse_existing(step: str, detail: str):
        report["steps"].append({"step": step, "ok": False, "detail": detail})
        raise TargetExists(detail)

    created_db = False
    created_artifact_dir = False
    parsed = parse_pg_url(target_url)
    started = datetime.now(timezone.utc)

    try:
        try:
            manifest_ok = verify_backup(str(root))
        except Exception as exc:
            record("verify_backup", False, f"{type(exc).__name__}: {exc}")
        else:
            record("verify_backup", True, f"{manifest_ok['files_checked']} artifact checksums verified")

        target_db = parsed.path.lstrip("/")
        if _target_exists(parsed, target_db):
            if not force_overwrite:
                refuse_existing(
                    "target_exists",
                    f"restore target {target.display} already exists; pass --force-overwrite to drop and recreate it, or choose a fresh name",
                )
            _drop_database(parsed, target_db)
            record("drop_existing_target", True, "force-overwrite confirmed")
        if artifact_dest.exists() and any(artifact_dest.iterdir()):
            if not force_overwrite:
                refuse_existing(
                    "artifact_dir_exists",
                    f"restore artifact directory {artifact_dest} is not empty; pass --force-overwrite to replace it",
                )
            _remove_tree(artifact_dest)
            record("clear_existing_artifact_dir", True, "force-overwrite confirmed")

        _create_database(parsed, target_db)
        created_db = True
        record("create_target_database", True, target.database)

        restore = subprocess.run(
            [
                "pg_restore", "--no-owner", "--no-privileges",
                "-h", parsed.hostname or "localhost", "-p", str(parsed.port or 5432),
                "-U", parsed.username or "postgres", "-d", target.database,
                str(root / DUMP_FILENAME),
            ],
            env=dict(os.environ, PGPASSWORD=parsed.password or ""),
            capture_output=True,
            text=True,
            timeout=600,
        )
        if restore.returncode != 0:
            raise BackupError(f"pg_restore failed: {sanitize(restore.stderr.strip())[:400]}")
        record("pg_restore", True, DUMP_FILENAME)

        artifact_dest.mkdir(parents=True)
        created_artifact_dir = True
        shutil.copytree(root / ARTIFACTS_DIRNAME, artifact_dest, dirs_exist_ok=True)
        record("restore_artifacts", True, str(artifact_dest))

        restored = _inventory_tree(artifact_dest)
        expected = {item["rel_path"]: item for item in json.loads((root / MANIFEST_FILENAME).read_text())["artifacts"]["files"]}
        mismatches = []
        for rel_path, item in expected.items():
            found = next((f for f in restored if f["rel_path"] == rel_path), None)
            if found is None:
                mismatches.append(f"missing {rel_path}")
            elif found["sha256"] != item["sha256"]:
                mismatches.append(f"corrupt {rel_path}")
        if mismatches:
            raise BackupError("artifact verification failed: " + "; ".join(mismatches[:10]))
        record("verify_artifacts", True, f"{len(restored)} files match manifest checksums")

        engine = create_engine(database_url_for(parsed, target.database))
        try:
            manifest_stats = json.loads((root / MANIFEST_FILENAME).read_text())["database"]
            stats = _schema_stats(engine)
            if stats["tables"] != manifest_stats["tables"]:
                raise BackupError(f"schema verification failed: tables {stats['tables']} != expected {manifest_stats['tables']}")
            if stats["indexes"] != manifest_stats["indexes"]:
                raise BackupError(f"schema verification failed: indexes {stats['indexes']} != expected {manifest_stats['indexes']}")
            missing_exts = [ext for ext in manifest_stats.get("extensions", []) if ext not in stats["extensions"]]
            if missing_exts:
                raise BackupError(f"schema verification failed: missing extensions {missing_exts}")
            record("verify_schema", True, f"tables={stats['tables']} indexes={stats['indexes']} extensions={stats['extensions']}")

            found_names = _referenced_artifact_basenames(engine)
            present = {item["rel_path"].split("/")[-1] for item in restored}
            missing = [name for name in found_names if name not in present]
            report["artifacts"] = {
                "referenced_by_database": len(found_names),
                "restored_files": len(restored),
                "missing_referenced": missing,
            }
            if missing:
                raise BackupError(f"restored artifacts are missing {len(missing)} database-referenced files: {missing[:5]}")
            record("verify_artifact_mapping", True, f"{len(found_names)} referenced basenames present in restored tree")
        finally:
            engine.dispose()

        report["success"] = True
        report["elapsed_seconds"] = (datetime.now(timezone.utc) - started).total_seconds()
        return report
    except Exception as exc:
        report["error"] = sanitize(f"{type(exc).__name__}: {exc}")
        if created_db:
            try:
                from backend.app.testing import fork_lifecycle

                fork_report = fork_lifecycle.OwnedFork(
                    target_url, target.database, parsed,
                ).cleanup(reason="restore failure — drop created target")
                ok = bool(fork_report.get("success"))
                report.setdefault("steps", []).append({
                    "step": "cleanup_created_database",
                    "ok": ok,
                    "detail": "dropped after failure" if ok else f"cleanup failed: {fork_report.get('error')}",
                })
            except Exception as cleanup_exc:
                report.setdefault("steps", []).append({
                    "step": "cleanup_created_database",
                    "ok": False,
                    "detail": f"cleanup failed: {type(cleanup_exc).__name__}",
                })
                sys.stderr.write(f"WARNING: restore failed and created target {target.database} could not be dropped\n")
        if created_artifact_dir:
            _remove_tree(artifact_dest)
            report.setdefault("steps", []).append({"step": "cleanup_created_artifacts", "ok": True, "detail": "removed after failure"})
        raise
    finally:
        try:
            path = Path(report_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        except OSError:
            sys.stderr.write("warning: could not write restore report\n")
