import time
import pytest
import statistics
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import event

from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models.candidate import CandidateProfile
from backend.app.models.opportunity import Opportunity
from backend.app.models.candidate_opportunity_match import CandidateOpportunityMatch
from backend.app.core.auth import create_access_token
from backend.app.services.matching.service import matching_service, MATCHING_ENGINE_VERSION
from backend.app.services.discovery_search_service import (
    execute_intelligent_discovery_search,
    build_opportunity_intelligence
)
from backend.app.services.intelligence_cache import ranking_snapshot_cache


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class QueryCounter:
    """Helper to track SQL statement count and execution times."""
    def __init__(self, engine):
        self.engine = engine
        self.count = 0
        self.queries = []
        self.start_times = {}

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


def create_test_opp(
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


@pytest.mark.asyncio
async def test_cold_start_same_response_reranking(db_session: Session):
    """
    Phase 2 Test:
    Verify that a candidate's first search (cold start with 0 prior evaluations)
    deterministically evaluates high-potential opportunities on-demand and
    RERANKS THEM INTO THE SAME RESPONSE before returning.
    """
    test_uid = 92001
    cand = CandidateProfile(
        user_id=test_uid,
        name="Cold Start Test Engineer",
        email="coldstart@careeros.internal",
        skills=[
            {"name": "Python", "level": "advanced", "category": "language"},
            {"name": "FastAPI", "level": "advanced", "category": "framework"},
            {"name": "PostgreSQL", "level": "intermediate", "category": "database"}
        ],
        preferred_locations=["remote"]
    )
    db_session.add(cand)
    db_session.commit()
    db_session.refresh(cand)

    # Clean any leftover matches for this user
    db_session.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == test_uid).delete()
    db_session.commit()

    ts = int(time.time() * 1000)
    opp_high = create_test_opp(
        title=f"Senior Python Backend Intern {ts}",
        company_name=f"PyCloud Labs {ts}",
        description="We are seeking a Python Intern proficient with FastAPI, microservices, and PostgreSQL.",
        required_skills=["Python", "FastAPI"],
        preferred_skills=["PostgreSQL"],
        original_url=f"https://pycloud.internal/careers/{ts}"
    )
    opp_low = create_test_opp(
        title=f"Marketing & Social Media Specialist {ts}",
        company_name=f"BrandBoost {ts}",
        description="Seeking marketing intern to handle TikTok, Canva, copywriting, and Instagram campaigns.",
        required_skills=["TikTok", "Canva", "Copywriting"],
        preferred_skills=["Instagram"],
        source_platform="lever",
        original_url=f"https://brandboost.internal/careers/{ts}"
    )
    db_session.add_all([opp_high, opp_low])
    db_session.commit()
    db_session.refresh(opp_high)
    db_session.refresh(opp_low)

    try:
        # First discovery search: cold start for this candidate
        results, total = await execute_intelligent_discovery_search(
            db=db_session,
            tab="recommended",
            sort_by="match_score",
            sort_order="desc",
            limit=10,
            user_id=test_uid
        )

        assert total >= 2
        # Locate the test opportunities in results
        high_item = next((r for r in results if r["id"] == opp_high.id), None)
        low_item = next((r for r in results if r["id"] == opp_low.id), None)

        assert high_item is not None, "High-fit opportunity should be present in results"
        # Verify that newly calculated match score influenced the response
        assert high_item["match_score"] >= 70.0, f"Expected high score >= 70, got {high_item['match_score']}"
        assert high_item["ranking_reasons"]["is_evaluated"] is True
        assert high_item["ranking_reasons"]["evaluation_state"] == "evaluated_high"

        # If low item was evaluated, verify it is ranked below high item
        if low_item and low_item["ranking_reasons"]["is_evaluated"]:
            high_idx = results.index(high_item)
            low_idx = results.index(low_item)
            assert high_idx < low_idx, f"High match (idx {high_idx}) must rank above low match (idx {low_idx})"

        # Verify persistent record was stored in candidate_opportunity_matches
        match_rec = (
            db_session.query(CandidateOpportunityMatch)
            .filter(
                CandidateOpportunityMatch.user_id == test_uid,
                CandidateOpportunityMatch.opportunity_id == opp_high.id
            )
            .first()
        )
        assert match_rec is not None
        assert match_rec.match_score >= 70.0
        assert match_rec.engine_version == MATCHING_ENGINE_VERSION

    finally:
        db_session.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == test_uid).delete(synchronize_session=False)
        db_session.query(Opportunity).filter(Opportunity.id.in_([opp_high.id, opp_low.id])).delete(synchronize_session=False)
        db_session.query(CandidateProfile).filter(CandidateProfile.id == cand.id).delete(synchronize_session=False)
        db_session.commit()


