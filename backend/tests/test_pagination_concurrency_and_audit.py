import asyncio
import time
import statistics
import concurrent.futures
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import event, text

from backend.app.database import SessionLocal, engine
from backend.app.models.opportunity import Opportunity
from backend.app.models.candidate import CandidateProfile
from backend.app.models.candidate_opportunity_match import CandidateOpportunityMatch, utc_now
from backend.app.services.matching.service import matching_service, MATCHING_ENGINE_VERSION
from backend.app.services.discovery_search_service import (
    execute_intelligent_discovery_search,
    compute_search_signature
)
from backend.app.services.intelligence_cache import ranking_snapshot_cache


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
        eligibility_status="eligible"
    )


# ==============================================================================
# PHASE 2: ADVERSARIAL PAGINATION TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_adversarial_pagination_integrity_100_opps(db_session: Session):
    """
    Phase 2:
    Adversarial pagination test across a deterministic dataset of 100+ opportunities.
    Validates:
    1. Zero duplicate opportunity IDs across pages (Page 1, 2, 3).
    2. Zero skipped eligible opportunities within the ranking snapshot.
    3. Correct tiered ordering (Tier 2 >= 50, Tier 1 unevaluated, Tier 0 < 50).
    4. Repeated paginated requests return identical, deterministic results.
    5. Correct behavior across multiple page sizes and sort directions.
    """
    test_uid = 93001
    ranking_snapshot_cache.clear()

    # Pre-clean
    db_session.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == test_uid).delete(synchronize_session=False)
    db_session.query(CandidateProfile).filter(CandidateProfile.user_id == test_uid).delete(synchronize_session=False)
    db_session.commit()

    cand = CandidateProfile(
        user_id=test_uid, name="Adversarial Pagination Candidate", email="adv_page@careeros.internal",
        skills=[
            {"name": "Python", "level": "advanced", "category": "language"},
            {"name": "FastAPI", "level": "advanced", "category": "framework"}
        ],
        preferred_locations=["remote"]
    )
    db_session.add(cand)
    db_session.commit()
    db_session.refresh(cand)

    ts = int(time.time() * 1000)
    created_opps = []

    try:
        # Seed 100 diverse opportunities:
        # - High fit (Python, FastAPI): should score ~85% (Tier 2)
        # - Low fit (Java, Kotlin): should score ~18% (Tier 0)
        # - Unevaluated opportunities
        # - Pre-evaluated opportunities
        for i in range(100):
            if i % 4 == 0:
                skill = "Python"
                desc = "Python backend FastAPI service engineering."
                req = ["Python", "FastAPI"]
            elif i % 4 == 1:
                skill = "Java"
                desc = "Android Java mobile systems development."
                req = ["Java", "Kotlin"]
            elif i % 4 == 2:
                skill = "React"
                desc = "Frontend UI components and TypeScript."
                req = ["React", "TypeScript"]
            else:
                skill = "C++"
                desc = "Embedded systems firmware development."
                req = ["C++"]

            opp = create_opp(
                title=f"{skill} Engineering Role {ts}_{i:03d}",
                company_name=f"AdvCorp_{ts}",
                description=desc,
                required_skills=req,
                original_url=f"https://adv.test/{ts}_{i:03d}"
            )
            created_opps.append(opp)

        db_session.add_all(created_opps)
        db_session.commit()

        # Seed pre-existing evaluations for specific items:
        # 1. Pre-evaluated high score (Tier 2)
        pre_high_opp = created_opps[10]
        db_session.add(CandidateOpportunityMatch(
            user_id=test_uid, candidate_id=cand.id, opportunity_id=pre_high_opp.id,
            match_score=92.5, eligibility_status="eligible",
            match_analysis={"profile_match_score": 92.5, "engine_version": MATCHING_ENGINE_VERSION},
            candidate_content_hash="cand_hash", opportunity_content_hash="opp_hash",
            engine_version=MATCHING_ENGINE_VERSION
        ))

        # 2. Pre-evaluated low score (Tier 0)
        pre_low_opp = created_opps[11]
        db_session.add(CandidateOpportunityMatch(
            user_id=test_uid, candidate_id=cand.id, opportunity_id=pre_low_opp.id,
            match_score=15.0, eligibility_status="eligible",
            match_analysis={"profile_match_score": 15.0, "engine_version": MATCHING_ENGINE_VERSION},
            candidate_content_hash="cand_hash", opportunity_content_hash="opp_hash",
            engine_version=MATCHING_ENGINE_VERSION
        ))
        db_session.commit()

        # ----------------------------------------------------------------------
        # TEST 1: Retrieve Page 1, Page 2, Page 3 (limit=25)
        # ----------------------------------------------------------------------
        p1, tot1 = await execute_intelligent_discovery_search(
            db=db_session, company=f"AdvCorp_{ts}", tab="recommended", sort_by="match_score", sort_order="desc",
            skip=0, limit=25, user_id=test_uid
        )
        p2, tot2 = await execute_intelligent_discovery_search(
            db=db_session, company=f"AdvCorp_{ts}", tab="recommended", sort_by="match_score", sort_order="desc",
            skip=25, limit=25, user_id=test_uid
        )
        p3, tot3 = await execute_intelligent_discovery_search(
            db=db_session, company=f"AdvCorp_{ts}", tab="recommended", sort_by="match_score", sort_order="desc",
            skip=50, limit=25, user_id=test_uid
        )
        p4, tot4 = await execute_intelligent_discovery_search(
            db=db_session, company=f"AdvCorp_{ts}", tab="recommended", sort_by="match_score", sort_order="desc",
            skip=75, limit=25, user_id=test_uid
        )

        assert tot1 == 100
        assert tot2 == 100
        assert tot3 == 100
        assert tot4 == 100
        assert len(p1) == 25
        assert len(p2) == 25
        assert len(p3) == 25
        assert len(p4) == 25

        ids_p1 = [r["id"] for r in p1]
        ids_p2 = [r["id"] for r in p2]
        ids_p3 = [r["id"] for r in p3]
        ids_p4 = [r["id"] for r in p4]

        all_combined = ids_p1 + ids_p2 + ids_p3 + ids_p4
        unique_combined = set(all_combined)

        # 1. Verify ZERO duplicates across all 4 pages
        assert len(all_combined) == 100, f"Expected 100 total items across 4 pages, got {len(all_combined)}"
        assert len(unique_combined) == 100, (
            f"Duplicate IDs detected across pages! Total={len(all_combined)}, Unique={len(unique_combined)}. "
            f"Overlap P1-P2={set(ids_p1).intersection(set(ids_p2))}, "
            f"Overlap P2-P3={set(ids_p2).intersection(set(ids_p3))}, "
            f"Overlap P3-P4={set(ids_p3).intersection(set(ids_p4))}"
        )

        # 2. Verify pre-evaluated 92.5% high-fit opportunity is on Page 1
        assert pre_high_opp.id in ids_p1, "Pre-evaluated 92.5% opportunity should appear on Page 1!"

        # 3. Verify pre-evaluated 15.0% low-fit opportunity is relegated to Page 4 (Tier 0)
        assert pre_low_opp.id not in ids_p1, "Low match (15.0%) should not be on Page 1!"
        assert pre_low_opp.id in ids_p4, "Low match (15.0%) should be in Tier 0 on Page 4!"

        # 4. Repeat requests and verify deterministic idempotence
        p1_repeat, _ = await execute_intelligent_discovery_search(
            db=db_session, company=f"AdvCorp_{ts}", tab="recommended", sort_by="match_score", sort_order="desc",
            skip=0, limit=25, user_id=test_uid
        )
        p2_repeat, _ = await execute_intelligent_discovery_search(
            db=db_session, company=f"AdvCorp_{ts}", tab="recommended", sort_by="match_score", sort_order="desc",
            skip=25, limit=25, user_id=test_uid
        )
        assert [r["id"] for r in p1_repeat] == ids_p1, "Page 1 repeated request must be identical!"
        assert [r["id"] for r in p2_repeat] == ids_p2, "Page 2 repeated request must be identical!"

        # ----------------------------------------------------------------------
        # TEST 2: Test Multiple Page Sizes (limit=10)
        # ----------------------------------------------------------------------
        ranking_snapshot_cache.clear()
        p1_10, _ = await execute_intelligent_discovery_search(
            db=db_session, company=f"AdvCorp_{ts}", tab="recommended", sort_by="match_score", sort_order="desc",
            skip=0, limit=10, user_id=test_uid
        )
        p2_10, _ = await execute_intelligent_discovery_search(
            db=db_session, company=f"AdvCorp_{ts}", tab="recommended", sort_by="match_score", sort_order="desc",
            skip=10, limit=10, user_id=test_uid
        )
        ids_10_p1 = [r["id"] for r in p1_10]
        ids_10_p2 = [r["id"] for r in p2_10]
        assert len(set(ids_10_p1).intersection(set(ids_10_p2))) == 0, "No duplicate IDs for limit=10!"

        # ----------------------------------------------------------------------
        # TEST 3: Test Ascending Sort Order (sort_order="asc")
        # ----------------------------------------------------------------------
        ranking_snapshot_cache.clear()
        p1_asc, _ = await execute_intelligent_discovery_search(
            db=db_session, company=f"AdvCorp_{ts}", tab="recommended", sort_by="match_score", sort_order="asc",
            skip=0, limit=25, user_id=test_uid
        )
        # In ascending order, Tier 0 (low scores) should appear first!
        assert p1_asc[0]["id"] == pre_low_opp.id, (
            f"Expected lowest score ({pre_low_opp.id}) at rank 0 for ascending sort, got {p1_asc[0]['id']}"
        )

    finally:
        db_session.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == test_uid).delete(synchronize_session=False)
        for o in created_opps:
            db_session.delete(o)
        db_session.query(CandidateProfile).filter(CandidateProfile.user_id == test_uid).delete(synchronize_session=False)
        db_session.commit()
        ranking_snapshot_cache.clear()


