"""
CareerOS — Iteration 2.3 Scale & Operational Benchmark
Measures empirical latencies across catalogue sizes: 100, 500, 1,000, and 10,000 opportunities.

Metrics:
1. Snapshot creation latency (P50, P95)
2. L1 in-memory snapshot hit latency (P50, P95)
3. L2 PostgreSQL snapshot hit latency (P50, P95)
4. Full page retrieval latency (Page 1, Page 2, Page 5)
5. Invalidation latency under mutation (candidate & opportunity GIN index)
6. Stale-write rejection rate under simulated concurrent races
7. GIN index query performance (EXPLAIN ANALYZE BUFFERS)
"""

import time
import json
import statistics
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal, engine
from backend.app.models.opportunity import Opportunity
from backend.app.models.candidate import CandidateProfile
from backend.app.models.candidate_opportunity_match import CandidateOpportunityMatch, utc_now
from backend.app.models.discovery_ranking_snapshot import DiscoveryRankingSnapshot
from backend.app.services.discovery_snapshot_manager import snapshot_manager
from backend.app.services.discovery_search_service import execute_intelligent_discovery_search


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.mark.asyncio
async def test_run_iteration_2_3_scale_benchmarks(db: Session):
    user_id = 89999
    # Clean previous benchmark artifacts
    snapshot_manager.clear_all(db)
    db.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == user_id).delete()
    db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).delete()
    db.commit()

    cand = CandidateProfile(
        user_id=user_id,
        name="Scale Benchmark Candidate",
        skills=[{"name": "Python", "level": "advanced"}, {"name": "PostgreSQL"}],
        evidence_version=1
    )
    db.merge(cand)
    db.commit()
    cand_db = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()

    catalogue_sizes = [100, 500, 1000, 10000]
    bench_results = {}

    print("\n" + "=" * 110)
    print("CAREEROS ITERATION 2.3 — SCALE & OPERATIONAL BENCHMARK (100, 500, 1,000, 10,000)")
    print("=" * 110)

    for size in catalogue_sizes:
        fake_ids = list(range(1, size + 1))
        sig = f"sig_bench_{size}_{int(time.time()*1000)}"
        snap_key = f"snap:{user_id}:{sig}"
        session_id = f"bench_sess_{size}_{int(time.time()*1000)}"

        # 1. Snapshot creation latency (P50, P95 over 15 iterations)
        create_times = []
        for i in range(15):
            k = f"{snap_key}_{i}"
            sid = f"{session_id}_{i}"
            t0 = time.perf_counter()
            snapshot_manager.set_snapshot(
                snapshot_key=k,
                user_id=user_id,
                signature=sig,
                candidate_evidence_version="v1",
                snapshot_ids=fake_ids,
                total_count=size,
                db=db,
                snapshot_id=sid,
                ttl_seconds=120
            )
            create_times.append((time.perf_counter() - t0) * 1000.0)

        p50_create = statistics.median(create_times)
        p95_create = sorted(create_times)[int(0.95 * len(create_times))]

        # Storage size in PostgreSQL
        storage_bytes = db.execute(text("""
            SELECT pg_column_size(snapshot_ids) FROM discovery_ranking_snapshots WHERE snapshot_key = :k
        """), {"k": f"{snap_key}_0"}).scalar() or 0

        # 2. L1 hit latency (P50, P95 over 50 iterations)
        l1_times = []
        for _ in range(50):
            t0 = time.perf_counter()
            val = snapshot_manager.l1_cache.get(f"{snap_key}_0")
            l1_times.append((time.perf_counter() - t0) * 1000.0)
        p50_l1 = statistics.median(l1_times)
        p95_l1 = sorted(l1_times)[int(0.95 * len(l1_times))]

        # 3. L2 PostgreSQL hit latency (P50, P95 over 15 iterations with L1 bypassed)
        l2_times = []
        for _ in range(15):
            snapshot_manager.l1_cache.delete(f"{snap_key}_0")
            snapshot_manager.l1_cache.delete(f"snap_id:{session_id}_0")
            t0 = time.perf_counter()
            val = snapshot_manager.get_snapshot_by_id(f"{session_id}_0", db)
            l2_times.append((time.perf_counter() - t0) * 1000.0)
            assert val is not None, "L2 retrieval must find persisted snapshot"
        p50_l2 = statistics.median(l2_times)
        p95_l2 = sorted(l2_times)[int(0.95 * len(l2_times))]

        # 4. Full page retrieval latency (Page 1, Page 2, Page 5)
        page1_times = []
        for _ in range(10):
            t0 = time.perf_counter()
            p1, _, _ = await execute_intelligent_discovery_search(
                db=db, user_id=user_id, skip=0, limit=20, snapshot_id=f"{session_id}_0", return_snapshot_id=True
            )
            page1_times.append((time.perf_counter() - t0) * 1000.0)
        p50_p1 = statistics.median(page1_times)

        page2_times = []
        for _ in range(10):
            t0 = time.perf_counter()
            p2, _, _ = await execute_intelligent_discovery_search(
                db=db, user_id=user_id, skip=20, limit=20, snapshot_id=f"{session_id}_0", return_snapshot_id=True
            )
            page2_times.append((time.perf_counter() - t0) * 1000.0)
        p50_p2 = statistics.median(page2_times)

        page5_times = []
        for _ in range(10):
            t0 = time.perf_counter()
            p5, _, _ = await execute_intelligent_discovery_search(
                db=db, user_id=user_id, skip=80, limit=20, snapshot_id=f"{session_id}_0", return_snapshot_id=True
            )
            page5_times.append((time.perf_counter() - t0) * 1000.0)
        p50_p5 = statistics.median(page5_times)

        # 5. Invalidation latency under mutation
        # A: Candidate mutation invalidation
        t0 = time.perf_counter()
        snapshot_manager.invalidate_candidate_snapshots(user_id, db)
        t_cand_inval = (time.perf_counter() - t0) * 1000.0

        # Re-set one snapshot to test opportunity GIN invalidation
        snapshot_manager.set_snapshot(
            snapshot_key=f"{snap_key}_gin",
            user_id=user_id,
            signature=sig,
            candidate_evidence_version="v1",
            snapshot_ids=fake_ids,
            total_count=size,
            db=db,
            snapshot_id=f"{session_id}_gin",
            ttl_seconds=120
        )
        t0 = time.perf_counter()
        snapshot_manager.invalidate_opportunity_snapshots(fake_ids[0], db)
        t_opp_inval = (time.perf_counter() - t0) * 1000.0

        bench_results[size] = {
            "storage_bytes": storage_bytes,
            "p50_create": p50_create,
            "p95_create": p95_create,
            "p50_l1_us": p50_l1 * 1000.0,
            "p95_l1_us": p95_l1 * 1000.0,
            "p50_l2": p50_l2,
            "p95_l2": p95_l2,
            "p50_p1": p50_p1,
            "p50_p2": p50_p2,
            "p50_p5": p50_p5,
            "t_cand_inval": t_cand_inval,
            "t_opp_inval": t_opp_inval,
        }

        print(
            f"Catalogue: {size:5d} IDs | "
            f"Storage: {storage_bytes:5d} B | "
            f"Create (P50/P95): {p50_create:5.2f} / {p95_create:5.2f} ms | "
            f"L1 Hit: {p50_l1*1000.0:5.2f} µs | "
            f"L2 Hit: {p50_l2:4.2f} ms | "
            f"Page 1: {p50_p1:4.2f} ms | "
            f"Page 5: {p50_p5:4.2f} ms | "
            f"GIN Inval: {t_opp_inval:4.2f} ms"
        )

    # 6. Stale-write rejection rate under simulated race conditions
    print("\n" + "-" * 80)
    print("STALE-WRITE PROTECTION RACE SIMULATION (100 CONCURRENT WRITES)")
    print("-" * 80)
    
    test_opp_id = 99990
    db.execute(text("""
        INSERT INTO opportunities (id, title, normalized_title, company_name, original_url, source_platform, employment_type, status, content_version, created_at)
        VALUES (:id, 'Race Opp', 'race opp', 'RaceCorp', 'https://race.com/1', 'greenhouse', 'internship', 'verified', 2, NOW())
        ON CONFLICT (id) DO UPDATE SET content_version = 2;
    """), {"id": test_opp_id})
    db.commit()

    db.execute(text("""
        INSERT INTO candidate_opportunity_matches (
            user_id, candidate_id, opportunity_id, match_score, eligibility_status,
            match_analysis, candidate_evidence_version, opportunity_content_version,
            candidate_content_hash, opportunity_content_hash,
            engine_version, created_at, updated_at
        ) VALUES (
            :uid, :cid, :oid, 85.0, 'eligible', '{}'::json, 2, 2, 'hash_c', 'hash_o', '2.0.0', NOW(), NOW()
        )
        ON CONFLICT ON CONSTRAINT uq_candidate_opportunity_match_user_opp
        DO UPDATE SET
            match_score = EXCLUDED.match_score,
            candidate_evidence_version = EXCLUDED.candidate_evidence_version,
            opportunity_content_version = EXCLUDED.opportunity_content_version,
            engine_version = EXCLUDED.engine_version,
            updated_at = EXCLUDED.updated_at
        WHERE
            EXCLUDED.candidate_evidence_version >= candidate_opportunity_matches.candidate_evidence_version
            AND EXCLUDED.opportunity_content_version >= candidate_opportunity_matches.opportunity_content_version
            AND EXCLUDED.engine_version >= candidate_opportunity_matches.engine_version
            AND EXCLUDED.updated_at >= candidate_opportunity_matches.updated_at;
    """), {"uid": user_id, "cid": cand_db.id, "oid": test_opp_id})
    db.commit()

    obsolete_attempts = 100
    rejected_count = 0
    for i in range(obsolete_attempts):
        eng = "1.0.0" if i % 2 == 0 else "2.0.0"
        ev_ver = 2 if i % 2 == 0 else 1
        res = db.execute(text("""
            INSERT INTO candidate_opportunity_matches (
                user_id, candidate_id, opportunity_id, match_score, eligibility_status,
                match_analysis, candidate_evidence_version, opportunity_content_version,
                candidate_content_hash, opportunity_content_hash,
                engine_version, created_at, updated_at
            ) VALUES (
                :uid, :cid, :oid, 10.0, 'eligible', '{}'::json, :ev_ver, 2, 'hash_c', 'hash_o', :eng, NOW(), NOW()
            )
            ON CONFLICT ON CONSTRAINT uq_candidate_opportunity_match_user_opp
            DO UPDATE SET
                match_score = EXCLUDED.match_score,
                candidate_evidence_version = EXCLUDED.candidate_evidence_version,
                opportunity_content_version = EXCLUDED.opportunity_content_version,
                engine_version = EXCLUDED.engine_version,
                updated_at = EXCLUDED.updated_at
            WHERE
                EXCLUDED.candidate_evidence_version >= candidate_opportunity_matches.candidate_evidence_version
                AND EXCLUDED.opportunity_content_version >= candidate_opportunity_matches.opportunity_content_version
                AND EXCLUDED.engine_version >= candidate_opportunity_matches.engine_version
                AND EXCLUDED.updated_at >= candidate_opportunity_matches.updated_at
            RETURNING id;
        """), {"uid": user_id, "cid": cand_db.id, "oid": test_opp_id, "ev_ver": ev_ver, "eng": eng}).first()
        if res is None:
            rejected_count += 1

    rejection_rate = (rejected_count / obsolete_attempts) * 100.0
    print(f"Total Stale Writes Attempted: {obsolete_attempts} | Rejected: {rejected_count} | Rejection Rate: {rejection_rate:.1f}%")
    assert rejection_rate == 100.0, f"Expected 100% rejection rate for stale writes, got {rejection_rate}%"

    # 7. GIN index query plan verification (EXPLAIN ANALYZE BUFFERS)
    print("\n" + "-" * 80)
    print("GIN INDEX QUERY PLAN (EXPLAIN (ANALYZE, BUFFERS))")
    print("-" * 80)
    target_id = 42
    snapshot_manager.set_snapshot(
        snapshot_key=f"snap:{user_id}:gin_plan",
        user_id=user_id,
        signature="sig_gin_plan",
        candidate_evidence_version="v1",
        snapshot_ids=[target_id, 101, 102, 103],
        total_count=4,
        db=db,
        ttl_seconds=120
    )
    plan_rows = db.execute(text(f"""
        EXPLAIN (ANALYZE, BUFFERS)
        SELECT snapshot_key, snapshot_id FROM discovery_ranking_snapshots
        WHERE snapshot_ids @> '[{target_id}]'::jsonb;
    """)).fetchall()

    plan_str = "\n".join(r[0] for r in plan_rows)
    print(plan_str)

    # Clean up benchmark state
    snapshot_manager.clear_all(db)
    db.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == user_id).delete()
    db.query(Opportunity).filter(Opportunity.id == test_opp_id).delete()
    db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).delete()
    db.commit()

    print("=" * 110 + "\n")
    return bench_results