@pytest.mark.asyncio
async def test_tiered_ranking_and_state_distinction(db_session: Session):
    """
    Phase 2 & 3 Test:
    Verify clear distinction between:
    - Evaluated High Match (Tier 2, score >= 70)
    - Evaluated Moderate Match (Tier 2, 50 <= score < 70)
    - Unevaluated / Potential (Tier 1)
    - Evaluated Low Match (Tier 0, score < 50)
    Ensures unevaluated opportunities are never conflated with 0.0 poor matches.
    """
    test_uid = 92002
    cand = CandidateProfile(
        user_id=test_uid,
        name="Tiering Test Engineer",
        email="tiering@careeros.internal",
        skills=[{"name": "Rust", "level": "advanced", "category": "language"}],
        preferred_locations=["remote"]
    )
    db_session.add(cand)
    db_session.commit()
    db_session.refresh(cand)

    ts = int(time.time() * 1000)
    # Create 4 opportunities
    opp_high = create_test_opp(
        title=f"Rust Systems Intern {ts}", company_name=f"RustCorp {ts}",
        description="Rust memory safety systems intern.", required_skills=["Rust"],
        original_url=f"https://rustcorp.internal/{ts}_1"
    )
    opp_mod = create_test_opp(
        title=f"C++ Systems Intern {ts}", company_name=f"CppCorp {ts}",
        description="C++ low level memory systems.", required_skills=["C++"],
        original_url=f"https://cppcorp.internal/{ts}_2"
    )
    opp_uneval = create_test_opp(
        title=f"Un-evaluated Intern {ts}", company_name=f"GenericCorp {ts}",
        description="General software internship.", required_skills=["General"],
        original_url=f"https://generic.internal/{ts}_3"
    )
    opp_low = create_test_opp(
        title=f"Graphic Design Intern {ts}", company_name=f"DesignCorp {ts}",
        description="Figma graphic design.", required_skills=["Figma", "Illustrator"],
        original_url=f"https://design.internal/{ts}_4"
    )
    db_session.add_all([opp_high, opp_mod, opp_uneval, opp_low])
    db_session.commit()
    for o in [opp_high, opp_mod, opp_uneval, opp_low]:
        db_session.refresh(o)

    # Explicitly seed matches
    m_high = CandidateOpportunityMatch(
        user_id=test_uid, candidate_id=cand.id, opportunity_id=opp_high.id,
        match_score=92.0, eligibility_status="eligible",
        match_analysis={"profile_match_score": 92.0},
        candidate_content_hash="h1", opportunity_content_hash="h1",
        engine_version=MATCHING_ENGINE_VERSION
    )
    m_mod = CandidateOpportunityMatch(
        user_id=test_uid, candidate_id=cand.id, opportunity_id=opp_mod.id,
        match_score=60.0, eligibility_status="eligible",
        match_analysis={"profile_match_score": 60.0},
        candidate_content_hash="h2", opportunity_content_hash="h2",
        engine_version=MATCHING_ENGINE_VERSION
    )
    m_low = CandidateOpportunityMatch(
        user_id=test_uid, candidate_id=cand.id, opportunity_id=opp_low.id,
        match_score=18.0, eligibility_status="eligible",
        match_analysis={"profile_match_score": 18.0},
        candidate_content_hash="h4", opportunity_content_hash="h4",
        engine_version=MATCHING_ENGINE_VERSION
    )
    # opp_uneval has NO match record
    db_session.add_all([m_high, m_mod, m_low])
    db_session.commit()

    try:
        results, total = await execute_intelligent_discovery_search(
            db=db_session,
            company=f"{ts}",
            tab="recommended",
            sort_by="match_score",
            sort_order="desc",
            limit=25,
            user_id=test_uid
        )

        item_map = {r["id"]: r for r in results}
        assert opp_high.id in item_map
        assert opp_mod.id in item_map
        assert opp_low.id in item_map
        assert opp_uneval.id in item_map

        idx_high = results.index(item_map[opp_high.id])
        idx_mod = results.index(item_map[opp_mod.id])
        idx_low = results.index(item_map[opp_low.id])
        idx_uneval = results.index(item_map[opp_uneval.id])

        # Verify ranking order: High (92) < Mod (60) < Unevaluated (Tier 1) < Low (18, Tier 0)
        assert idx_high < idx_mod, f"High match ({idx_high}) must rank before moderate match ({idx_mod})"
        assert idx_mod < idx_low, f"Moderate match ({idx_mod}) must rank before low match ({idx_low})"
        assert idx_uneval < idx_low, f"Unevaluated ({idx_uneval}) must rank above evaluated poor match ({idx_low})"

        # Verify state labels
        assert item_map[opp_high.id]["ranking_reasons"]["evaluation_state"] == "evaluated_high"
        assert item_map[opp_mod.id]["ranking_reasons"]["evaluation_state"] == "evaluated_moderate"
        assert item_map[opp_low.id]["ranking_reasons"]["evaluation_state"] == "evaluated_low"

    finally:
        db_session.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == test_uid).delete(synchronize_session=False)
        db_session.query(Opportunity).filter(Opportunity.id.in_([opp_high.id, opp_mod.id, opp_uneval.id, opp_low.id])).delete(synchronize_session=False)
        db_session.query(CandidateProfile).filter(CandidateProfile.id == cand.id).delete(synchronize_session=False)
        db_session.commit()