# ==============================================================================
# PHASES 3 & 4: POSTGRESQL CONCURRENT UPSERT & RACE TESTING
# ==============================================================================

def _eval_pair_worker(cand_id: int, user_id: int, opp_id: int):
    """Independent worker thread executing evaluate_match using its own SessionLocal."""
    db = SessionLocal()
    try:
        cand = db.query(CandidateProfile).filter(CandidateProfile.id == cand_id).first()
        opp = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        res = loop.run_until_complete(matching_service.evaluate_match(cand, opp, db, use_ai=False))
        loop.close()
        return {"status": "success", "score": res.profile_match_score, "user_id": user_id, "opp_id": opp_id}
    except Exception as e:
        return {"status": "error", "error": str(e), "type": type(e).__name__}
    finally:
        db.close()


def _eval_batch_worker(cand_id: int, opp_ids: list):
    """Independent worker thread executing evaluate_matches_batch."""
    db = SessionLocal()
    try:
        cand = db.query(CandidateProfile).filter(CandidateProfile.id == cand_id).first()
        opps = db.query(Opportunity).filter(Opportunity.id.in_(opp_ids)).all()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(matching_service.evaluate_matches_batch(cand, opps, db, use_ai=False))
        loop.close()
        return {"status": "success", "count": len(results)}
    except Exception as e:
        return {"status": "error", "error": str(e), "type": type(e).__name__}
    finally:
        db.close()


