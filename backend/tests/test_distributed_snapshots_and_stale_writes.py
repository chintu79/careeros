import os
import time
import json
import asyncio
import statistics
import multiprocessing
import concurrent.futures
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import event, text

from backend.app.database import SessionLocal, engine
from backend.app.models.opportunity import Opportunity
from backend.app.models.candidate import CandidateProfile
from backend.app.models.candidate_opportunity_match import CandidateOpportunityMatch, utc_now
from backend.app.models.discovery_ranking_snapshot import DiscoveryRankingSnapshot
from backend.app.services.matching.service import matching_service, MATCHING_ENGINE_VERSION
from backend.app.services.discovery_snapshot_manager import snapshot_manager
from backend.app.services.discovery_search_service import (
    execute_intelligent_discovery_search,
    compute_search_signature,
    RANKING_CONFIG_VERSION
)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class QueryCounter:
    def __init__(self, target_engine):
        self.engine = target_engine
        self.count = 0
        self.queries = []

    def __enter__(self):
        self.count = 0
        self.queries = []
        event.listen(self.engine, "before_cursor_execute", self._before_exec)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        event.remove(self.engine, "before_cursor_execute", self._before_exec)

    def _before_exec(self, conn, cursor, statement, parameters, context, executemany):
        self.count += 1
        self.queries.append(statement)


def create_opp(
    title: str,
    company_name: str,
    description: str,
    required_skills: list,
    original_url: str,
    preferred_skills: list = None,
    source_platform: str = "greenhouse"
) -> Opportunity:
    return Opportunity(
        title=title,
        normalized_title=title,
        company_name=company_name,
        description=description,
        required_skills=required_skills,
        preferred_skills=preferred_skills or [],
        location="Remote",
        normalized_location="Remote",
        workplace_type="remote",
        employment_type="internship",
        source_platform=source_platform,
        original_url=original_url,
        status="verified",
        eligibility_status="eligible",
        content_version=1
    )


# ==============================================================================
# PHASE 2: MULTI-WORKER PROCESS ISOLATION WORKER FUNCTIONS
# ==============================================================================

def _worker_search_process(company: str, skip: int, limit: int, user_id: int):
    """
    Simulates an independent application worker process (different PID, empty L1 memory cache).
    Connects to PostgreSQL, retrieves page, and returns result IDs, total count, and PID.
    """
    db = SessionLocal()
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results, total = loop.run_until_complete(
            execute_intelligent_discovery_search(
                db=db,
                company=company,
                tab="recommended",
                sort_by="match_score",
                sort_order="desc",
                skip=skip,
                limit=limit,
                user_id=user_id
            )
        )
        loop.close()
        item_ids = [r["id"] for r in results]
        return {
            "status": "success",
            "pid": os.getpid(),
            "ids": item_ids,
            "total": total,
            "count": len(item_ids)
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "pid": os.getpid()}
    finally:
        db.close()


# ==============================================================================
# PHASE 2: MULTI-WORKER PAGINATION CONSISTENCY
# ==============================================================================

