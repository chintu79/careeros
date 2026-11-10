import logging
from sqlalchemy import text
from sqlalchemy.engine import Engine
from backend.app.database import engine as default_engine, Base
import backend.app.models.discovery_ranking_snapshot  # noqa: F401

logger = logging.getLogger(__name__)

MIGRATION_ADVISORY_LOCK_ID = 42000101

def run_database_migrations(engine: Engine = None) -> None:
    """
    Executes database table creation and schema migrations inside a single PostgreSQL transaction
    protected by an advisory transaction lock (pg_advisory_xact_lock).
    
    Guarantees:
    1. Single Connection & Single Transaction: Advisory lock and all DDL statements share
       the exact same PostgreSQL connection and transaction.
    2. Multi-Worker Serialization: Multiple workers starting up simultaneously serialize on
       the advisory lock, preventing catalog race conditions or deadlocks.
    3. Fail-Fast Rollback: Any exception immediately rolls back the transaction, releases
       the lock, and raises RuntimeError so the application cannot start in a partially migrated state.
    4. Idempotency: All DDL statements are idempotent (CREATE TABLE IF NOT EXISTS via metadata,
       ADD COLUMN IF NOT EXISTS, and conditional constraint creation).
    """
    db_engine = engine or default_engine
    logger.info("Executing transactional database migrations with advisory lock %d...", MIGRATION_ADVISORY_LOCK_ID)

    try:
        with db_engine.begin() as conn:
            # 1. Acquire transaction-level exclusive advisory lock
            conn.execute(text(f"SELECT pg_advisory_xact_lock({MIGRATION_ADVISORY_LOCK_ID});"))
            
            # 2. Run metadata table creation on the locked connection
            Base.metadata.create_all(bind=conn)
            
            # 3. Add structured_content JSONB columns if not present
            conn.execute(text("ALTER TABLE resume_documents ADD COLUMN IF NOT EXISTS structured_content JSONB;"))
            conn.execute(text("ALTER TABLE resume_versions ADD COLUMN IF NOT EXISTS structured_content JSONB;"))
            
            # 4. Add unique constraint on resume_versions(resume_id, version_number) if not present
            conn.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'uq_resume_version_resume_id_version_number'
                    ) THEN
                        ALTER TABLE resume_versions 
                        ADD CONSTRAINT uq_resume_version_resume_id_version_number 
                        UNIQUE (resume_id, version_number);
                    END IF;
                END $$;
            """))

            # 5. Iteration 1.8: Candidate-Scoped Match Result Isolation
            # Table + constraints only. Data backfill is an explicit operator command (ops/backfill_matches.py).
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS candidate_opportunity_matches (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    candidate_id INTEGER NOT NULL REFERENCES candidate_profiles(id) ON DELETE CASCADE,
                    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
                    match_score DOUBLE PRECISION DEFAULT 0.0,
                    eligibility_status VARCHAR(50) DEFAULT 'eligible',
                    match_analysis JSONB DEFAULT '{}'::jsonb,
                    candidate_content_hash VARCHAR(64) NOT NULL,
                    opportunity_content_hash VARCHAR(64) NOT NULL,
                    engine_version VARCHAR(20) DEFAULT '1.9.0',
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
                    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
                );
                
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'uq_candidate_profiles_id_user'
                    ) THEN
                        ALTER TABLE candidate_profiles
                        ADD CONSTRAINT uq_candidate_profiles_id_user
                        UNIQUE (id, user_id);
                    END IF;
                END $$;

                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'uq_candidate_opportunity_match_user_opp'
                    ) THEN
                        ALTER TABLE candidate_opportunity_matches
                        ADD CONSTRAINT uq_candidate_opportunity_match_user_opp
                        UNIQUE (user_id, opportunity_id);
                    END IF;
                END $$;

                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'fk_cand_opp_match_cand_user'
                    ) THEN
                        ALTER TABLE candidate_opportunity_matches
                        ADD CONSTRAINT fk_cand_opp_match_cand_user
                        FOREIGN KEY (candidate_id, user_id)
                        REFERENCES candidate_profiles (id, user_id)
                        ON DELETE CASCADE;
                    END IF;
                END $$;

                DROP INDEX IF EXISTS ix_candidate_opp_match_user_opp;
                CREATE INDEX IF NOT EXISTS ix_candidate_opp_match_cand_id ON candidate_opportunity_matches (candidate_id);
                CREATE INDEX IF NOT EXISTS ix_candidate_opp_match_opp_id ON candidate_opportunity_matches (opportunity_id);
                CREATE INDEX IF NOT EXISTS ix_candidate_opp_match_score ON candidate_opportunity_matches (match_score);
            """))

            # §5 business-data backfill removed from startup. See ops/backfill_matches.py

            # 6. Iteration 2.2: Distributed Ranking Snapshots & Stale-Write Protection
            conn.execute(text("""
                ALTER TABLE candidate_profiles ADD COLUMN IF NOT EXISTS evidence_version INTEGER DEFAULT 1 NOT NULL;
                ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS content_version INTEGER DEFAULT 1 NOT NULL;
                ALTER TABLE candidate_opportunity_matches ADD COLUMN IF NOT EXISTS candidate_evidence_version INTEGER DEFAULT 1 NOT NULL;
                ALTER TABLE candidate_opportunity_matches ADD COLUMN IF NOT EXISTS opportunity_content_version INTEGER DEFAULT 1 NOT NULL;

                CREATE TABLE IF NOT EXISTS discovery_ranking_snapshots (
                    snapshot_key VARCHAR(128) PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    signature VARCHAR(64) NOT NULL,
                    candidate_evidence_version VARCHAR(64) NOT NULL,
                    total_count INTEGER NOT NULL,
                    snapshot_ids JSONB NOT NULL,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
                    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_disc_snap_user_id ON discovery_ranking_snapshots(user_id);
                CREATE INDEX IF NOT EXISTS idx_disc_snap_expires_at ON discovery_ranking_snapshots(expires_at);
            """))

            # 7. Iteration 2.3: Mutation-Safe Pagination, Session IDs & GIN Indexing
            conn.execute(text("""
                ALTER TABLE discovery_ranking_snapshots ADD COLUMN IF NOT EXISTS snapshot_id VARCHAR(64);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_disc_snap_session_id ON discovery_ranking_snapshots(snapshot_id);
                CREATE INDEX IF NOT EXISTS idx_disc_snap_ids_gin ON discovery_ranking_snapshots USING GIN (snapshot_ids);
            """))

            # 8. Iteration 2.4: Monotonic Evaluation Generations & Engine Ordering
            conn.execute(text("""
                ALTER TABLE candidate_opportunity_matches ADD COLUMN IF NOT EXISTS engine_generation INTEGER DEFAULT 2 NOT NULL;
                -- Fresh databases created by metadata lack the server default; production has one.
                ALTER TABLE candidate_opportunity_matches ALTER COLUMN engine_generation SET DEFAULT 2;
                CREATE INDEX IF NOT EXISTS idx_cand_opp_match_engine_gen ON candidate_opportunity_matches(engine_generation);
                UPDATE candidate_opportunity_matches SET engine_generation = 2 WHERE engine_generation IS NULL;
            """))

            # 9. Iteration 2.8: Candidate Onboarding, Profile Completion & Personalized Activation
            conn.execute(text("""
                ALTER TABLE candidate_profiles ADD COLUMN IF NOT EXISTS onboarding_status VARCHAR(50) DEFAULT 'not_started';
                ALTER TABLE candidate_profiles ADD COLUMN IF NOT EXISTS onboarding_step INTEGER DEFAULT 1;
                ALTER TABLE candidate_profiles ADD COLUMN IF NOT EXISTS career_goals JSONB DEFAULT '{}'::jsonb;
            """))

            # 11. Iteration 3.0.2: Rate Limiting Store (shared across workers)
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS rate_limit_buckets (
                    id SERIAL PRIMARY KEY,
                    bucket_key VARCHAR(128) NOT NULL UNIQUE,
                    tokens DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    capacity DOUBLE PRECISION NOT NULL,
                    refill_per_second DOUBLE PRECISION NOT NULL,
                    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_rate_limit_buckets_key ON rate_limit_buckets(bucket_key);
            """))

            # 10. Iteration 2.8.1: Strict Candidate Record Uniqueness & Idempotency Enforcing
            conn.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'uq_candidate_profiles_user_id'
                    ) THEN
                        ALTER TABLE candidate_profiles 
                        ADD CONSTRAINT uq_candidate_profiles_user_id 
                        UNIQUE (user_id);
                    END IF;
                END $$;
            """))

        logger.info("Database migrations successfully executed and committed.")
    except Exception as e:
        logger.critical(f"Database migration transaction failed: {e}", exc_info=True)
        raise RuntimeError(f"Database migration transaction failed: {e}") from e