def test_concurrent_upsert_five_simultaneous_first_time_evaluations(db_session: Session):
    """
    Phase 4:
    Test 5 simultaneous first-time evaluations of the exact same candidate-opportunity pair
    using independent database connections and real PostgreSQL concurrency.
    Verifies:
    1. Zero unhandled UniqueViolation exceptions.
    2. All 5 requests succeed with valid scores.
    3. Exactly 1 persistent row exists in candidate_opportunity_matches.
    """
    test_uid = 94001
    cand = CandidateProfile(
        user_id=test_uid, name="Concurrency Test Candidate",
        skills=[{"name": "Python", "level": "advanced", "category": "language"}]
    )
    db_session.add(cand)
    db_session.commit()
    db_session.refresh(cand)

    ts = int(time.time() * 1000)
    opp = create_opp(
        title=f"Concurrent Test Opp {ts}",
        company_name="RaceCorp",
        description="Python backend concurrency testing.",
        required_skills=["Python"],
        original_url=f"https://race.test/{ts}"
    )
    db_session.add(opp)
    db_session.commit()
    db_session.refresh(opp)

    try:
        # Launch 5 concurrent evaluations of the same pair in parallel threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(_eval_pair_worker, cand.id, test_uid, opp.id)
                for _ in range(5)
            ]
            results = [f.result() for f in futures]

        # Verify all 5 succeeded
        for idx, res in enumerate(results):
            assert res["status"] == "success", f"Worker {idx} failed with {res.get('error')}"
            assert res["score"] > 70.0

        # Verify database has EXACTLY 1 row
        db_rows = (
            db_session.query(CandidateOpportunityMatch)
            .filter(
                CandidateOpportunityMatch.user_id == test_uid,
                CandidateOpportunityMatch.opportunity_id == opp.id
            )
            .all()
        )
        assert len(db_rows) == 1, f"Expected exactly 1 row, found {len(db_rows)}!"
        assert db_rows[0].candidate_id == cand.id

    finally:
        db_session.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == test_uid).delete(synchronize_session=False)
        db_session.delete(opp)
        db_session.delete(cand)
        db_session.commit()