def test_multi_worker_pagination_consistency_isolated_processes(db_session: Session):
    """
    Phase 2:
    Reproduce multi-worker scenario using isolated OS processes:
    1. Worker A receives page 1 and creates ranking snapshot in PostgreSQL L2.
    2. Worker B (separate process, empty L1) receives page 2 and retrieves from PostgreSQL L2.
    3. Worker C (separate process, empty L1) receives page 3 and retrieves from PostgreSQL L2.
    Verifies:
    - All workers return contiguous pages from the exact same ranking snapshot.
    - Zero duplicate IDs across pages.
    - Zero skipped opportunities.
    """
    test_uid = 97001
    snapshot_manager.clear_all(db_session)

    # Pre-clean
    db_session.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == test_uid).delete(synchronize_session=False)
    db_session.query(CandidateProfile).filter(CandidateProfile.user_id == test_uid).delete(synchronize_session=False)
    db_session.commit()

    cand = CandidateProfile(
        user_id=test_uid, name="Multi Worker Candidate",
        skills=[{"name": "Python", "level": "advanced", "category": "language"}],
        evidence_version=1
    )
    db_session.add(cand)
    db_session.commit()
    db_session.refresh(cand)

    ts = int(time.time() * 1000)
    company = f"DistCorp_{ts}"
    created_opps = []

    try:
        # Seed 75 diverse opportunities
        for i in range(75):
            skill = "Python" if i % 2 == 0 else "Java"
            desc = f"{skill} engineering systems."
            opp = create_opp(
                title=f"{skill} Role {ts}_{i:03d}",
                company_name=company,
                description=desc,
                required_skills=[skill],
                original_url=f"https://dist.test/{ts}_{i:03d}"
            )
            created_opps.append(opp)
        db_session.add_all(created_opps)
        db_session.commit()

        # Spawn isolated processes using ProcessPoolExecutor
        # Ensures completely distinct process IDs and memory heaps
        ctx = multiprocessing.get_context("spawn")
        with concurrent.futures.ProcessPoolExecutor(max_workers=3, mp_context=ctx) as executor:
            # Step 1: Worker A executes Page 1 (skip=0, limit=25)
            fut_a = executor.submit(_worker_search_process, company, 0, 25, test_uid)
            res_a = fut_a.result()

            assert res_a["status"] == "success"
            assert res_a["count"] == 25
            pid_a = res_a["pid"]

            # Verify snapshot was stored in PostgreSQL L2
            l2_snap = db_session.query(DiscoveryRankingSnapshot).filter(
                DiscoveryRankingSnapshot.user_id == test_uid
            ).first()
            assert l2_snap is not None, "Worker A must have persisted ranking snapshot to PostgreSQL L2!"
            assert len(l2_snap.snapshot_ids) == 75

            # Step 2: Worker B executes Page 2 (skip=25, limit=25) in an independent process
            fut_b = executor.submit(_worker_search_process, company, 25, 25, test_uid)
            res_b = fut_b.result()

            assert res_b["status"] == "success"
            assert res_b["count"] == 25
            pid_b = res_b["pid"]

            # Step 3: Worker C executes Page 3 (skip=50, limit=25) in another process
            fut_c = executor.submit(_worker_search_process, company, 50, 25, test_uid)
            res_c = fut_c.result()

            assert res_c["status"] == "success"
            assert res_c["count"] == 25
            pid_c = res_c["pid"]

        ids_a = res_a["ids"]
        ids_b = res_b["ids"]
        ids_c = res_c["ids"]

        combined = ids_a + ids_b + ids_c
        unique_combined = set(combined)

        # Cross-worker verification
        assert len(combined) == 75, f"Expected 75 total IDs across 3 pages, got {len(combined)}"
        assert len(unique_combined) == 75, (
            f"Cross-worker duplicate detected! Unique={len(unique_combined)}. "
            f"Overlap A-B={set(ids_a).intersection(set(ids_b))}, "
            f"Overlap B-C={set(ids_b).intersection(set(ids_c))}"
        )
        assert combined == l2_snap.snapshot_ids, "Slices from Workers A, B, C must strictly match the shared PostgreSQL snapshot!"

    finally:
        snapshot_manager.clear_all(db_session)
        db_session.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == test_uid).delete(synchronize_session=False)
        for o in created_opps:
            db_session.delete(o)
        db_session.delete(cand)
        db_session.commit()


# ==============================================================================
# PHASE 3: COMPLETE SEARCH SIGNATURE VALIDATION
# ==============================================================================