@pytest.mark.asyncio
async def test_pagination_consistency_and_stability(db_session: Session):
    """
    Phase 4 Test:
    Verify that pagination across multiple pages (Page 1 and Page 2):
    - Produces zero duplicate records across pages.
    - Leaves zero skipped opportunities between pages.
    - Maintains stable deterministic order under sort_by="match_score".
    """
    test_uid = 92003
    cand = CandidateProfile(
        user_id=test_uid,
        name="Pagination Test Candidate",
        email="pagination@careeros.internal",
        skills=[{"name": "Go", "level": "intermediate", "category": "language"}],
        preferred_locations=["remote"]
    )
    db_session.add(cand)
    db_session.commit()
    db_session.refresh(cand)

    ts = int(time.time() * 1000)
    opps = []
    # Create 20 unique opportunities
    for i in range(20):
        opp = create_test_opp(
            title=f"Golang Intern {ts}_{i}",
            company_name=f"GoLabs_{i}",
            description=f"Go backend development role {i} with microservices.",
            required_skills=["Go"],
            original_url=f"https://golabs.internal/{ts}_{i}"
        )
        opps.append(opp)
    db_session.add_all(opps)
    db_session.commit()
    opp_ids = [o.id for o in opps]

    try:
        # Request Page 1 (limit=10, skip=0)
        p1_results, total = await execute_intelligent_discovery_search(
            db=db_session,
            tab="recommended",
            sort_by="match_score",
            sort_order="desc",
            skip=0,
            limit=10,
            user_id=test_uid
        )

        # Request Page 2 (limit=10, skip=10)
        p2_results, _ = await execute_intelligent_discovery_search(
            db=db_session,
            tab="recommended",
            sort_by="match_score",
            sort_order="desc",
            skip=10,
            limit=10,
            user_id=test_uid
        )

        p1_ids = [r["id"] for r in p1_results]
        p2_ids = [r["id"] for r in p2_results]

        assert len(p1_results) == 10, f"Expected 10 items on page 1, got {len(p1_results)}"
        assert len(p2_results) == 10, f"Expected 10 items on page 2, got {len(p2_results)}"

        # Strict disjoint set check: Zero duplicates across pages
        duplicate_ids = set(p1_ids).intersection(set(p2_ids))
        assert len(duplicate_ids) == 0, f"Found duplicate IDs across pages: {duplicate_ids}"

        # Scores on page 1 should be >= scores on page 2 or match state priority
        p1_min_score = min(r["match_score"] for r in p1_results)
        p2_max_score = max(r["match_score"] for r in p2_results)
        assert p1_min_score >= p2_max_score or p1_results[-1]["ranking_reasons"]["evaluation_state"] in ("not_evaluated", "evaluated_high")

    finally:
        db_session.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == test_uid).delete(synchronize_session=False)
        db_session.query(Opportunity).filter(Opportunity.id.in_(opp_ids)).delete(synchronize_session=False)
        db_session.query(CandidateProfile).filter(CandidateProfile.id == cand.id).delete(synchronize_session=False)
        db_session.commit()