def test_concurrent_batch_requests_overlapping_ids(db_session: Session):
    """
    Phase 4:
    Test 2 concurrent batch evaluation requests with overlapping opportunity IDs.
    Request 1 evaluates opps [0..9].
    Request 2 evaluates opps [5..14].
    Opps [5..9] overlap.
    Verifies:
    1. Both batches succeed without unique constraint collisions.
    2. Exactly 1 row exists for each of the 15 unique opportunity IDs.
    """
    test_uid = 94002
    cand = CandidateProfile(
        user_id=test_uid, name="Batch Race Candidate",
        skills=[{"name": "Python", "level": "advanced", "category": "language"}]
    )
    db_session.add(cand)
    db_session.commit()
    db_session.refresh(cand)

    ts = int(time.time() * 1000)
    opps = [
        create_opp(
            title=f"Batch Opp {ts}_{i}", company_name="OverlapCorp",
            description="Python software engineering.",
            required_skills=["Python"], original_url=f"https://overlap.test/{ts}_{i}"
        )
        for i in range(15)
    ]
    db_session.add_all(opps)
    db_session.commit()

    opp_ids = [o.id for o in opps]
    batch_1_ids = opp_ids[:10]  # IDs 0..9
    batch_2_ids = opp_ids[5:]   # IDs 5..14 (overlap on 5..9)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(_eval_batch_worker, cand.id, batch_1_ids)
            f2 = executor.submit(_eval_batch_worker, cand.id, batch_2_ids)
            r1 = f1.result()
            r2 = f2.result()

        assert r1["status"] == "success", f"Batch 1 failed: {r1}"
        assert r2["status"] == "success", f"Batch 2 failed: {r2}"
        assert r1["count"] == 10
        assert r2["count"] == 10

        # Verify all 15 unique opps have exactly 1 record
        records = (
            db_session.query(CandidateOpportunityMatch)
            .filter(
                CandidateOpportunityMatch.user_id == test_uid,
                CandidateOpportunityMatch.opportunity_id.in_(opp_ids)
            )
            .all()
        )
        assert len(records) == 15, f"Expected 15 records, found {len(records)}"

    finally:
        db_session.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == test_uid).delete(synchronize_session=False)
        for o in opps:
            db_session.delete(o)
        db_session.delete(cand)
        db_session.commit()