def test_complete_search_signature_canonical_sensitivity():
    """
    Phase 3:
    Validates that compute_search_signature accounts for every search, candidate evidence,
    and engine parameter. Tests changing exactly one parameter at a time and verifies
    the signature hash changes deterministically.
    """
    base_params = {
        "user_id": 101,
        "candidate_evidence_version": "cand_hash_v1",
        "tab": "recommended",
        "search_mode": "keyword",
        "query_str": "software intern",
        "category": "software_engineering",
        "company": "Google",
        "location": "Remote",
        "workplace_type": "remote",
        "internship_type": "summer",
        "work_mode": "full-time",
        "employment_type": "internship",
        "min_stipend": 20000.0,
        "compensation_type": "stipend",
        "skills": "Python, React",
        "duration_months": 3,
        "posted_days": 14,
        "source_platform": "greenhouse",
        "status": "verified",
        "eligibility_status": "eligible",
        "min_score": 50.0,
        "sort_by": "match_score",
        "sort_order": "desc",
        "page_size": 25,
        "matching_engine_version": "2.0.0",
        "ranking_config_version": RANKING_CONFIG_VERSION
    }

    base_sig = compute_search_signature(**base_params)
    assert len(base_sig) == 64, "Signature must be a 64-character SHA-256 hex string"

    # Verify idempotence
    assert compute_search_signature(**base_params) == base_sig

    # Test changing each parameter individually
    perturbations = {
        "user_id": 102,
        "candidate_evidence_version": "cand_hash_v2",
        "tab": "latest",
        "search_mode": "semantic",
        "query_str": "data engineer",
        "category": "data_science",
        "company": "Microsoft",
        "location": "Bangalore",
        "workplace_type": "hybrid",
        "internship_type": "winter",
        "work_mode": "part-time",
        "employment_type": "full-time",
        "min_stipend": 25000.0,
        "compensation_type": "unpaid",
        "skills": "Python, PyTorch",
        "duration_months": 6,
        "posted_days": 7,
        "source_platform": "lever",
        "status": "active",
        "eligibility_status": "flagged",
        "min_score": 70.0,
        "sort_by": "posted_at",
        "sort_order": "asc",
        "page_size": 50,
        "matching_engine_version": "2.1.0",
        "ranking_config_version": "2.3.0"
    }

    for param_name, new_val in perturbations.items():
        perturbed = dict(base_params)
        perturbed[param_name] = new_val
        new_sig = compute_search_signature(**perturbed)
        assert new_sig != base_sig, (
            f"Search signature failed to change when modifying parameter '{param_name}' from {base_params[param_name]} to {new_val}!"
        )


# ==============================================================================
# PHASE 4: CANDIDATE PROFILE SNAPSHOT INVALIDATION
# ==============================================================================

def test_candidate_profile_snapshot_invalidation_isolation(db_session: Session):
    """
    Phase 4:
    A candidate updating their profile must invalidate their previous ranking snapshot,
    while other candidates' snapshots remain active.
    """
    uid_a = 97002
    uid_b = 97003
    snapshot_manager.clear_all(db_session)

    # Setup Candidate A and Candidate B
    cand_a = CandidateProfile(user_id=uid_a, name="Candidate Alpha", skills=[{"name": "Python"}], evidence_version=1)
    cand_b = CandidateProfile(user_id=uid_b, name="Candidate Beta", skills=[{"name": "Java"}], evidence_version=1)
    db_session.add_all([cand_a, cand_b])
    db_session.commit()

    # Store snapshots for both candidates
    snapshot_manager.set_snapshot("snap:97002:sigA", uid_a, "sigA", "hashA", [1, 2, 3], 3, db_session)
    snapshot_manager.set_snapshot("snap:97003:sigB", uid_b, "sigB", "hashB", [4, 5, 6], 3, db_session)

    assert snapshot_manager.get_snapshot("snap:97002:sigA", db_session) is not None
    assert snapshot_manager.get_snapshot("snap:97003:sigB", db_session) is not None

    try:
        # Candidate A updates skills via profile update
        cand_a.skills = [{"name": "Python"}, {"name": "FastAPI"}]
        cand_a.evidence_version = (cand_a.evidence_version or 1) + 1
        cand_a.updated_at = utc_now()
        db_session.commit()
        # Trigger invalidation hook
        deleted = snapshot_manager.invalidate_candidate_snapshots(user_id=uid_a, db=db_session)
        assert deleted >= 1

        # Verify Candidate A's snapshot is gone
        assert snapshot_manager.get_snapshot("snap:97002:sigA", db_session) is None, "Candidate A's snapshot should be invalidated!"

        # Verify Candidate B's snapshot is STILL ACTIVE and untouched
        snap_b = snapshot_manager.get_snapshot("snap:97003:sigB", db_session)
        assert snap_b is not None, "Candidate B's snapshot must remain active!"
        assert snap_b[0] == [4, 5, 6]

    finally:
        snapshot_manager.clear_all(db_session)
        db_session.delete(cand_a)
        db_session.delete(cand_b)
        db_session.commit()


# ==============================================================================
# PHASE 5: OPPORTUNITY CHANGE & DISMISSAL INVALIDATION
# ==============================================================================

