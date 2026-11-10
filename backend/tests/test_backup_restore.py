"""
Backup/restore safety and recovery regression tests (Phase 3.0.5).

Mutation tests run against the disposable conftest fork; every restore target created
here is a fresh `careeros_test_*` database and is dropped in a finally block.
No test touches production. No test reconstructs a live URL from a dump filename.
"""

import json
import os
import shutil
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from backend.app.config import settings
from backend.app.services import backup_restore as br
from backend.app.services import migration_guard as guard
from backend.app.testing import db_guard
from backend.app.testing.db_guard import TEST_DB_PREFIX, parse_pg_url
from backend.ops import backup as backup_cli
from backend.ops import restore as restore_cli

PROD_URL = "postgresql+psycopg://ops_user:s3cret-pass@db.example.com:5432/interniq"
PROD_FP = guard.fingerprint("db.example.com", 5432, "interniq")
DEV_URL = "postgresql+psycopg://u:p@localhost:5432/careeros_dev"
UNREACHABLE_TEST_URL = "postgresql+psycopg://u:p@127.0.0.1:1/careeros_test_zz"


def _fork():
    url = settings.DATABASE_URL
    parsed = parse_pg_url(url)
    return url, parsed, guard.fingerprint(parsed.hostname, parsed.port or 5432, parsed.path.lstrip("/"))


def _synthetic_artifacts(directory, fork_url):
    engine = create_engine(fork_url)
    try:
        names = br._referenced_artifact_basenames(engine)
    finally:
        engine.dispose()
    directory.mkdir(parents=True, exist_ok=True)
    for i, name in enumerate(names):
        (directory / name).write_bytes(f"%PDF-1.4 synthetic {i}\n%%EOF\n".encode())
    (directory / "extra.tex").write_bytes(b"\\documentclass{article}\n")
    return names


@pytest.fixture(scope="module")
def synthetic_dir(tmp_path_factory):
    fork_url, _, _ = _fork()
    path = tmp_path_factory.mktemp("synthetic-artifacts") / "artifacts"
    _synthetic_artifacts(path, fork_url)
    return path


@pytest.fixture()
def artifact_copy(tmp_path, synthetic_dir):
    dest = tmp_path / "artifacts-copy"
    shutil.copytree(synthetic_dir, dest)
    return dest


def _prod_url_and_fp():
    return PROD_URL, PROD_FP


# ---------------------------------------------------------------------------
# Production refusal / unknown target / no fallback
# ---------------------------------------------------------------------------

def test_backup_refuses_production_by_default(capsys, tmp_path, synthetic_dir):
    rc = backup_cli.run(
        ["--confirm", "--target", PROD_FP, "--artifact-dir", str(synthetic_dir), "--dest-root", str(tmp_path)],
        database_url=PROD_URL, environ={},
    )
    captured = capsys.readouterr()
    assert rc == 3
    assert "CAREEROS_MIGRATION_AUTHORIZATION" in captured.err
    assert "s3cret-pass" not in captured.err
    assert list(tmp_path.iterdir()) == []


def test_backup_requires_target_without_exception(capsys, tmp_path, synthetic_dir):
    rc = backup_cli.run(
        ["--confirm", "--artifact-dir", str(synthetic_dir), "--dest-root", str(tmp_path)],
        database_url=PROD_URL, environ={},
    )
    assert rc == 3
    assert list(tmp_path.iterdir()) == []


def test_backup_refuses_unknown_target(capsys, tmp_path, synthetic_dir):
    rc = backup_cli.run(
        ["--confirm", "--target", PROD_FP, "--artifact-dir", str(synthetic_dir), "--dest-root", str(tmp_path)],
        database_url="sqlite:///tmp/opencode/not-postgres.db", environ={},
    )
    assert rc == 3
    assert list(tmp_path.iterdir()) == []


def test_backup_missing_artifact_dir_refused_and_nothing_written(capsys, tmp_path):
    fork_url, _, fp = _fork()
    rc = backup_cli.run(
        ["--confirm", "--target", fp, "--artifact-dir", str(tmp_path / "nope"), "--dest-root", str(tmp_path / "out")],
        database_url=fork_url, environ={},
    )
    assert rc == 1
    assert not (tmp_path / "out").exists() or list((tmp_path / "out").iterdir()) == []


def test_backup_failure_cleans_up_staging(tmp_path, synthetic_dir):
    """A failure before pg_dump must leave no staging directory behind."""
    dest_root = tmp_path / "backups"
    with pytest.raises(Exception):
        br.create_backup(
            UNREACHABLE_TEST_URL,
            artifact_dir=str(synthetic_dir),
            dest_root=str(dest_root),
            target_fingerprint=guard.fingerprint("127.0.0.1", 1, "careeros_test_zz"),
            environ={},
        )
    leftovers = list(dest_root.glob(f"{br.STAGING_PREFIX}*")) if dest_root.exists() else []
    assert leftovers == []
    assert list(dest_root.glob("*-*")) == []


