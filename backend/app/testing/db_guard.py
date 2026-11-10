"""
Safety guard + provisioning for the disposable PostgreSQL test database.

The CareerOS backend test suite is PostgreSQL-native (pg_trgm/GIN indexes,
advisory locks, psycopg concurrency semantics). Empty-schema test databases
leave ~30 tests failing only because they exercise behavior anchored on a
consistent snapshot (master resume id=1, the tracked pipeline feeding
command-center assertions, replication of evidence relationships). Re-seeding
every one of those fixtures risks subtly altering semantics, so the suite uses
a disposable, uniquely-named, same-server full CLONE of the live database.

The alternative (schema-only clone) is retained as make_disposable_schema_only
but is not the suite default; full clones are justified because they preserve
the exact data topology those tests are written against without code changes.

Risks accepted, mitigations enforced:

1. The clone contains live records at dump time. Dump artifacts never persist —
   they are deleted immediately after pg_restore. The fork is dropped at
   interpreter exit (best effort, verified after every full run: 0 leftovers).
2. The fork is never opened by production code paths. conftest rewrites both
   the cached settings object and os.environ before the engine is constructed.
   The engine fingerprint is asserted to carry the pinned prefix.
3. Cleanup is strict: only databases whose name starts with PINNED_PREFIX,
   owned by the connecting role, with zero active connections, are dropped —
   never by broad patterns, never outside the prefix, never with FORCE by
   default.
4. Logs must not print the production URL; the fork DB name is printed, row
   contents never are.

Maintenance (stale forks left by a hard crash):
    PYTHONPATH=. venv/bin/python -m backend.app.testing.db_guard          # dry run, prints a plan
    PYTHONPATH=. venv/bin/python -m backend.app.testing.db_guard --confirm # drops eligible forks

Eligibility = pinned prefix + owner == current role + zero active connections.
Human-readable output lists names only; never row contents.
"""

import atexit
import os
import subprocess
import sys
import uuid
from urllib.parse import urlparse

TEST_DB_PREFIX = "careeros_test_"
EXPECTED_MIN_TABLES = 20


def parse_pg_url(url: str):
    p = urlparse(url) if url else None
    if p is None or p.scheme not in ("postgresql", "postgresql+psycopg"):
        raise RuntimeError(
            f"Test database must be PostgreSQL (scheme postgresql). Got scheme: "
            f"{(p.scheme if p else 'none')!r}. The suite is PostgreSQL-native."
        )
    return p


def is_test_database_name(name: str) -> bool:
    return bool(name) and name.startswith(TEST_DB_PREFIX)


def assert_disposable_pg_url(url: str, production_url: str = ""):
    """Validate a caller-provided test database URL against the safety contract."""
    prod = parse_pg_url(production_url) if production_url else None
    test = parse_pg_url(url)
    test_name = test.path.lstrip("/")
    if prod is not None and (test.hostname != prod.hostname or test.port != prod.port):
        raise RuntimeError(
            "Test database must live on the same host/port as the production database "
            "(same-server fork requirement)."
        )
    if not is_test_database_name(test_name):
        raise RuntimeError(
            f"Test database name must start with {TEST_DB_PREFIX!r}. Got {test_name!r}."
        )
    if prod is not None:
        prod_name = prod.path.lstrip("/")
        if test_name == prod_name:
            raise RuntimeError("Test database name resolves to the production database name; refusing.")
        if test.geturl() == prod.geturl():
            raise RuntimeError("Test database URL is identical to the production URL; refusing.")
    return test


def _psql_env(p) -> dict:
    return dict(os.environ, PGPASSWORD=p.password or "")


def _psql(p, database, sql, check=True):
    res = subprocess.run(
        ["psql", "-v", "ON_ERROR_STOP=1", "-h", p.hostname, "-p", str(p.port or 5432),
         "-U", p.username, "-d", database, "-tAX", "-c", sql],
        env=_psql_env(p), capture_output=True, text=True, timeout=120,
    )
    if check and res.returncode != 0:
        raise RuntimeError(f"psql failed: {res.stderr.strip()[:300]}")
    return res


def _fork_database_url(prod, test_db: str) -> str:
    p = urlparse(prod) if isinstance(prod, str) else prod
    return f"postgresql+psycopg://{p.username}:{p.password}@{p.hostname}:{p.port or 5432}/{test_db}"