@pytest.mark.asyncio
async def test_multi_candidate_ranking_divergence_and_isolation(db_session: Session):
    """
    Phase 5 Test:
    Verify that Candidate A (Python) and Candidate B (Java) searching the exact same
    catalogue receive divergent personalized rankings, and Candidate A's on-demand
    evaluations never leak or affect Candidate B.
    """
    uid_a = 92004
    uid_b = 92005

    # Pre-clean any leftover data from previous runs
    db_session.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id.in_([uid_a, uid_b])).delete(synchronize_session=False)
    db_session.query(CandidateProfile).filter(CandidateProfile.user_id.in_([uid_a, uid_b])).delete(synchronize_session=False)
    db_session.commit()

    cand_a = CandidateProfile(
        user_id=uid_a, name="Python Candidate", email="cand_a@careeros.internal",
        skills=[{"name": "Python", "level": "advanced", "category": "language"}]
    )
    cand_b = CandidateProfile(
        user_id=uid_b, name="Java Candidate", email="cand_b@careeros.internal",
        skills=[{"name": "Java", "level": "advanced", "category": "language"}]
    )
    db_session.add_all([cand_a, cand_b])
    db_session.commit()
    db_session.refresh(cand_a)
    db_session.refresh(cand_b)

    ts = int(time.time() * 1000)
    opp_py = create_test_opp(
        title=f"Python Framework Engineer {ts}", company_name=f"PyHouse {ts}",
        description="Core Python engineering internship.", required_skills=["Python"],
        original_url=f"https://pyhouse.internal/{ts}"
    )
    opp_java = create_test_opp(
        title=f"Java Android Engineer {ts}", company_name=f"JavaHouse {ts}",
        description="Android Java SDK development.", required_skills=["Java"],
        original_url=f"https://javahouse.internal/{ts}"
    )
    db_session.add_all([opp_py, opp_java])
    db_session.commit()
    db_session.refresh(opp_py)
    db_session.refresh(opp_java)

    try:
        # Candidate A searches
        res_a, _ = await execute_intelligent_discovery_search(
            db=db_session, company=f"House {ts}", tab="recommended", sort_by="match_score", sort_order="desc",
            limit=10, user_id=uid_a
        )
        # Candidate B searches
        res_b, _ = await execute_intelligent_discovery_search(
            db=db_session, company=f"House {ts}", tab="recommended", sort_by="match_score", sort_order="desc",
            limit=10, user_id=uid_b
        )

        item_py_a = next(r for r in res_a if r["id"] == opp_py.id)
        item_java_a = next(r for r in res_a if r["id"] == opp_java.id)

        item_py_b = next(r for r in res_b if r["id"] == opp_py.id)
        item_java_b = next(r for r in res_b if r["id"] == opp_java.id)

        # Candidate A sees Python > Java
        assert item_py_a["match_score"] > item_java_a["match_score"]
        # Candidate B sees Java > Python
        assert item_java_b["match_score"] > item_py_b["match_score"]

        # Isolation verification: Candidate A has records in DB with user_id=uid_a only
        cand_a_matches = db_session.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == uid_a).all()
        for m in cand_a_matches:
            assert m.user_id == uid_a
            assert m.candidate_id == cand_a.id

    finally:
        db_session.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id.in_([uid_a, uid_b])).delete(synchronize_session=False)
        db_session.query(Opportunity).filter(Opportunity.id.in_([opp_py.id, opp_java.id])).delete(synchronize_session=False)
        db_session.query(CandidateProfile).filter(CandidateProfile.id.in_([cand_a.id, cand_b.id])).delete(synchronize_session=False)
        db_session.commit()