def run_schema_migrations(engine: Engine = None) -> None:
    """Alias for explicit operator invocation. Same transactional advisory lock."""
    run_database_migrations(engine)


def ops_backfill_candidate_matches(engine: Engine = None, dry_run: bool = False) -> int:
    """
    Explicit operator command: back-fill candidate_opportunity_matches from opportunities.match_analysis.
    No-op when nothing to do. Safe to re-run (ON CONFLICT DO NOTHING).
    """
    db_engine = engine or default_engine
    sql = """
        INSERT INTO candidate_opportunity_matches (
            user_id, candidate_id, opportunity_id, match_score, eligibility_status,
            match_analysis, candidate_content_hash, opportunity_content_hash,
            engine_version, created_at, updated_at
        )
        SELECT 
            COALESCE(
                (opp.match_analysis->>'user_id')::integer,
                opp.user_id,
                cand.user_id
            ) AS user_id,
            cand.id AS candidate_id,
            opp.id AS opportunity_id,
            COALESCE(opp.match_score, 0.0) AS match_score,
            COALESCE(opp.eligibility_status, 'eligible') AS eligibility_status,
            COALESCE(opp.match_analysis, '{}'::json) AS match_analysis,
            COALESCE(opp.match_analysis->>'candidate_content_hash', 'legacy_hash') AS candidate_content_hash,
            COALESCE(opp.match_analysis->>'opportunity_content_hash', 'legacy_hash') AS opportunity_content_hash,
            COALESCE(opp.match_analysis->>'engine_version', '1.7.0') AS engine_version,
            COALESCE(opp.created_at, NOW() AT TIME ZONE 'utc') AS created_at,
            COALESCE(opp.updated_at, NOW() AT TIME ZONE 'utc') AS updated_at
        FROM opportunities opp
        JOIN candidate_profiles cand ON cand.user_id = COALESCE(
            (opp.match_analysis->>'user_id')::integer,
            opp.user_id,
            1
        )
        WHERE opp.match_analysis IS NOT NULL
          AND opp.match_analysis::text != '{}'
          AND opp.match_score > 0
        ON CONFLICT (user_id, opportunity_id) DO NOTHING
        RETURNING 1;
    """
    with db_engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(42000102);"))  # distinct from migration lock
        if dry_run:
            select_only_sql = """
                SELECT count(*)
                FROM opportunities opp
                JOIN candidate_profiles cand ON cand.user_id = COALESCE(
                    (opp.match_analysis->>'user_id')::integer,
                    opp.user_id,
                    1
                )
                WHERE opp.match_analysis IS NOT NULL
                  AND opp.match_analysis::text != '{}'
                  AND opp.match_score > 0
            """
            res = conn.execute(text(select_only_sql))
            n = res.scalar() or 0
            logger.info("backfill dry-run would create %d candidate_opportunity_matches rows", n)
            return n
        res = conn.execute(text(sql))
        n = res.rowcount or 0
        logger.info("backfill inserted candidate_opportunity_matches (rowcount=%d)", n)
        return n
