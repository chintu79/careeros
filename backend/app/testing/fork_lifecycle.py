"""
Deterministic lifecycle for disposable PostgreSQL forks (Phase 3.0.5.1).

Every fork registered here is disposable by construction (prefix `careeros_test_`).
Cleanup order:
  1. dispose SQLAlchemy engines bound to the fork (checked-in and checked-out pools),
  2. terminate remaining backends *scoped to the exact fork database and current role*,
  3. guarded drop via db_guard.drop_test_database (prefix + ownership + zero-active rules),
  4. verify the database no longer exists,
  5. remove the lifecycle marker.

The marker (written at provision time) records the database name and server coordinates
but **no credentials**, and is 0600. Recovery of crashed runs only considers forks with
a marker *and* a correctly prefixed name *and* ownership by the current role *and* zero
active connections. Everything is idempotent.
"""

from __future__ import annotations

import gc
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from sqlalchemy.engine import Engine, make_url

from backend.app.testing import db_guard
from backend.app.testing.db_guard import (
    TEST_DB_PREFIX,
    _psql,
    parse_pg_url,
)

TOOL = "careeros-fork-lifecycle/3.0.5.1"
MARKER_DIRNAME = "careeros-fork-lifecycle"
_ENV_MARKER_DIR = "CAREEROS_FORK_MARKER_DIR"


class ForkLifecycleError(RuntimeError):
    """Cleanup could not complete; .report carries every detail needed to act."""

    def __init__(self, report: Dict[str, Any]):
        self.report = report
        super().__init__(report.get("error", "fork cleanup failed"))


def _marker_dir() -> Path:
    base = Path(os.environ.get(_ENV_MARKER_DIR, Path(tempfile.gettempdir()) / MARKER_DIRNAME))
    base.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(base, 0o700)
    except OSError:
        pass
    return base


def _marker_path(name: str) -> Path:
    return _marker_dir() / f"{name}.json"


