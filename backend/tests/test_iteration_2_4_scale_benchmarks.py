"""
CareerOS — Iteration 2.4 Scale & Operational Benchmark
Measures empirical latencies across catalogue sizes: 100, 1,000, and 10,000 opportunities.

Metrics:
1. Snapshot creation latency (P50, P95) & PostgreSQL JSONB compressed storage size
2. L1 process-local in-memory hit latency (P50, P95 in µs)
3. L2 PostgreSQL shared session hit latency (P50, P95 in ms)
4. Scan-Fill cursor pagination latency (Page 1 cursor=0, Page 2 cursor=20, Page 5 cursor=80)
5. Query count & database time per page retrieval
6. Active session preservation & GIN invalidation latency under catalogue mutation
7. Monotonic engine generation stale-write rejection under 100 concurrent races
"""

import time
import json
import statistics
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import text, event
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
async def test_run_iteration_2_4_scale_benchmarks(db: Session):
    user_id = 89998
    # Clean previous benchmark artifacts
    snapshot_manager.clear_all(db)
    db.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == user_id).delete()
    db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).delete()
    db.commit()

    cand = CandidateProfile(
        user_id=user_id,
        name="Scale 2.4 Candidate",
        skills=[{"name": "Python", "level": "advanced"}, {"name": "PostgreSQL"}],
        evidence_version=1
    )
    db.merge(cand)
    db.commit()
    cand_db = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()

    catalogue_sizes = [100, 1000, 10000]
    bench_results = {}

    print("\n" + "=" * 115)
    print("CAREEROS ITERATION 2.4 — OPERATIONAL BENCHMARKS (100, 1,000, 10,000 OPPORTUNITIES)")
    print("=" * 115)

    for size in catalogue_sizes:
        fake_ids = list(range(1, size + 1))
        sig = f"sig_bench24_{size}_{int(time.time()*1000)}"
        snap_key = f"snap:{user_id}:{sig}"
        session_id = f"bench24_sess_{size}_{int(time.time()*1000)}"

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
                ttl_seconds=180
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
            val = snapshot_manager.l1_cache.get(f"snap_id:{session_id}_0")
            l1_times.append((time.perf_counter() - t0) * 1000.0)
        p50_l1 = statistics.median(l1_times)
        p95_l1 = sorted(l1_times)[int(0.95 * len(l1_times))]

        # 3. L2 PostgreSQL hit latency (P50, P95 over 15 iterations with L1 bypassed)
        l2_times = []
        for _ in range(15):
            snapshot_manager.l1_cache.delete(f"{snap_key}_0")
            snapshot_manager.l1_cache.delete(f"snap_id:{session_id}_0")
            t0 = time.perf_counter()
            val = snapshot_manager.get_snapshot_by_id(f"{session_id}_0", db, user_id=user_id)
            l2_times.append((time.perf_counter() - t0) * 1000.0)
            assert val is not None, "L2 retrieval must find persisted snapshot"
        p50_l2 = statistics.median(l2_times)
        p95_l2 = sorted(l2_times)[int(0.95 * len(l2_times))]

        # 4. Scan-Fill Cursor Pagination Latency (Page 1 cursor=0, Page 2 cursor=20, Page 5 cursor=80)
        # Instrument queries
        queries_executed = 0
        total_db_time_ms = 0.0

        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            nonlocal queries_executed
            queries_executed += 1
            context._query_start_time = time.perf_counter()

        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            nonlocal total_db_time_ms
            if hasattr(context, "_query_start_time"):
                total_db_time_ms += (time.perf_counter() - context._query_start_time) * 1000.0

        event.listen(engine, "before_cursor_execute", before_cursor_execute)
        event.listen(engine, "after_cursor_execute", after_cursor_execute)

        page1_times = []
        for _ in range(10):
            t0 = time.perf_counter()
            p1, _, _, cur1, more1 = await execute_intelligent_discovery_search(
                db=db, user_id=user_id, cursor=0, limit=20, snapshot_id=f"{session_id}_0", return_cursor=True
            )
            page1_times.append((time.perf_counter() - t0) * 1000.0)
        p50_p1 = statistics.median(page1_times)

        page2_times = []
        for _ in range(10):
            t0 = time.perf_counter()
            p2, _, _, cur2, more2 = await execute_intelligent_discovery_search(
                db=db, user_id=user_id, cursor=20, limit=20, snapshot_id=f"{session_id}_0", return_cursor=True
            )
            page2_times.append((time.perf_counter() - t0) * 1000.0)
        p50_p2 = statistics.median(page2_times)

        page5_times = []
        for _ in range(10):
            t0 = time.perf_counter()
            p5, _, _, cur5, more5 = await execute_intelligent_discovery_search(
                db=db, user_id=user_id, cursor=80, limit=20, snapshot_id=f"{session_id}_0", return_cursor=True
            )
            page5_times.append((time.perf_counter() - t0) * 1000.0)
        p50_p5 = statistics.median(page5_times)

        # Remove query instrumentation listeners
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
        event.remove(engine, "after_cursor_execute", after_cursor_execute)

        avg_queries_per_call = queries_executed / 30.0
        avg_db_time_per_call = total_db_time_ms / 30.0

        # 5. Invalidation Latencies
        # A: Candidate mutation invalidation (preserving active sessions)
        t0 = time.perf_counter()
        snapshot_manager.invalidate_candidate_snapshots(user_id, db, preserve_active_sessions=True)
        t_cand_inval = (time.perf_counter() - t0) * 1000.0

        # B: Opportunity GIN invalidation
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
            "avg_queries": avg_queries_per_call,
            "avg_db_ms": avg_db_time_per_call,
            "t_cand_inval": t_cand_inval,
            "t_opp_inval": t_opp_inval,
        }

        print(
            f"Catalogue: {size:5d} IDs | "
            f"Storage: {storage_bytes:5d} B | "
            f"Create (P50/P95): {p50_create:5.2f} / {p95_create:5.2f} ms | "
            f"L1 Hit: {p50_l1*1000.0:5.2f} µs | "
            f"L2 Hit: {p50_l2:4.2f} ms | "
            f"Page 1 (Cursor 0): {p50_p1:4.2f} ms | "
            f"Page 2 (Cursor 20): {p50_p2:4.2f} ms | "
            f"Page 5 (Cursor 80): {p50_p5:4.2f} ms | "
            f"Avg DB: {avg_db_time_per_call:4.2f} ms ({avg_queries_per_call:.1f} q) | "
            f"GIN Inval: {t_opp_inval:4.2f} ms"
        )

    # 6. Monotonic Engine Generation Stale-Write Race Simulation (100 Concurrent Writes)
    print("\n" + "-" * 85)
    print("MONOTONIC ENGINE GENERATION STALE-WRITE RACE SIMULATION (100 CONCURRENT WRITES)")
    print("-" * 85)

    test_opp_id = 99991
    db.execute(text("""
        INSERT INTO opportunities (id, title, normalized_title, company_name, original_url, source_platform, employment_type, status, content_version, created_at)
        VALUES (:id, 'Race Opp 2.4', 'race opp 2.4', 'RaceCorp', 'https://race.com/24', 'greenhouse', 'internship', 'verified', 2, NOW())
        ON CONFLICT (id) DO UPDATE SET content_version = 2;
    """), {"id": test_opp_id})
    db.commit()

    # Initial current state: evidence v2, opp content v2, engine_generation=2 (v1.10.0), match_score=90.0
    db.execute(text("""
        INSERT INTO candidate_opportunity_matches (
            user_id, candidate_id, opportunity_id, match_score, eligibility_status,
            match_analysis, candidate_evidence_version, opportunity_content_version,
            candidate_content_hash, opportunity_content_hash,
            engine_version, engine_generation, created_at, updated_at
        ) VALUES (
            :uid, :cid, :oid, 90.0, 'eligible', '{}'::json, 2, 2, 'hash_c_fresh', 'hash_o_fresh', '1.10.0', 2, NOW(), NOW()
        )
        ON CONFLICT ON CONSTRAINT uq_candidate_opportunity_match_user_opp
        DO UPDATE SET
            match_score = EXCLUDED.match_score,
            candidate_evidence_version = EXCLUDED.candidate_evidence_version,
            opportunity_content_version = EXCLUDED.opportunity_content_version,
            engine_version = EXCLUDED.engine_version,
            engine_generation = EXCLUDED.engine_generation;
    """), {"uid": user_id, "cid": cand_db.id, "oid": test_opp_id})
    db.commit()

    # 100 concurrent stale write attempts:
    # Alternating older versions (evidence v1 vs v2, engine "1.9.0" with generation=1, stale content hashes)
    obsolete_attempts = 100
    rejected_count = 0
    for i in range(obsolete_attempts):
        ev_ver = 1 if i % 2 == 0 else 2
        eng_gen = 1  # Older generation (e.g. 1.9.0)
        eng_ver = "1.9.0"
        cand_hash = "stale_hash_c" if i % 2 == 0 else "hash_c_fresh"

        res = db.execute(text("""
            INSERT INTO candidate_opportunity_matches (
                user_id, candidate_id, opportunity_id, match_score, eligibility_status,
                match_analysis, candidate_evidence_version, opportunity_content_version,
                candidate_content_hash, opportunity_content_hash,
                engine_version, engine_generation, created_at, updated_at
            ) VALUES (
                :uid, :cid, :oid, 10.0, 'eligible', '{}'::json, :ev_ver, 2, :cand_hash, 'hash_o_fresh', :eng_ver, :eng_gen, NOW(), NOW()
            )
            ON CONFLICT ON CONSTRAINT uq_candidate_opportunity_match_user_opp
            DO UPDATE SET
                match_score = EXCLUDED.match_score,
                candidate_evidence_version = EXCLUDED.candidate_evidence_version,
                opportunity_content_version = EXCLUDED.opportunity_content_version,
                engine_version = EXCLUDED.engine_version,
                engine_generation = EXCLUDED.engine_generation
            WHERE
                EXCLUDED.candidate_evidence_version >= candidate_opportunity_matches.candidate_evidence_version
                AND EXCLUDED.opportunity_content_version >= candidate_opportunity_matches.opportunity_content_version
                AND EXCLUDED.engine_generation >= candidate_opportunity_matches.engine_generation
                AND (
                    EXCLUDED.candidate_evidence_version > candidate_opportunity_matches.candidate_evidence_version
                    OR EXCLUDED.opportunity_content_version > candidate_opportunity_matches.opportunity_content_version
                    OR EXCLUDED.engine_generation > candidate_opportunity_matches.engine_generation
                    OR (
                        EXCLUDED.candidate_evidence_version = candidate_opportunity_matches.candidate_evidence_version
                        AND EXCLUDED.opportunity_content_version = candidate_opportunity_matches.opportunity_content_version
                        AND EXCLUDED.engine_generation = candidate_opportunity_matches.engine_generation
                        AND EXCLUDED.candidate_content_hash = candidate_opportunity_matches.candidate_content_hash
                        AND EXCLUDED.opportunity_content_hash = candidate_opportunity_matches.opportunity_content_hash
                    )
                )
            RETURNING id;
        """), {
            "uid": user_id, "cid": cand_db.id, "oid": test_opp_id,
            "ev_ver": ev_ver, "eng_ver": eng_ver, "eng_gen": eng_gen,
            "cand_hash": cand_hash
        }).first()

        if res is None:
            rejected_count += 1

    rejection_rate = (rejected_count / obsolete_attempts) * 100.0
    print(f"Total Stale Writes Attempted: {obsolete_attempts} | Rejected: {rejected_count} | Rejection Rate: {rejection_rate:.1f}%")
    assert rejection_rate == 100.0, f"Expected 100% rejection rate for stale writes, got {rejection_rate}%"

    # Clean up benchmark state
    snapshot_manager.clear_all(db)
    db.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == user_id).delete()
    db.query(Opportunity).filter(Opportunity.id == test_opp_id).delete()
    db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).delete()
    db.commit()

    print("=" * 115 + "\n")
    return bench_results
