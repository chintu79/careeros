"""
CI-only seeding entrypoint.

Creates the seeded CI database using the already-built backend image's Python
interpreter. NEVER used by the live application; does not write to production.

Usage:
    python -m backend.app.testing.seed_ci_cli           # uses $DATABASE_URL
    python -m backend.app.testing.seed_ci_cli <url>      # explicit target url
"""
import sys

from sqlalchemy import create_engine, text

from backend.app.testing import synthetic_fixture


def _load_url() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    from backend.app.config import settings

    return settings.DATABASE_URL


def main() -> int:
    url = _load_url()

    # Safety: refuse anything outside the disposable CI database names.
    from backend.app.testing.db_guard import TEST_DB_PREFIX, parse_pg_url

    parsed = parse_pg_url(url)
    dbname = (parsed.path or "").lstrip("/")
    if not (dbname.startswith(TEST_DB_PREFIX) or dbname.startswith("careeros_ci_")):
        print(f"REFUSED: seed_ci_cli only targets disposable CI databases, got {dbname!r}")
        return 3


    print(f"seeding the CI database")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    from backend.app.services.database_migration import run_database_migrations
    run_database_migrations(engine)

    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import delete
    from backend.app.models.application import ApplicationRecord
    from backend.app.models.application_transition import ApplicationStageTransition
    from backend.app.models.candidate import CandidateProfile
    from backend.app.models.candidate_opportunity_match import CandidateOpportunityMatch
    from backend.app.models.company import Company
    from backend.app.models.discovery_ranking_snapshot import DiscoveryRankingSnapshot
    from backend.app.models.opportunity import Opportunity
    from backend.app.models.preferences import UserPreferences
    from backend.app.models.resume import ResumeDocument
    from backend.app.models.resume_version import ResumeVersion
    from backend.app.models.source import JobSource

    SessionCfg = sessionmaker(bind=engine)
    with SessionCfg() as db:
        db.execute(delete(CandidateOpportunityMatch))
        db.execute(delete(DiscoveryRankingSnapshot))
        db.execute(delete(ApplicationStageTransition))
        db.execute(delete(ApplicationRecord))
        db.execute(delete(ResumeVersion))
        db.execute(delete(ResumeDocument))
        db.execute(delete(Opportunity))
        db.execute(delete(Company))
        db.execute(delete(UserPreferences))
        db.execute(delete(JobSource))
        db.execute(delete(CandidateProfile))
        db.commit()

    engine.dispose()
    engine = create_engine(url)
    from backend.app.testing.synthetic_fixture import _seed_synthetic_rows

    with engine.begin() as conn:
        conn.execute(text("SET search_path TO public"))
    _seed_synthetic_rows(engine)
    print("seed complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