def test_backup_dry_run_writes_nothing(tmp_path, synthetic_dir):
    fork_url, _, fp = _fork()
    dest_root = tmp_path / "backups"
    rc = backup_cli.run(
        ["--dry-run", "--target", fp, "--artifact-dir", str(synthetic_dir), "--dest-root", str(dest_root)],
        database_url=fork_url, environ={},
    )
    assert rc == 0
    assert not dest_root.exists() or list(dest_root.iterdir()) == []


def test_backup_dry_run_production_still_refused_without_target(capsys, tmp_path, synthetic_dir):
    rc = backup_cli.run(
        ["--dry-run", "--artifact-dir", str(synthetic_dir), "--dest-root", str(tmp_path)],
        database_url=PROD_URL, environ={},
    )
    assert rc == 0  # dry-run prints the plan; no execution possible
    assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------
# Backup verification (checksum + manifest)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def fork_backup(tmp_path_factory, synthetic_dir):
    fork_url, _, fp = _fork()
    dest_root = tmp_path_factory.mktemp("fork-backups")
    result = br.create_backup(
        fork_url,
        artifact_dir=str(synthetic_dir),
        dest_root=str(dest_root),
        target_fingerprint=fp,
        environ={},
    )
    return result["backup_path"]


def test_backup_manifest_and_credentials(fork_backup):
    manifest = json.loads((Path(fork_backup) / br.MANIFEST_FILENAME).read_text(encoding="utf-8"))
    assert manifest["format_version"] == br.BACKUP_FORMAT_VERSION
    assert manifest["tool"] == br.TOOL
    assert manifest["database"]["format"] == "pg_dump/custom"
    assert manifest["database"]["tables"] >= 20
    assert "vector" in manifest["database"]["extensions"]
    assert manifest["artifacts"]["file_count"] >= 2
    display = manifest["source"]["display"]
    assert "s3cret" not in display and "ops_user" not in display
    assert "fingerprint" in manifest["source"] and manifest["source"]["fingerprint"]


def test_backup_verify_ok(fork_backup):
    result = br.verify_backup(fork_backup)
    assert result["ok"] is True
    assert result["files_checked"] >= 2