def make_disposable_pg_database(production_url: str) -> str:
    """Full clone fork (default for this suite — see module docstring)."""
    prod = parse_pg_url(production_url)
    test_db = TEST_DB_PREFIX + uuid.uuid4().hex[:12]
    host, port, user, password = prod.hostname, prod.port or 5432, prod.username, prod.password
    src_db = prod.path.lstrip("/")
    env = _psql_env(prod)

    def run(cmd):
        res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
        if res.returncode != 0:
            raise RuntimeError(f"Command failed ({' '.join(cmd[:2])}): {res.stderr.strip()[:300]}")
        return res

    dump_file = f"/tmp/opencode/careeros-test-backup-{test_db}.dump"
    try:
        run(["psql", "-v", "ON_ERROR_STOP=1", "-h", host, "-p", str(port), "-U", user,
             "-d", "postgres", "-c", f'CREATE DATABASE "{test_db}"'])
        run(["pg_dump", "--format=custom", "--no-owner", "--no-privileges",
             "-h", host, "-p", str(port), "-U", user, "-d", src_db, "-f", dump_file])
        run(["pg_restore", "--no-owner", "--no-privileges",
             "-h", host, "-p", str(port), "-U", user, "-d", test_db, dump_file])
    except Exception:
        # Partial provisioning must never leave a fork behind.
        try:
            subprocess.run(
                ["psql", "-v", "ON_ERROR_STOP=1", "-h", host, "-p", str(port), "-U", user,
                 "-d", "postgres", "-c", f'DROP DATABASE IF EXISTS "{test_db}"'],
                env=env, capture_output=True, text=True, timeout=60,
            )
        finally:
            if os.path.exists(dump_file):
                os.remove(dump_file)
        raise
    finally:
        if os.path.exists(dump_file):
            os.remove(dump_file)

    disposable_url = _fork_database_url(prod, test_db)
    _register_drop_hook(prod, test_db)
    try:
        from backend.app.testing import fork_lifecycle as _fl
        p = parse_pg_url(disposable_url)
        _fl.write_marker(test_db, host=p.hostname or "localhost", port=p.port or 5432, username=p.username or "")
    except Exception as exc:
        print(f"WARNING: could not write fork marker for {test_db}: {exc}", file=sys.stderr)
    return disposable_url


def make_disposable_schema_only(production_url: str) -> str:
    """Privacy-improving variant: schema-only clone, no rows copied anywhere."""
    prod = parse_pg_url(production_url)
    test_db = TEST_DB_PREFIX + uuid.uuid4().hex[:12]
    host, port, user, password = prod.hostname, prod.port or 5432, prod.username, prod.password
    src_db = prod.path.lstrip("/")
    env = _psql_env(prod)

    def run(cmd):
        res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
        if res.returncode != 0:
            raise RuntimeError(f"Command failed ({' '.join(cmd[:2])}): {res.stderr.strip()[:300]}")
        return res

    dump_file = f"/tmp/opencode/schema-{test_db}.dump"
    try:
        run(["psql", "-v", "ON_ERROR_STOP=1", "-h", host, "-p", str(port), "-U", user,
             "-d", "postgres", "-c", f'CREATE DATABASE "{test_db}"'])
        run(["pg_dump", "--schema-only", "--format=custom", "--no-owner", "--no-privileges",
             "-h", host, "-p", str(port), "-U", user, "-d", src_db, "-f", dump_file])
        run(["pg_restore", "--no-owner", "--no-privileges",
             "-h", host, "-p", str(port), "-U", user, "-d", test_db, dump_file])
    except Exception:
        # Partial provisioning must never leave a fork behind.
        try:
            subprocess.run(
                ["psql", "-v", "ON_ERROR_STOP=1", "-h", host, "-p", str(port), "-U", user,
                 "-d", "postgres", "-c", f'DROP DATABASE IF EXISTS "{test_db}"'],
                env=env, capture_output=True, text=True, timeout=60,
            )
        finally:
            if os.path.exists(dump_file):
                os.remove(dump_file)
        raise
    finally:
        if os.path.exists(dump_file):
            os.remove(dump_file)

    disposable_url = _fork_database_url(prod, test_db)
    _register_drop_hook(prod, test_db)
    try:
        from backend.app.testing import fork_lifecycle as _fl
        p = parse_pg_url(disposable_url)
        _fl.write_marker(test_db, host=p.hostname or "localhost", port=p.port or 5432, username=p.username or "")
    except Exception as exc:
        print(f"WARNING: could not write fork marker for {test_db}: {exc}", file=sys.stderr)
    return disposable_url