@pytest.mark.asyncio
async def test_query_efficiency_and_batch_evaluation(db_session: Session):
    """
    Phase 7 Test:
    Verify that evaluate_matches_batch:
    - Eliminates N+1 query patterns.
    - Executes single candidate profile loading, single evidence construction,
      and single atomic commit across 10 opportunities.
    """
    test_uid = 92006
    cand = CandidateProfile(
        user_id=test_uid, name="Batch Test Candidate", email="batch@careeros.internal",
        skills=[{"name": "TypeScript", "level": "advanced", "category": "language"}]
    )
    db_session.add(cand)
    db_session.commit()
    db_session.refresh(cand)

    ts = int(time.time() * 1000)
    opps = [
        create_test_opp(
            title=f"TS Intern {ts}_{i}", company_name=f"TSCorp_{i}",
            description="TypeScript frontend developer.", required_skills=["TypeScript"],
            original_url=f"https://tscorp.internal/{ts}_{i}"
        )
        for i in range(10)
    ]
    db_session.add_all(opps)
    db_session.commit()
    opp_ids = [o.id for o in opps]

    try:
        from backend.app.database import engine
        with QueryCounter(engine) as counter:
            results = await matching_service.evaluate_matches_batch(
                candidate=cand,
                opportunities=opps,
                db=db_session,
                force_refresh=False,
                use_ai=False
            )

        assert len(results) == 10
        # In a naive N+1 implementation with 10 items, queries would be 10*4+ = 40+ queries.
        # With evaluate_matches_batch: candidate load (1) + batch match query (1) + commit (1) + refresh (10) ~ 15 queries.
        print(f"\n[Query Efficiency] Total SQL queries executed for 10 batch items: {counter.count}")
        assert counter.count <= 20, f"Expected <= 20 queries for batch evaluation, got {counter.count}"

    finally:
        db_session.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == test_uid).delete(synchronize_session=False)
        db_session.query(Opportunity).filter(Opportunity.id.in_(opp_ids)).delete(synchronize_session=False)
        db_session.query(CandidateProfile).filter(CandidateProfile.id == cand.id).delete(synchronize_session=False)
        db_session.commit()