def test_backup_verify_detects_corrupt_dump(fork_backup, tmp_path):
    copied = tmp_path / "backup-corrupt-dump"
    shutil.copytree(fork_backup, copied)
    dump = copied / br.DUMP_FILENAME
    data = bytearray(dump.read_bytes())
    data[len(data) // 2] ^= 0xFF
    dump.write_bytes(bytes(data))
    with pytest.raises(br.BackupError, match="corrupt dump"):
        br.verify_backup(str(copied))


def test_backup_verify_detects_corrupt_artifact(fork_backup, tmp_path):
    copied = tmp_path / "backup-corrupt-artifact"
    shutil.copytree(fork_backup, copied)
    victim = next((copied / br.ARTIFACTS_DIRNAME).rglob("*.pdf"))
    data = bytearray(victim.read_bytes())
    data[0] ^= 0xFF
    victim.write_bytes(bytes(data))
    with pytest.raises(br.BackupError, match="corrupt artifact"):
        br.verify_backup(str(copied))


def test_backup_verify_detects_missing_artifact(fork_backup, tmp_path):
    copied = tmp_path / "backup-missing-artifact"
    shutil.copytree(fork_backup, copied)
    victim = next((copied / br.ARTIFACTS_DIRNAME).rglob("*.pdf"))
    victim.unlink()
    with pytest.raises(br.BackupError, match="missing artifact"):
        br.verify_backup(str(copied))


def test_backup_cli_verify(fork_backup, capsys):
    rc = backup_cli.run(["--verify", fork_backup], environ={})
    assert rc == 0
    assert "OK" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------

def _new_target_name():
    return f"{TEST_DB_PREFIX}drill_{uuid.uuid4().hex[:10]}"


def _target_url(name, parsed):
    return br.database_url_for(parsed, name)


def test_restore_refuses_production_target(capsys, fork_backup):
    rc = restore_cli.run(
        ["--confirm", "--backup", fork_backup, "--target-url", PROD_URL,
         "--target", PROD_FP, "--artifact-dest", "/tmp/opencode/never-created"],
        environ={},
    )
    captured = capsys.readouterr()
    assert rc == 3
    assert "disposable test databases" in captured.err
    assert "s3cret-pass" not in captured.err


def test_restore_refuses_non_test_dev_target(capsys, fork_backup):
    fp = guard.fingerprint("localhost", 5432, "careeros_dev")
    rc = restore_cli.run(
        ["--confirm", "--backup", fork_backup, "--target-url", DEV_URL,
         "--target", fp, "--artifact-dest", "/tmp/opencode/never-created"],
        environ={},
    )
    assert rc == 3


def test_restore_refuses_unknown_target(capsys, fork_backup):
    rc = restore_cli.run(
        ["--confirm", "--backup", fork_backup, "--target-url", "sqlite:///tmp/opencode/x.db",
         "--target", PROD_FP, "--artifact-dest", "/tmp/opencode/never-created"],
        environ={},
    )
    assert rc == 3


def test_restore_fingerprint_mismatch_refused(fork_backup, tmp_path):
    _, parsed, _ = _fork()
    target_name = _new_target_name()
    with pytest.raises(guard.MigrationRefused):
        br.restore_backup(
            fork_backup, br.database_url_for(parsed, target_name),
            target_fingerprint="0000000000000000",
            artifact_root=str(tmp_path / "artifacts"),
            report_path=str(tmp_path / "report.json"),
            environ={},
        )
    assert not br._target_exists(parse_pg_url(settings.ORIGINAL_DATABASE_URL), target_name)


def test_restore_into_separate_fork_and_report(fork_backup, tmp_path):
    fork_url, parsed, _ = _fork()
    prod_parsed = parse_pg_url(settings.ORIGINAL_DATABASE_URL)
    target_name = _new_target_name()
    artifact_dest = tmp_path / "restored-artifacts"
    report_path = tmp_path / "restore-report.json"
    try:
        report = br.restore_backup(
            fork_backup, br.database_url_for(parsed, target_name),
            target_fingerprint=guard.fingerprint(parsed.hostname, parsed.port or 5432, target_name),
            artifact_root=str(artifact_dest),
            report_path=str(report_path),
            environ={},
        )
        assert report["success"] is True
        assert Path_like(artifact_dest)
        data = json.loads(report_path.read_text(encoding="utf-8"))
        assert data["success"] is True
        assert any(step["step"] == "verify_schema" and step["ok"] for step in data["steps"])
        assert any(step["step"] == "verify_artifact_mapping" and step["ok"] for step in data["steps"])

        engine = create_engine(br.database_url_for(parsed, target_name))
        try:
            with engine.connect() as conn:
                stats = br._schema_stats(engine)
                assert stats["tables"] >= 20
                assert "vector" in stats["extensions"]
                assert conn.execute(text("SELECT to_regclass('public.rate_limit_buckets') IS NOT NULL")).scalar() is True
                assert conn.execute(text("SELECT count(*) FROM resume_documents WHERE is_master IS TRUE")).scalar() >= 1
        finally:
            engine.dispose()
    finally:
        db_guard.drop_test_database(prod_parsed, target_name)


def Path_like(path):
    return path.is_dir() and any(path.rglob("*"))


def test_restore_refuses_existing_target(fork_backup, tmp_path):
    fork_url, parsed, _ = _fork()
    prod_parsed = parse_pg_url(settings.ORIGINAL_DATABASE_URL)
    # Deliberately create an existing target using the fork provisioning path.
    existing_url = db_guard.make_disposable_pg_database(settings.ORIGINAL_DATABASE_URL)
    existing_name = existing_url.rsplit("/", 1)[-1]
    artifact_dest = tmp_path / "restored-artifacts"
    try:
        with pytest.raises(br.TargetExists):
            br.restore_backup(
                fork_backup, existing_url,
                target_fingerprint=guard.fingerprint(parsed.hostname, parsed.port or 5432, existing_name),
                artifact_root=str(artifact_dest),
                report_path=str(tmp_path / "report.json"),
                environ={},
            )
        # Existing target is untouched and still answers.
        check = create_engine(existing_url)
        try:
            with check.connect() as conn:
                assert conn.execute(text("SELECT count(*) FROM information_schema.tables")).scalar() >= 20
        finally:
            check.dispose()
    finally:
        db_guard.drop_test_database(prod_parsed, existing_name)
    assert not artifact_dest.exists()


def test_failed_restore_cleans_up_created_target_and_artifacts(fork_backup, tmp_path):
    fork_url, parsed, _ = _fork()
    prod_parsed = parse_pg_url(settings.ORIGINAL_DATABASE_URL)
    target_name = _new_target_name()
    artifact_dest = tmp_path / "restored-artifacts"
    corrupt_backup = tmp_path / "backup-corrupt"
    shutil.copytree(fork_backup, corrupt_backup)
    dump = corrupt_backup / br.DUMP_FILENAME
    data = bytearray(dump.read_bytes())
    data[len(data) // 2] ^= 0xFF
    dump.write_bytes(bytes(data))

    with pytest.raises(br.BackupError):
        br.restore_backup(
            str(corrupt_backup), br.database_url_for(parsed, target_name),
            target_fingerprint=guard.fingerprint(parsed.hostname, parsed.port or 5432, target_name),
            artifact_root=str(artifact_dest),
            report_path=str(tmp_path / "report.json"),
            environ={},
        )
    assert not br._target_exists(prod_parsed, target_name)
    assert not artifact_dest.exists()
    db_guard.drop_test_database(prod_parsed, target_name)  # no-op if never created


def test_failed_restore_leaves_no_fallback_or_partial_artifacts(tmp_path, synthetic_dir):
    """An unreachable test target must fail without creating artifacts or falling back."""
    artifact_dest = tmp_path / "never-created"
    with pytest.raises(Exception):
        br.restore_backup(
            str(tmp_path / "does-not-exist"), UNREACHABLE_TEST_URL,
            target_fingerprint=guard.fingerprint("127.0.0.1", 1, "careeros_test_zz"),
            artifact_root=str(artifact_dest),
            report_path=str(tmp_path / "report.json"),
            environ={},
        )
    assert not artifact_dest.exists()