def test_concurrent_multi_candidate_public_opportunity_isolation(db_session: Session):
    """
    Phase 4:
    Test Candidate A and Candidate B simultaneously evaluating the same public opportunity.
    Verifies:
    1. Both succeed concurrently.
    2. Exactly 1 row for Candidate A and 1 row for Candidate B.
    3. Scores reflect candidates' individual profiles with zero cross-tenant leakage.
    """
    uid_a = 94003
    uid_b = 94004
    cand_a = CandidateProfile(
        user_id=uid_a, name="Candidate Python",
        skills=[{"name": "Python", "level": "advanced", "category": "language"}]
    )
    cand_b = CandidateProfile(
        user_id=uid_b, name="Candidate Java",
        skills=[{"name": "Java", "level": "advanced", "category": "language"}]
    )
    db_session.add_all([cand_a, cand_b])
    db_session.commit()
    db_session.refresh(cand_a)
    db_session.refresh(cand_b)

    ts = int(time.time() * 1000)
    public_opp = create_opp(
        title=f"Python Public Opp {ts}", company_name="PublicATS",
        description="Python backend development.",
        required_skills=["Python"], original_url=f"https://public.test/{ts}"
    )
    db_session.add(public_opp)
    db_session.commit()
    db_session.refresh(public_opp)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f_a = executor.submit(_eval_pair_worker, cand_a.id, uid_a, public_opp.id)
            f_b = executor.submit(_eval_pair_worker, cand_b.id, uid_b, public_opp.id)
            r_a = f_a.result()
            r_b = f_b.result()

        assert r_a["status"] == "success"
        assert r_b["status"] == "success"
        assert r_a["score"] > 75.0, "Candidate A (Python) should score high (> 75%)"
        assert r_b["score"] < 50.0, "Candidate B (Java) should score in Tier 0 (< 50%)"

        # Verify distinct database rows
        match_a = db_session.query(CandidateOpportunityMatch).filter(
            CandidateOpportunityMatch.user_id == uid_a,
            CandidateOpportunityMatch.opportunity_id == public_opp.id
        ).first()
        match_b = db_session.query(CandidateOpportunityMatch).filter(
            CandidateOpportunityMatch.user_id == uid_b,
            CandidateOpportunityMatch.opportunity_id == public_opp.id
        ).first()

        assert match_a is not None and match_b is not None
        assert match_a.id != match_b.id
        assert match_a.match_score == r_a["score"]
        assert match_b.match_score == r_b["score"]

    finally:
        db_session.query(CandidateOpportunityMatch).filter(
            CandidateOpportunityMatch.user_id.in_([uid_a, uid_b])
        ).delete(synchronize_session=False)
        db_session.delete(public_opp)
        db_session.delete(cand_a)
        db_session.delete(cand_b)
        db_session.commit()


# ==============================================================================
# PHASE 7: RANKING SEMANTICS & EDGE CASE VALIDATION
# ==============================================================================

@pytest.mark.asyncio
async def test_ranking_tier_edge_cases_0_50_100_null(db_session: Session):
    """
    Phase 7:
    Validate ranking tiers across edge cases:
    - Score 100.0 (Tier 2)
    - Score 50.0  (Tier 2 - exact boundary)
    - Score 49.99 (Tier 0 - just below boundary)
    - Score 0.0   (Tier 0 - complete mismatch)
    - Missing score (Tier 1 - unevaluated)
    Verifies that:
    Tier 2 (100.0, 50.0) > Tier 1 (unevaluated NULL) > Tier 0 (49.99, 0.0)
    """
    test_uid = 95001
    ranking_snapshot_cache.clear()

    cand = CandidateProfile(
        user_id=test_uid, name="Tier Edge Candidate",
        skills=[{"name": "Python", "level": "advanced", "category": "language"}]
    )
    db_session.add(cand)
    db_session.commit()
    db_session.refresh(cand)

    ts = int(time.time() * 1000)
    # Create 15 filler opportunities matching Python that will consume the 15-item on-demand evaluation cap
    filler_opps = [
        create_opp(f"Python Filler {ts}_{i:02d}", "TierCorp", "Python backend engineering.", ["Python"], f"https://t.test/{ts}_fill_{i}")
        for i in range(15)
    ]
    target_opps = [
        create_opp(f"Opp Score 100 {ts}", "TierCorp", "desc", ["Python"], f"https://t.test/{ts}_100"),
        create_opp(f"Opp Score 50 {ts}", "TierCorp", "desc", ["Python"], f"https://t.test/{ts}_50"),
        create_opp(f"Opp Unevaluated {ts}", "TierCorp", "desc", ["Other"], f"https://t.test/{ts}_null"),
        create_opp(f"Opp Score 49.99 {ts}", "TierCorp", "desc", ["Other"], f"https://t.test/{ts}_49"),
        create_opp(f"Opp Score 0.0 {ts}", "TierCorp", "desc", ["Other"], f"https://t.test/{ts}_0")
    ]
    all_created = filler_opps + target_opps
    db_session.add_all(all_created)
    db_session.commit()

    opp_100, opp_50, opp_null, opp_49, opp_0 = target_opps

    # Seed explicit match records for the scored opportunities
    for opp, score in [
        (opp_100, 100.0),
        (opp_50, 50.0),
        (opp_49, 49.99),
        (opp_0, 0.0)
    ]:
        db_session.add(CandidateOpportunityMatch(
            user_id=test_uid, candidate_id=cand.id, opportunity_id=opp.id,
            match_score=score, eligibility_status="eligible",
            match_analysis={"profile_match_score": score, "engine_version": MATCHING_ENGINE_VERSION},
            candidate_content_hash="hash", opportunity_content_hash="hash",
            engine_version=MATCHING_ENGINE_VERSION
        ))
    db_session.commit()

    try:
        results, total = await execute_intelligent_discovery_search(
            db=db_session, company="TierCorp", tab="recommended", sort_by="match_score", sort_order="desc",
            limit=25, user_id=test_uid
        )

        res_ids = [r["id"] for r in results]

        # Verify ordering:
        # Tier 2: opp_100 (100.0), filler opps (~85.0), opp_50 (50.0)
        # Tier 1: opp_null (unevaluated NULL)
        # Tier 0: opp_49 (49.99), opp_0 (0.0)
        idx_100 = res_ids.index(opp_100.id)
        idx_50 = res_ids.index(opp_50.id)
        idx_null = res_ids.index(opp_null.id)
        idx_49 = res_ids.index(opp_49.id)
        idx_0 = res_ids.index(opp_0.id)

        assert idx_100 < idx_50, "100.0 should rank before 50.0"
        assert idx_50 < idx_null, "50.0 (Tier 2) should rank before unevaluated NULL (Tier 1)"
        assert idx_null < idx_49, "Unevaluated NULL (Tier 1) should rank before 49.99 (Tier 0)"
        assert idx_49 < idx_0, "49.99 should rank before 0.0"

        # Verify intelligence and evaluation state
        opp_null_rec = next(r for r in results if r["id"] == opp_null.id)
        opp_50_rec = next(r for r in results if r["id"] == opp_50.id)
        opp_49_rec = next(r for r in results if r["id"] == opp_49.id)

        assert opp_null_rec["ranking_reasons"]["evaluation_state"] == "not_evaluated"
        assert opp_50_rec["ranking_reasons"]["evaluation_state"] == "evaluated_moderate"
        assert opp_49_rec["ranking_reasons"]["evaluation_state"] == "evaluated_low"

    finally:
        db_session.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == test_uid).delete(synchronize_session=False)
        for o in all_created:
            db_session.delete(o)
        db_session.delete(cand)
        db_session.commit()
        ranking_snapshot_cache.clear()


