"""
Migration target guard + audit trail.

Rules enforced here:
- The target database is classified before anything connects:
    test        -> name starts with careeros_test_
    development -> local host, non-production database name, dev/test env
    production  -> production env, production database name, or any remote host
- Every execution requires --confirm AND --target <fingerprint>.
- Production additionally requires --authorize-production AND
  CAREEROS_MIGRATION_AUTHORIZATION=<fingerprint> (separate from --confirm).
- Anything unrecognized is refused; nothing silently proceeds.
- Dry-runs never connect.

Only sanitized identifiers are printed or persisted: no credentials, no URLs.
"""
from __future__ import annotations

import getpass
import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.engine import Engine

from backend.app.testing.db_guard import TEST_DB_PREFIX, parse_pg_url


class MigrationRefused(RuntimeError):
    """Safety refusal. Never converted into a warning."""


_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]"}
_PRODUCTION_ENVIRONMENTS = {"production", "prod"}
_AUTHORIZATION_ENV = "CAREEROS_MIGRATION_AUTHORIZATION"
_AUDIT_TABLE = "migration_audit_log"


@dataclass(frozen=True)
class MigrationTarget:
    host: str
    port: int
    database: str
    environment: str
    kind: str
    fingerprint: str

    @property
    def display(self) -> str:
        return (
            f"{self.database}@{self.host}:{self.port} "
            f"[{self.kind}; env={self.environment}] fp={self.fingerprint}"
        )


def sanitize(text_value: str) -> str:
    """Strip anything credential-shaped before printing or auditing."""
    return re.sub(r"://[^@\s]+@", "://***@", text_value or "")[:500]


def fingerprint(host: str, port: int, database: str) -> str:
    return hashlib.sha256(f"{host}:{port}/{database}".encode()).hexdigest()[:16]


def production_database_name() -> str:
    return os.getenv("CAREEROS_PRODUCTION_DB_NAME", "interniq").strip() or "interniq"


def resolve_target(database_url: str, environment: Optional[str] = None) -> MigrationTarget:
    """Classify the target or refuse. Never guesses in favour of proceeding."""
    try:
        parsed = parse_pg_url(database_url or "")
    except Exception as exc:
        raise MigrationRefused(f"unrecognized database target: {sanitize(str(exc))}") from exc

    host = (parsed.hostname or "").strip()
    database = (parsed.path or "").lstrip("/").strip()
    port = parsed.port or 5432
    env = (environment or os.getenv("ENVIRONMENT", "development")).strip().lower()

    if not host or not database:
        raise MigrationRefused("unrecognized database target: host and database name are required")

    if database.startswith(TEST_DB_PREFIX):
        kind = "test"
    elif env in _PRODUCTION_ENVIRONMENTS or database == production_database_name():
        kind = "production"
    elif host in _LOCAL_HOSTS:
        kind = "development"
    else:
        # Remote host that is neither a known test fork nor explicitly local is
        # treated as production: it must go through the production gate.
        kind = "production"

    return MigrationTarget(
        host=host, port=port, database=database, environment=env,
        kind=kind, fingerprint=fingerprint(host, port, database),
    )


def authorize(
    target: MigrationTarget,
    *,
    confirm: bool,
    target_fingerprint: Optional[str],
    authorize_production: bool,
    environ: Optional[Mapping[str, str]] = None,
) -> str:
    """Return the authorization method, or raise MigrationRefused."""
    env = environ if environ is not None else os.environ

    if not confirm:
        raise MigrationRefused("--confirm is required to execute (dry-run never executes).")

    if not target_fingerprint:
        raise MigrationRefused(
            f"explicit target verification required: pass --target {target.fingerprint} "
            f"(from --dry-run). Target: {target.display}"
        )
    if target_fingerprint.strip().lower() != target.fingerprint:
        raise MigrationRefused(
            f"target fingerprint mismatch: got {target_fingerprint!r}, expected "
            f"{target.fingerprint!r} for {target.display}"
        )

    if target.kind == "production":
        if not authorize_production:
            raise MigrationRefused(
                f"refusing production target {target.display}: "
                "add --authorize-production and set "
                f"{_AUTHORIZATION_ENV}={target.fingerprint}"
            )
        token = (env.get(_AUTHORIZATION_ENV) or "").strip()
        if not token:
            raise MigrationRefused(
                f"refusing production target {target.display}: {_AUTHORIZATION_ENV} is not set"
            )
        if token != target.fingerprint:
            raise MigrationRefused(
                f"refusing production target {target.display}: {_AUTHORIZATION_ENV} does not "
                "match the target fingerprint"
            )
        return "confirm+target+production-authorization"

    return "confirm+target"