def write_marker(name: str, *, host: str, port: int, username: str) -> Path:
    path = _marker_path(name)
    path.write_text(json.dumps({
        "database": name,
        "host": host,
        "port": port,
        "username": username,
        "tool": TOOL,
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def read_marker(name: str) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(_marker_path(name).read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(data, dict) and data.get("database") == name:
        return data
    return None


def remove_marker(name: str) -> None:
    try:
        _marker_path(name).unlink()
    except FileNotFoundError:
        pass


def _esc(value: str) -> str:
    return value.replace("'", "''")


def _url_key(url) -> tuple:
    return (url.host or "", url.port or 5432, url.database or "")


def database_exists(prod, database: str) -> bool:
    output = _psql(prod, "postgres",
                   f"SELECT 1 FROM pg_database WHERE datname = '{_esc(database)}'", check=False)
    return output.stdout.strip() == "1"


def _owned_connection_count(prod, database: str) -> int:
    output = _psql(
        prod,
        "postgres",
        (
            "SELECT count(*) FROM pg_stat_activity WHERE datname = '{db}' "
            "AND usename = current_user AND pid <> pg_backend_pid()"
        ).format(db=_esc(database)),
        check=False,
    )
    try:
        return int(output.stdout.strip() or "0")
    except ValueError:
        return -1


def terminate_owned_backends(prod, database: str) -> int:
    """
    Terminate backends connected to *this exact fork database*, owned by the current
    role only. Cannot touch the application, other forks or any other database.
    """
    listing = _psql(
        prod,
        "postgres",
        (
            "SELECT pid FROM pg_stat_activity WHERE datname = '{db}' "
            "AND usename = current_user AND pid <> pg_backend_pid()"
        ).format(db=_esc(database)),
        check=False,
    )
    pids = [line.strip() for line in listing.stdout.splitlines() if line.strip().isdigit()]
    for pid in pids:
        _psql(prod, "postgres", f"SELECT pg_terminate_backend({int(pid)})", check=False)
    return len(pids)


def dispose_engines_bound_to(database: str, prod) -> int:
    host, port = prod.hostname or "localhost", prod.port or 5432
    target = (host, port, database)
    disposed = 0
    for obj in list(gc.get_objects()):
        if not isinstance(obj, Engine):
            continue
        try:
            url = make_url(str(obj.url))
        except Exception:
            continue
        if _url_key(url) == target:
            try:
                obj.dispose()
                disposed += 1
            except Exception:
                pass
    return disposed


class OwnedFork:
    """A fork created through the lifecycle. Call cleanup() at workflow end."""

    def __init__(self, url: str, name: str, prod=None):
        self.url = url
        self.name = name
        self.prod = prod or parse_pg_url(_maintenance_url(url))

    def cleanup(self, *, reason: str = "workflow teardown") -> Dict[str, Any]:
        report: Dict[str, Any] = {
            "database": self.name,
            "reason": reason,
            "tool": TOOL,
            "steps": [],
            "success": False,
            "remaining_connections": None,
            "error": None,
            "recovery": (
                "python -m backend.app.testing.fork_lifecycle --recover --confirm "
                "(prefix careeros_test_, same-server owner check; never forces)"
            ),
        }

        def step(label: str, ok: bool, detail: str = "") -> None:
            report["steps"].append({"step": label, "ok": ok, "detail": detail})
            if not ok and report["error"] is None:
                report["error"] = f"{label}: {detail}"

        if not self.name.startswith(TEST_DB_PREFIX):
            step("prefix_check", False, f"database {self.name!r} lacks disposable prefix {TEST_DB_PREFIX!r}")
            return report

        step("prefix_check", True, self.name)

        try:
            disposed = dispose_engines_bound_to(self.name, self.prod)
            step("dispose_engines", True, f"{disposed} engine(s) disposed")
        except Exception as exc:
            step("dispose_engines", False, f"{type(exc).__name__}: {exc}")

        try:
            terminated = terminate_owned_backends(self.prod, self.name)
            step("terminate_owned_backends", True, f"{terminated} backend(s) terminated")
        except Exception as exc:
            step("terminate_owned_backends", False, f"{type(exc).__name__}: {exc}")

        remaining = _owned_connection_count(self.prod, self.name)
        report["remaining_connections"] = remaining
        if remaining < 0:
            step("connection_check", False, "could not count remaining connections")
        else:
            step("connection_check", remaining == 0, f"{remaining} connection(s) remaining")

        if database_exists(self.prod, self.name):
            try:
                verdict = db_guard.drop_test_database(self.prod, self.name)
            except Exception as exc:
                verdict = f"refused: {type(exc).__name__}: {exc}"
            dropped = str(verdict).startswith("dropped") or not database_exists(self.prod, self.name)
            step("guarded_drop", dropped, str(verdict))
        else:
            step("guarded_drop", True, "already absent")

        absent = not database_exists(self.prod, self.name)
        step("verify_absent", absent, "database gone" if absent else "database still present")

        failed = [s for s in report["steps"] if not s["ok"]]
        if not failed:
            remove_marker(self.name)
            step("marker_removed", True, "")
        else:
            # Keep the marker so crash recovery can rerun this teardown.
            step("marker_removed", True, "marker retained for recovery")

        report["success"] = all(s["ok"] for s in report["steps"])
        if report["success"]:
            report["error"] = None
        return report

    def cleanup_or_raise(self, *, reason: str = "workflow teardown") -> None:
        report = self.cleanup(reason=reason)
        if not report["success"]:
            raise ForkLifecycleError(report)


def _maintenance_url(fork_url: str) -> str:
    """Same server, same role, deliberately *no* maintenance database name encoded."""
    parsed = parse_pg_url(fork_url)
    return (
        f"postgresql+psycopg://{parsed.username}:{parsed.password}"
        f"@{parsed.hostname}:{parsed.port or 5432}/postgres"
    )


def provision(production_url: str, *, schema_only: bool = False) -> OwnedFork:
    """Create a disposable fork and register it for deterministic teardown."""
    if schema_only:
        url = db_guard.make_disposable_schema_only(production_url)
    else:
        url = db_guard.make_disposable_pg_database(production_url)
    parsed = parse_pg_url(url)
    marker_host = parsed.hostname or "localhost"
    marker_port = parsed.port or 5432
    marker_user = parsed.username or ""
    name = parsed.path.lstrip("/")
    write_marker(name, host=marker_host, port=marker_port, username=marker_user)
    return OwnedFork(url, name, parse_pg_url(_maintenance_url(url)))


def _production_basis():
    """
    Resolve the production-like basis used for fork coordinates. The suite prefers
    CAREEROS_CI_DATABASE_URL (the CI simulation host), then ORIGINAL_DATABASE_URL
    captured before conftest rewrites, then settings.DATABASE_URL. Whichever serves
    as the same server forks were created on is fine; comparisons below enforce exact
    match and refuse anything else.
    """
    from backend.app.config import settings

    candidates = []
    ci_url = os.environ.get("CAREEROS_CI_DATABASE_URL")
    if ci_url:
        candidates.append(("ci", ci_url))
    original = getattr(settings, "ORIGINAL_DATABASE_URL", None)
    if original and "/careeros_test_" not in original:
        candidates.append(("original", original))
    candidates.append(("settings", settings.DATABASE_URL))

    for label, url in candidates:
        try:
            parsed = parse_pg_url(url)
            return parsed
        except Exception:
            continue
    return parse_pg_url(settings.DATABASE_URL)


def reconcile_stale_markers(confirm: bool = False) -> List[Dict[str, Any]]:
    """
    Reconcile lifecycle markers against the expected fork server, WITHOUT ever
    dropping a database.

    A marker is removable only when all of the following hold:
      - it is a readable CareerOS lifecycle marker whose `database` field matches
        its filename and which carries complete host/port/username ownership metadata;
      - its host/port/username match this machine's fork basis exactly (foreign
        servers and roles are never contacted);
      - psql confirms the database is absent on that server.

    Everything else is reported retained — databases are never dropped, servers
    are never contacted for foreign markers, and ambiguity blocks any action.
    Idempotent: running twice removes nothing the second time.
    """
    verdicts: List[Dict[str, Any]] = []
    try:
        basis = _production_basis()
    except Exception as exc:
        return [{"database": "<all>", "removed": False,
                 "verdict": f"retain: cannot resolve fork-server basis: {exc}"}]

    for marker in sorted(_marker_dir().glob("*.json")):
        name = marker.stem
        entry: Dict[str, Any] = {"database": name, "removed": False, "verdict": None}

        data = read_marker(name)
        if data is None:
            entry["verdict"] = "invalid: unreadable or mismatched marker; retained"
            verdicts.append(entry)
            continue
        if not name.startswith(TEST_DB_PREFIX):
            entry["verdict"] = "invalid: not a CareerOS lifecycle marker (prefix mismatch); retained"
            verdicts.append(entry)
            continue

        host, port, user = data.get("host"), data.get("port"), data.get("username")
        try:
            port = int(port or 0)
        except (TypeError, ValueError):
            port = 0
        if not isinstance(host, str) or not isinstance(user, str) or not host or not user or not port:
            entry["verdict"] = "invalid: incomplete ownership metadata; retained"
            verdicts.append(entry)
            continue

        if host != (basis.hostname or "localhost") or port != int(basis.port or 5432):
            entry["verdict"] = "retain: marker server coordinates do not match this fork server"
            verdicts.append(entry)
            continue
        if user != basis.username:
            entry["verdict"] = f"retain: marker owner {user!r} does not match this server role"
            verdicts.append(entry)
            continue

        try:
            exists = database_exists(basis, name)
        except Exception as exc:
            entry["verdict"] = f"retain: server unreachable ({type(exc).__name__}); cannot verify; retained"
            verdicts.append(entry)
            continue

        if exists:
            entry["verdict"] = "retain: database present; marker is live (crash recovery finishes teardown)"
            verdicts.append(entry)
            continue

        if confirm:
            remove_marker(name)
            entry["removed"] = True
            entry["verdict"] = "removed: database confirmed absent; marker deleted"
        else:
            entry["verdict"] = "eligible: database confirmed absent (dry run; pass --confirm to remove)"
        verdicts.append(entry)

    return verdicts


# ---------------------------------------------------------------------------
# Crash recovery
# ---------------------------------------------------------------------------

def recover_stale_forks(confirm: bool = False) -> List[Dict[str, Any]]:
    """
    List (or drop, with confirm=True) forks carrying a lifecycle marker. Never touches
    unmarked databases. Requires prefix + same-server credentials + ownership by the
    current role + zero active connections before dropping.
    """
    results: List[Dict[str, Any]] = []
    try:
        basis = _production_basis()
    except Exception as exc:
        return [{"database": "<all>", "verdict": f"skip: cannot resolve production basis: {exc}", "dropped": False}]

    for marker in sorted(_marker_dir().glob(f"{TEST_DB_PREFIX}*.json")):
        name = marker.stem
        data = read_marker(name)
        entry: Dict[str, Any] = {"database": name, "dropped": False, "verdict": None}

        if not name.startswith(TEST_DB_PREFIX):
            entry["verdict"] = "skip: prefix check failed"
            results.append(entry)
            continue
        if data is None:
            entry["verdict"] = "skip: unreadable or mismatched marker"
            results.append(entry)
            continue
        if (
            data.get("host") != basis.hostname
            or int(data.get("port") or 0) != int(basis.port or 5432)
            or data.get("username") != basis.username
        ):
            entry["verdict"] = "skip: marker server coordinates do not match this server"
            results.append(entry)
            continue

        exists = database_exists(basis, name)
        if not exists:
            entry["verdict"] = "already absent; marker removed"
            if confirm:
                remove_marker(name)
            results.append(entry)
            continue

        owner = db_guard._database_owner(basis, name)
        if owner != basis.username:
            entry["verdict"] = "skip: owner mismatch"
            results.append(entry)
            continue
        remaining = _owned_connection_count(basis, name)
        if remaining != 0:
            entry["verdict"] = f"skip: {remaining} connection(s) still active"
            results.append(entry)
            continue

        if confirm:
            fork = OwnedFork(
                _maintenance_url(
                    f"postgresql+psycopg://{basis.username}:{basis.password}@{basis.hostname}:{basis.port or 5432}/{name}"
                ),
                name,
                basis,
            )
            report = fork.cleanup(reason="crash recovery")
            entry["dropped"] = report["success"]
            entry["verdict"] = "dropped" if report["success"] else f"failed: {report['error']}"
        else:
            entry["verdict"] = "eligible to drop (dry run)"
        results.append(entry)
    return results


def _main() -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog="backend.app.testing.fork_lifecycle")
    parser.add_argument("--recover", action="store_true", help="list or drop forks carrying lifecycle markers")
    parser.add_argument("--reconcile-markers", action="store_true", help="remove markers whose fork database is confirmed absent (never drops a database)")
    parser.add_argument("--confirm", action="store_true", help="actually drop eligible forks (default is dry run)")
    args = parser.parse_args()
    if args.reconcile_markers:
        verdicts = reconcile_stale_markers(confirm=args.confirm)
        for entry in verdicts:
            print(f"{entry['verdict']} — {entry['database']}")
        removed = sum(1 for v in verdicts if v.get("removed"))
        print(f"reconcile-markers: {removed} removed, {len(verdicts) - removed} retained/invalid")
        return 0
    if not args.recover:
        parser.error("pass --recover or --reconcile-markers")
    results = recover_stale_forks(confirm=args.confirm)
    for entry in results:
        print(f"{entry['verdict']} — {entry['database']}")
    if args.confirm:
        failed = [e for e in results if not e.get("dropped")]
        return 1 if failed and any(not str(e.get("verdict", "")).startswith("already absent") for e in failed) else 0
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_main())