# ==============================================================================
# PHASE 5: RECONCILED BENCHMARKS (WARM, COLD, PARTIAL, STALE)
# ==============================================================================

@pytest.mark.asyncio
async def test_reconciled_benchmark_matrix_scenarios_a_b_c_d(db_session: Session):
    """
    Phase 5:
    Reconciles the performance measurements across catalogue sizes (50, 100, 500, 1000):
    Scenario A: Fully warm cache (all evaluations exist and valid)
    Scenario B: Cold cache (no evaluations exist)
    Scenario C: Partially warm cache (some evaluations exist, some missing)
    Scenario D: Stale cache (outdated hash/version requiring re-evaluation)
    """
    test_uid = 96001
    ranking_snapshot_cache.clear()

    cand = CandidateProfile(
        user_id=test_uid, name="Reconciled Benchmark Candidate",
        skills=[
            {"name": "Python", "level": "advanced", "category": "language"},
            {"name": "FastAPI", "level": "advanced", "category": "framework"}
        ],
        preferred_locations=["remote"]
    )
    db_session.add(cand)
    db_session.commit()
    db_session.refresh(cand)

    catalog_sizes = [50, 100, 500, 1000]
    ts = int(time.time() * 1000)
    all_opp_ids = []

    print("\n" + "=" * 90)
    print("PHASE 5 RECONCILED PERFORMANCE BENCHMARK MATRIX")
    print("=" * 90)

    try:
        for size in catalog_sizes:
            needed = size - len(all_opp_ids)
            if needed > 0:
                new_opps = [
                    create_opp(
                        title=f"Bench Role {len(all_opp_ids)+i}", company_name=f"ReconcileCorp_{ts}",
                        description="Python software engineering.",
                        required_skills=["Python"], original_url=f"https://rec.test/{ts}_{len(all_opp_ids)+i}"
                    )
                    for i in range(needed)
                ]
                db_session.add_all(new_opps)
                db_session.commit()
                all_opp_ids.extend([o.id for o in new_opps])

            all_opps = db_session.query(Opportunity).filter(Opportunity.id.in_(all_opp_ids)).all()

            # SCENARIO B: Cold Cache (No evaluations)
            db_session.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == test_uid).delete(synchronize_session=False)
            db_session.commit()
            ranking_snapshot_cache.clear()

            with QueryCounter(engine) as cold_qc:
                t0 = time.perf_counter()
                res_b, _ = await execute_intelligent_discovery_search(
                    db=db_session, company=f"ReconcileCorp_{ts}", tab="recommended", sort_by="match_score", sort_order="desc",
                    limit=25, user_id=test_uid
                )
                t_cold = (time.perf_counter() - t0) * 1000.0

            # SCENARIO A: Fully Warm Cache (All evaluated and valid)
            await matching_service.evaluate_matches_batch(cand, all_opps, db_session)
            ranking_snapshot_cache.clear()

            warm_times = []
            warm_queries = []
            for _ in range(5):
                with QueryCounter(engine) as warm_qc:
                    t0 = time.perf_counter()
                    res_a, _ = await execute_intelligent_discovery_search(
                        db=db_session, company=f"ReconcileCorp_{ts}", tab="recommended", sort_by="match_score", sort_order="desc",
                        limit=25, user_id=test_uid
                    )
                    t_w = (time.perf_counter() - t0) * 1000.0
                warm_times.append(t_w)
                warm_queries.append(warm_qc.count)

            avg_warm = statistics.mean(warm_times)
            p50_warm = sorted(warm_times)[len(warm_times) // 2]
            p95_warm = sorted(warm_times)[-1]
            avg_warm_q = statistics.mean(warm_queries)

            # SCENARIO C: Partially Warm Cache (5 records missing)
            del_matches = (
                db_session.query(CandidateOpportunityMatch)
                .filter(CandidateOpportunityMatch.user_id == test_uid)
                .limit(5)
                .all()
            )
            for m in del_matches:
                db_session.delete(m)
            db_session.commit()
            ranking_snapshot_cache.clear()

            with QueryCounter(engine) as part_qc:
                t0 = time.perf_counter()
                res_c, _ = await execute_intelligent_discovery_search(
                    db=db_session, company=f"ReconcileCorp_{ts}", tab="recommended", sort_by="match_score", sort_order="desc",
                    limit=25, user_id=test_uid
                )
                t_part = (time.perf_counter() - t0) * 1000.0

            # SCENARIO D: Stale Cache (5 records have outdated hash)
            stale_matches = (
                db_session.query(CandidateOpportunityMatch)
                .filter(CandidateOpportunityMatch.user_id == test_uid)
                .limit(5)
                .all()
            )
            for m in stale_matches:
                m.candidate_content_hash = "stale_hash_value"
            db_session.commit()
            ranking_snapshot_cache.clear()

            with QueryCounter(engine) as stale_qc:
                t0 = time.perf_counter()
                res_d, _ = await execute_intelligent_discovery_search(
                    db=db_session, company=f"ReconcileCorp_{ts}", tab="recommended", sort_by="match_score", sort_order="desc",
                    limit=25, user_id=test_uid
                )
                t_stale = (time.perf_counter() - t0) * 1000.0

            print(
                f"Catalogue Size {size:4d} | "
                f"Cold: {t_cold:6.2f}ms ({cold_qc.count:2d} q) | "
                f"Warm: Avg={avg_warm:5.2f}ms P50={p50_warm:5.2f}ms P95={p95_warm:5.2f}ms ({avg_warm_q:.1f} q) | "
                f"Partial: {t_part:5.2f}ms ({part_qc.count:2d} q) | "
                f"Stale: {t_stale:5.2f}ms ({stale_qc.count:2d} q)"
            )

            # Assert warm search latency remains comfortably under 100ms
            assert avg_warm < 100.0, f"Warm search exceeded 100ms for catalogue size {size}: {avg_warm:.2f}ms"

    finally:
        db_session.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == test_uid).delete(synchronize_session=False)
        for o in db_session.query(Opportunity).filter(Opportunity.id.in_(all_opp_ids)).all():
            db_session.delete(o)
        db_session.delete(cand)
        db_session.commit()
        ranking_snapshot_cache.clear()