def assert_engine_matches_target(engine: Engine, target: MigrationTarget) -> None:
    """Fail closed if the engine binding differs from the authorized target."""
    url = engine.url
    bound = (url.host or "", url.port or 5432, url.database or "")
    expected = (target.host, target.port, target.database)
    if bound != expected:
        raise MigrationRefused(
            "engine binding does not match the authorized target; refusing "
            f"(engine binds {bound[2]}@{bound[0]}:{bound[1]})"
        )


def _schema_snapshot(engine: Engine) -> Dict[str, set]:
    with engine.connect() as conn:
        tables = {r[0] for r in conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        ))}
        columns = {f"{r[0]}.{r[1]}" for r in conn.execute(text(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema='public'"
        ))}
        indexes = {r[0] for r in conn.execute(text(
            "SELECT indexname FROM pg_indexes WHERE schemaname='public'"
        ))}
    return {"tables": tables, "columns": columns, "indexes": indexes}


def _schema_delta(before: Dict[str, set], after: Dict[str, set]) -> Dict[str, list]:
    delta = {}
    for key in ("tables", "columns", "indexes"):
        added = sorted(after[key] - before[key])[:200]
        removed = sorted(before[key] - after[key])[:200]
        if added:
            delta[f"added_{key}"] = added
        if removed:
            delta[f"removed_{key}"] = removed
    return delta


def _ensure_audit_table(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {_AUDIT_TABLE} (
                id SERIAL PRIMARY KEY,
                migration_id VARCHAR(120) NOT NULL,
                target_environment VARCHAR(32) NOT NULL,
                target_kind VARCHAR(16) NOT NULL,
                target_fingerprint VARCHAR(64) NOT NULL,
                target_display VARCHAR(255) NOT NULL,
                authorization_method VARCHAR(80) NOT NULL,
                operator VARCHAR(120) NOT NULL,
                started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                completed_at TIMESTAMPTZ,
                success BOOLEAN NOT NULL DEFAULT false,
                applied_changes JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                error_summary TEXT
            )
        """))


def execute_authorized(
    engine: Engine,
    *,
    migration_id: str,
    target: MigrationTarget,
    authorization_method: str,
    action: Callable[[], Optional[Dict[str, Any]]],
) -> Dict[str, Any]:
    """
    Run an already-authorized migration with a durable audit record.

    The audit row is committed before the migration starts, so a crash leaves a
    visible failed/incomplete attempt. Business data is never written by the audit.
    """
    assert_engine_matches_target(engine, target)

    before = _schema_snapshot(engine)
    _ensure_audit_table(engine)
    with engine.begin() as conn:
        audit_id = conn.execute(text(f"""
            INSERT INTO {_AUDIT_TABLE}
                (migration_id, target_environment, target_kind, target_fingerprint,
                 target_display, authorization_method, operator)
            VALUES (:mid, :env, :kind, :fp, :display, :auth, :operator)
            RETURNING id
        """), {
            "mid": migration_id, "env": target.environment, "kind": target.kind,
            "fp": target.fingerprint, "display": target.display,
            "auth": authorization_method, "operator": getpass.getuser()[:120],
        }).scalar_one()

    try:
        extra = action() or {}
    except Exception as exc:
        with engine.begin() as conn:
            conn.execute(text(f"""
                UPDATE {_AUDIT_TABLE}
                SET completed_at = now(), success = false, error_summary = :err
                WHERE id = :id
            """), {"err": sanitize(f"{type(exc).__name__}: {exc}"), "id": audit_id})
        raise

    after = _schema_snapshot(engine)
    applied = _schema_delta(before, after)
    applied.update(extra)
    with engine.begin() as conn:
        conn.execute(text(f"""
            UPDATE {_AUDIT_TABLE}
            SET completed_at = now(), success = true, applied_changes = CAST(:changes AS jsonb)
            WHERE id = :id
        """), {"changes": json.dumps(applied), "id": audit_id})

    return {"audit_id": audit_id, "applied_changes": applied}