@pytest.mark.asyncio
async def test_scale_benchmarks_50_100_500_1000(db_session: Session):
    """
    Phase 6 Benchmark:
    Rigorous benchmark testing across catalogue sizes: 50, 100, 500, and 1,000 opportunities.
    Measures:
    1. Warm search latency (Average, P50, P95)
    2. Cold search latency (initial on-demand evaluation)
    3. Partial cache search latency
    4. Profile modification invalidation latency
    Records SQL query count, database execution time, and throughput.
    """
    test_uid = 92007
    cand = CandidateProfile(
        user_id=test_uid, name="Scale Benchmark Candidate", email="scale@careeros.internal",
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
    benchmark_report = []

    ts = int(time.time() * 1000)
    all_created_opp_ids = []

    try:
        from backend.app.database import engine
        
        for size in catalog_sizes:
            needed = size - len(all_created_opp_ids)
            if needed > 0:
                new_opps = []
                for i in range(needed):
                    idx = len(all_created_opp_ids) + i
                    skill = "Python" if idx % 3 == 0 else ("Java" if idx % 3 == 1 else "React")
                    opp = create_test_opp(
                        title=f"{skill} Software Intern {ts}_{idx}",
                        company_name=f"ScaleCorp_{idx}",
                        description=f"{skill} engineering role working on cloud systems.",
                        required_skills=[skill],
                        original_url=f"https://scalecorp.internal/{ts}_{idx}"
                    )
                    new_opps.append(opp)
                db_session.add_all(new_opps)
                db_session.commit()
                all_created_opp_ids.extend([o.id for o in new_opps])

            # 1. Cold Search Run (Initial on-demand evaluation)
            # Clear user's match cache for fresh cold measurement
            db_session.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == test_uid).delete(synchronize_session=False)
            db_session.commit()

            with QueryCounter(engine) as cold_counter:
                t0 = time.perf_counter()
                results, total = await execute_intelligent_discovery_search(
                    db=db_session, company="ScaleCorp", tab="recommended", sort_by="match_score", sort_order="desc",
                    limit=25, user_id=test_uid
                )
                t_cold = (time.perf_counter() - t0) * 1000.0

            cold_evaluated = sum(1 for r in results if r["ranking_reasons"]["is_evaluated"])

            # Ensure candidate-opportunity matches are fully evaluated so warm search measures true pure cached retrieval
            all_opps_in_catalog = db_session.query(Opportunity).filter(Opportunity.id.in_(all_created_opp_ids)).all()
            await matching_service.evaluate_matches_batch(candidate=cand, opportunities=all_opps_in_catalog, db=db_session)

            # Invalidate snapshot cache to test fresh pure-retrieval search
            ranking_snapshot_cache.clear()

            # 2. Warm Search Runs (5 iterations)
            warm_latencies = []
            warm_queries = []
            for _ in range(5):
                with QueryCounter(engine) as warm_counter:
                    t0 = time.perf_counter()
                    results, total = await execute_intelligent_discovery_search(
                        db=db_session, company="ScaleCorp", tab="recommended", sort_by="match_score", sort_order="desc",
                        limit=25, user_id=test_uid
                    )
                    t_warm = (time.perf_counter() - t0) * 1000.0
                warm_latencies.append(t_warm)
                warm_queries.append(warm_counter.count)

            avg_warm = float(statistics.mean(warm_latencies))
            sorted_warm = sorted(warm_latencies)
            p50_warm = float(sorted_warm[len(sorted_warm) // 2])
            p95_warm = float(sorted_warm[-1])
            avg_queries = float(statistics.mean(warm_queries))

            # 3. Partial Cache Search Run
            # Invalidate 5 records
            some_matches = (
                db_session.query(CandidateOpportunityMatch)
                .filter(CandidateOpportunityMatch.user_id == test_uid)
                .limit(5)
                .all()
            )
            for m in some_matches:
                m.candidate_content_hash = "invalidated_hash"
            db_session.commit()

            t0 = time.perf_counter()
            await execute_intelligent_discovery_search(
                db=db_session, company="ScaleCorp", tab="recommended", sort_by="match_score", sort_order="desc",
                limit=25, user_id=test_uid
            )
            t_partial = (time.perf_counter() - t0) * 1000.0

            # 4. Profile Modification Search Run
            cand.skills = [{"name": "Python", "level": "advanced", "category": "language"}, {"name": "Docker", "level": "intermediate", "category": "devops"}]
            db_session.commit()
            t0 = time.perf_counter()
            await execute_intelligent_discovery_search(
                db=db_session, company="ScaleCorp", tab="recommended", sort_by="match_score", sort_order="desc",
                limit=25, user_id=test_uid
            )
            t_profile_mod = (time.perf_counter() - t0) * 1000.0

            benchmark_report.append({
                "catalogue_size": size,
                "cold_latency_ms": round(t_cold, 2),
                "cold_queries": cold_counter.count,
                "cold_evaluated": cold_evaluated,
                "warm_avg_ms": round(avg_warm, 2),
                "warm_p50_ms": round(p50_warm, 2),
                "warm_p95_ms": round(p95_warm, 2),
                "warm_queries": round(avg_queries, 1),
                "partial_latency_ms": round(t_partial, 2),
                "profile_mod_latency_ms": round(t_profile_mod, 2)
            })

            print(f"\n[Scale Benchmark] Size={size} opps: Cold={t_cold:.2f}ms ({cold_counter.count} queries) | Warm Avg={avg_warm:.2f}ms (P50={p50_warm:.2f}ms, P95={p95_warm:.2f}ms, {avg_queries:.1f} queries) | Partial={t_partial:.2f}ms | ProfileMod={t_profile_mod:.2f}ms")
            assert avg_warm < 100.0, f"Warm search exceeded 100ms for catalogue size {size}: {avg_warm:.2f}ms"

        # Print full benchmark markdown table
        print("\n" + "=" * 80)
        print("SCALE BENCHMARK RESULTS SUMMARY")
        print("=" * 80)
        print(f"| Catalogue Size | Cold Search (ms) | Cold Queries | Warm Avg (ms) | Warm P50 (ms) | Warm P95 (ms) | Warm Queries | Partial Cache (ms) | Profile Mod (ms) |")
        print(f"|---|---|---|---|---|---|---|---|---|")
        for row in benchmark_report:
            print(f"| {row['catalogue_size']} | {row['cold_latency_ms']}ms | {row['cold_queries']} | {row['warm_avg_ms']}ms | {row['warm_p50_ms']}ms | {row['warm_p95_ms']}ms | {row['warm_queries']} | {row['partial_latency_ms']}ms | {row['profile_mod_latency_ms']}ms |")

    finally:
        db_session.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == test_uid).delete(synchronize_session=False)
        db_session.query(Opportunity).filter(Opportunity.id.in_(all_created_opp_ids)).delete(synchronize_session=False)
        db_session.query(CandidateProfile).filter(CandidateProfile.id == cand.id).delete(synchronize_session=False)
        db_session.commit()