def _current_database_info(prod, name: str) -> tuple[str, int]:
    row = _psql(prod, "postgres", f"""
        select d.datname, c.count
        from (select pg_database.datname from pg_database where datname = '{_esc_name(name)}') d
        cross join (select count(*) as count from pg_stat_activity where datname = '{_esc_name(name)}') c
    """).stdout.strip()
    if not row:
        return "", -1
    _name, conns = row.rsplit("|", 1)
    return _name.strip(), int(conns.strip())


def _esc_name(name: str) -> str:
    return name.replace("'", "''")


def _database_owner(prod, name: str) -> str:
    row = _psql(prod, "postgres", f"select pg_get_userbyid(datdba) from pg_database where datname = '{_esc_name(name)}'").stdout.strip()
    return row


def drop_test_database(prod, name: str) -> str:
    """
    Eligible-only drop. Returns a short verdict string, never row contents.
    """
    owner = _database_owner(prod, name)
    if owner != prod.username:
        return f"skip ({name}): not owned by the current role"
    _, conns = _current_database_info(prod, name)
    if conns > 0:
        return f"skip ({name}): {conns} active connection(s)"
    res = _psql(prod, "postgres", f'DROP DATABASE "{_esc_name(name)}"', check=False)
    if res.returncode != 0:
        return f"skip ({name}): drop refused by server"
    return f"dropped {name}"


def cleanup_stale_test_databases(production_url: str, confirm: bool = False) -> list[str]:
    """
    List (and optionally drop) stale careeros_test_* databases left by hard crashes.

    Eligibility is checked per database: pinned prefix, owned by the current role,
    zero active connections. Never drops outside the prefix, never FORCE drops,
    never prints row contents.
    """
    prod = parse_pg_url(production_url)
    res = _psql(prod, "postgres", f"""
        select datname from pg_database
        where datname like '{TEST_DB_PREFIX}%' and not datistemplate
        order by datname
    """)
    names = [l.strip() for l in res.stdout.splitlines() if l.strip()]
    verdicts = []
    for name in names:
        if confirm:
            verdicts.append(drop_test_database(prod, name))
        else:
            owner = _database_owner(prod, name)
            _, conns = _current_database_info(prod, name)
            ok = owner == prod.username and conns == 0
            verdicts.append(f"{'eligible' if ok else 'skip'} ({name}): owner={owner}, connections={conns}")
    return verdicts


def _register_drop_hook(prod, test_db: str):
    """Best-effort safety net. The real teardown lives in fork_lifecycle / the conftest finalizer."""
    import atexit

    @atexit.register
    def _drop_fork():
        try:
            from backend.app.testing import fork_lifecycle

            url = _fork_database_url(prod, test_db)
            report = fork_lifecycle.OwnedFork(url, test_db, prod).cleanup(reason="atexit safety net")
            if not report["success"]:
                print(
                    f"FATAL: disposable fork {test_db} was NOT dropped at exit "
                    f"(remaining_connections={report['remaining_connections']}; error={report['error']}). "
                    f"Recover with: {report['recovery']}",
                    file=sys.stderr,
                )
        except Exception as exc:
            print(
                f"FATAL: disposable fork {test_db} cleanup raised {type(exc).__name__}: {exc}. "
                f"Recover with: python -m backend.app.testing.fork_lifecycle --recover --confirm",
                file=sys.stderr,
            )


def _main():
    from backend.app.config import settings
    prod_url = getattr(settings, "ORIGINAL_DATABASE_URL", None) or settings.DATABASE_URL
    if not prod_url:
        print("DATABASE_URL unavailable — refusing to run", file=sys.stderr)
        return 1
    confirm = "--confirm" in sys.argv
    print("stale test database cleanup (prefix: %s)%s" % (TEST_DB_PREFIX, " [CONFIRM]" if confirm else " [dry run]"))
    for line in cleanup_stale_test_databases(prod_url, confirm=confirm):
        print(line)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