@pytest.mark.asyncio
async def test_opportunity_dismissal_and_change_invalidation(db_session: Session):
    """
    Phase 5:
    Dismissing or modifying an opportunity invalidates snapshots containing that opportunity,
    ensuring dismissed opportunities do not appear on subsequent page requests.
    """
    test_uid = 97004
    snapshot_manager.clear_all(db_session)

    cand = CandidateProfile(user_id=test_uid, name="Dismissal Candidate", skills=[{"name": "Python"}], evidence_version=1)
    db_session.add(cand)
    db_session.commit()
    db_session.refresh(cand)

    ts = int(time.time() * 1000)
    company = f"DismissCorp_{ts}"
    opps = [
        create_opp(f"Opp {ts}_{i}", company, "Python backend.", ["Python"], f"https://d.test/{ts}_{i}")
        for i in range(10)
    ]
    db_session.add_all(opps)
    db_session.commit()

    opp_to_dismiss = opps[8]

    try:
        # Page 1 search creates snapshot
        results, _ = await execute_intelligent_discovery_search(
            db=db_session, company=company, tab="recommended", limit=5, user_id=test_uid
        )
        res_ids = [r["id"] for r in results]
        assert opp_to_dismiss.id in res_ids

        # Candidate dismisses opportunity 2
        opp_to_dismiss.is_dismissed = True
        opp_to_dismiss.content_version = (opp_to_dismiss.content_version or 1) + 1
        db_session.commit()
        snapshot_manager.invalidate_opportunity_snapshots(opp_to_dismiss.id, db_session)

        # Subsequent search must NOT contain dismissed opportunity
        res_after, _ = await execute_intelligent_discovery_search(
            db=db_session, company=company, tab="recommended", limit=5, user_id=test_uid
        )
        ids_after = [r["id"] for r in res_after]
        assert opp_to_dismiss.id not in ids_after, "Dismissed opportunity must not appear in discovery search!"

    finally:
        snapshot_manager.clear_all(db_session)
        db_session.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == test_uid).delete(synchronize_session=False)
        for o in opps:
            db_session.delete(o)
        db_session.delete(cand)
        db_session.commit()


# ==============================================================================
# PHASE 6: STALE-WRITE PROTECTION IN ATOMIC UPSERTS
# ==============================================================================

@pytest.mark.asyncio
async def test_stale_write_rejection_conditional_upsert(db_session: Session):
    """
    Phase 6:
    Reproduce stale-write race:
    1. Request A starts with candidate evidence version 1.
    2. Candidate profile updates to evidence version 2.
    3. Request B calculates and persists version 2 match (score: 95.0%).
    4. Slower Request A finishes later with version 1 (score: 70.0%).
    Verifies that the conditional PostgreSQL upsert REJECTS the stale write:
    Row in DB preserves version 2 with score 95.0%.
    """
    test_uid = 97005
    cand = CandidateProfile(
        user_id=test_uid, name="Stale Race Candidate",
        skills=[{"name": "Python"}], evidence_version=1
    )
    db_session.add(cand)
    db_session.commit()
    db_session.refresh(cand)

    ts = int(time.time() * 1000)
    opp = create_opp(f"Stale Race Opp {ts}", "StaleCorp", "Python systems.", ["Python"], f"https://stale.test/{ts}")
    db_session.add(opp)
    db_session.commit()
    db_session.refresh(opp)

    try:
        # Step 1: Request B computes and persists Version 2
        cand.evidence_version = 2
        cand.skills = [{"name": "Python"}, {"name": "FastAPI"}]
        db_session.commit()
        res_b = await matching_service.evaluate_match(cand, opp, db_session, use_ai=False)
        assert res_b.profile_match_score > 75.0

        db_rec = db_session.query(CandidateOpportunityMatch).filter(
            CandidateOpportunityMatch.user_id == test_uid,
            CandidateOpportunityMatch.opportunity_id == opp.id
        ).first()
        assert db_rec.candidate_evidence_version == 2
        score_v2 = db_rec.match_score

        # Step 2: Slower Request A attempts to write Version 1 (e.g. simulated older evaluation)
        # Directly execute conditional upsert with older evidence_version = 1 and an inferior score (10.0%)
        stmt = text("""
            INSERT INTO candidate_opportunity_matches (
                user_id, candidate_id, opportunity_id, match_score, eligibility_status,
                match_analysis, candidate_content_hash, opportunity_content_hash,
                candidate_evidence_version, opportunity_content_version,
                engine_version, created_at, updated_at
            ) VALUES (
                :uid, :cid, :oid, 10.0, 'eligible',
                '{"profile_match_score": 10.0}'::jsonb, 'stale_hash', 'opp_hash',
                1, 1,
                '2.0.0', NOW() AT TIME ZONE 'utc', NOW() AT TIME ZONE 'utc'
            )
            ON CONFLICT ON CONSTRAINT uq_candidate_opportunity_match_user_opp
            DO UPDATE SET
                match_score = EXCLUDED.match_score,
                candidate_evidence_version = EXCLUDED.candidate_evidence_version,
                updated_at = EXCLUDED.updated_at
            WHERE (
                EXCLUDED.candidate_evidence_version >= candidate_opportunity_matches.candidate_evidence_version
                AND
                EXCLUDED.opportunity_content_version >= candidate_opportunity_matches.opportunity_content_version
            )
            RETURNING candidate_opportunity_matches.id;
        """)

        res = db_session.execute(stmt, {"uid": test_uid, "cid": cand.id, "oid": opp.id}).scalars().first()
        db_session.commit()

        # RETURNING must be None because WHERE condition evaluated to FALSE (1 >= 2 is False)
        assert res is None, "Conditional upsert MUST return None when stale write is rejected!"

        # Verify the database preserved the newer Version 2 record
        db_rec_after = db_session.query(CandidateOpportunityMatch).filter(
            CandidateOpportunityMatch.user_id == test_uid,
            CandidateOpportunityMatch.opportunity_id == opp.id
        ).first()

        assert db_rec_after.candidate_evidence_version == 2, "Database record must retain Version 2!"
        assert db_rec_after.match_score == score_v2, "Database record must retain Version 2 score!"

    finally:
        db_session.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == test_uid).delete(synchronize_session=False)
        db_session.delete(opp)
        db_session.delete(cand)
        db_session.commit()


# ==============================================================================
# PHASE 7: FLAGGED ELIGIBILITY AND SCORE PERSISTENCE
# ==============================================================================

@pytest.mark.asyncio
async def test_flagged_eligibility_persistence_and_intelligence(db_session: Session):
    """
    Phase 7:
    Verifies that a candidate missing significant mandatory requirements produces
    eligibility_status = 'flagged', which is strictly persisted and surfaced without
    being silently overridden to 'eligible'.
    """
    test_uid = 97006
    cand = CandidateProfile(
        user_id=test_uid, name="Flagged Candidate",
        skills=[{"name": "HTML"}], evidence_version=1
    )
    db_session.add(cand)
    db_session.commit()
    db_session.refresh(cand)

    ts = int(time.time() * 1000)
    # Opp requiring 3 heavy technical skills that candidate lacks
    opp = create_opp(
        title=f"Flagged Technical Opp {ts}",
        company_name="FlagCorp",
        description="Must have requirements: C++, Rust, Linux Kernel, Assembly. Mandatory qualifications for kernel firmware and distributed systems.",
        required_skills=["C++", "Rust", "Linux Kernel", "Assembly"],
        original_url=f"https://flag.test/{ts}"
    )
    db_session.add(opp)
    db_session.commit()
    db_session.refresh(opp)

    try:
        # 1. Evaluate match
        match_result = await matching_service.evaluate_match(cand, opp, db_session, use_ai=False)

        # Deterministic engine flags candidate due to missing mandatory requirements
        assert match_result.eligibility_status == "flagged", (
            f"Expected eligibility_status='flagged', got '{match_result.eligibility_status}'"
        )
        assert len(match_result.disqualifying_reasons) > 0

        # 2. Verify persisted row in candidate_opportunity_matches
        db_rec = db_session.query(CandidateOpportunityMatch).filter(
            CandidateOpportunityMatch.user_id == test_uid,
            CandidateOpportunityMatch.opportunity_id == opp.id
        ).first()

        assert db_rec is not None
        assert db_rec.eligibility_status == "flagged", (
            f"Persisted eligibility_status must be 'flagged', got '{db_rec.eligibility_status}'"
        )

        # 3. Verify discovery intelligence payload
        results, _ = await execute_intelligent_discovery_search(
            db=db_session, company="FlagCorp", tab="recommended", limit=10, user_id=test_uid
        )
        flagged_item = next(r for r in results if r["id"] == opp.id)

        assert flagged_item["eligibility_status"] == "flagged"
        assert flagged_item["eligibility_assessment"]["status"] == "flagged"
        assert "Review Notice:" in flagged_item["eligibility_assessment"]["summary"]

    finally:
        db_session.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == test_uid).delete(synchronize_session=False)
        db_session.delete(opp)
        db_session.delete(cand)
        db_session.commit()


# ==============================================================================
# PHASE 10: PERFORMANCE AND OPERATIONAL AUDIT BENCHMARKS
# ==============================================================================

@pytest.mark.asyncio
async def test_distributed_snapshots_performance_benchmarks(db_session: Session):
    """
    Phase 10:
    Operational benchmark measuring:
    - Snapshot creation latency
    - L1 in-memory retrieval latency
    - L2 PostgreSQL retrieval latency
    - Snapshot invalidation latency
    - Search P50 and P95 latency across catalogue sizes (100, 500, 1,000, 10,000)
    """
    test_uid = 97007
    snapshot_manager.clear_all(db_session)

    cand = CandidateProfile(
        user_id=test_uid, name="Bench Candidate",
        skills=[{"name": "Python"}], evidence_version=1
    )
    db_session.add(cand)
    db_session.commit()
    db_session.refresh(cand)

    catalog_sizes = [100, 500, 1000, 10000]
    ts = int(time.time() * 1000)

    print("\n" + "=" * 95)
    print("PHASE 10: DISTRIBUTED RANKING SNAPSHOT OPERATIONAL BENCHMARKS")
    print("=" * 95)

    for size in catalog_sizes:
        fake_ids = list(range(1, size + 1))
        snap_key = f"snap:97007:bench_{size}_{ts}"

        # 1. Snapshot Creation & Persistence to PostgreSQL L2
        t0 = time.perf_counter()
        snapshot_manager.set_snapshot(
            snapshot_key=snap_key,
            user_id=test_uid,
            signature=f"sig_{size}",
            candidate_evidence_version="cand_v1",
            snapshot_ids=fake_ids,
            total_count=size,
            db=db_session,
            ttl_seconds=120
        )
        t_create = (time.perf_counter() - t0) * 1000.0

        # Measure storage size in DB
        storage_bytes = db_session.execute(text("""
            SELECT pg_column_size(snapshot_ids) FROM discovery_ranking_snapshots WHERE snapshot_key = :k
        """), {"k": snap_key}).scalar() or 0

        # 2. L1 in-memory cache retrieval latency
        l1_times = []
        for _ in range(50):
            t0 = time.perf_counter()
            val = snapshot_manager.l1_cache.get(snap_key)
            l1_times.append((time.perf_counter() - t0) * 1000.0)
        p50_l1 = statistics.median(l1_times)

        # 3. L2 PostgreSQL retrieval latency (simulate cold worker)
        l2_times = []
        for _ in range(10):
            snapshot_manager.l1_cache.delete(snap_key)  # Force L1 miss
            t0 = time.perf_counter()
            val = snapshot_manager.get_snapshot(snap_key, db_session)
            l2_times.append((time.perf_counter() - t0) * 1000.0)
        p50_l2 = statistics.median(l2_times)
        p95_l2 = sorted(l2_times)[-1]

        # 4. Invalidation Latency
        t0 = time.perf_counter()
        deleted = snapshot_manager.invalidate_candidate_snapshots(test_uid, db_session)
        t_inval = (time.perf_counter() - t0) * 1000.0

        print(
            f"Catalogue Size {size:5d} IDs | "
            f"Storage: {storage_bytes:5d} B | "
            f"L2 Persist: {t_create:5.2f}ms | "
            f"L1 Hit: {p50_l1*1000:5.2f}µs | "
            f"L2 Hit (P50/P95): {p50_l2:4.2f}ms / {p95_l2:4.2f}ms | "
            f"Inval: {t_inval:4.2f}ms"
        )

        # Assertions
        assert storage_bytes > 0
        assert p50_l2 < 5.0, f"L2 retrieval must be under 5ms, got {p50_l2:.2f}ms"

    # Clean up
    db_session.delete(cand)
    db_session.commit()
    snapshot_manager.clear_all(db_session)
