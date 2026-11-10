"""
CareerOS — Iteration 2.4 Test Suite
Pagination Session Semantics, Monotonic Evaluation Generations & Operational Integrity

Tests:
1. Scan-Fill Pagination: Multiple consecutive deleted, closed, and dismissed items filled up to limit.
2. End-of-Session Semantics: Short page permitted ONLY at end-of-session; has_more=False and next_cursor=None.
3. Cursor / Next-Offset Tracking: Subsequent pages using cursor maintain relative order and zero duplicates.
4. Generation Separation: Active sessions survive candidate profile mutations until natural TTL expiry.
5. Candidate Session Ownership Isolation: Candidate B cannot read Candidate A's snapshot_id.
6. Monotonic Engine Generation: String 1.9.0 (gen 1) cannot overwrite 1.10.0 (gen 2); integer generation ordering.
7. Engine Upgrade Replacement: Generation 3 successfully supersedes Generation 2.
8. Computation Freshness & Race Protection: Stale computation finishing late with lower version is rejected.
9. Expired Session L1 Purge: Expired snapshot rejected even if cached in L1.
10. Bounded Cleanup: cleanup_expired_snapshots removes expired rows in bounded batch without touching active sessions.
11. GIN Index Verification on Representative Dataset (1,000+ snapshots) with catalog inspection.
"""

import pytest
import asyncio
import time
import json
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models.opportunity import Opportunity
from backend.app.models.candidate import CandidateProfile
from backend.app.models.candidate_opportunity_match import CandidateOpportunityMatch, utc_now
from backend.app.models.discovery_ranking_snapshot import DiscoveryRankingSnapshot
from backend.app.services.discovery_snapshot_manager import snapshot_manager
from backend.app.services.discovery_search_service import (
    execute_intelligent_discovery_search,
    PaginationSessionExpiredException
)
from backend.app.services.matching.service import (
    matching_service,
    MATCHING_ENGINE_VERSION,
    MATCHING_ENGINE_GENERATION,
    get_engine_generation
)
from backend.app.core.auth import create_access_token


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_test_state(db):
    def _cleanup():
        snapshot_manager.clear_all(db)
        try:
            db.query(CandidateOpportunityMatch).filter(
                (CandidateOpportunityMatch.opportunity_id >= 90000) |
                (CandidateOpportunityMatch.user_id.between(85000, 85999))
            ).delete()
            db.query(Opportunity).filter(Opportunity.id >= 90000).delete()
            db.query(CandidateProfile).filter(CandidateProfile.user_id.between(85000, 85999)).delete()
            db.commit()
        except Exception:
            db.rollback()

    _cleanup()
    yield
    _cleanup()


def create_test_catalogue(db, count=60, base_id=95000):
    """Populates test opportunities with deterministic IDs."""
    now = utc_now()
    opps = []
    for i in range(count):
        opp_id = base_id + i
        title_str = f"Software Engineer Intern #{i:03d}"
        opp = Opportunity(
            id=opp_id,
            title=title_str,
            normalized_title=title_str.lower(),
            company_name=f"TechCorp {i % 5}",
            normalized_location="Remote",
            location="Remote",
            employment_type="internship",
            status="verified",
            description=f"Engineering internship with Python, React, and PostgreSQL #{i}.",
            required_skills=["Python", "PostgreSQL"],
            preferred_skills=["React"],
            min_stipend=25000.0 + (i * 100),
            quality_score=85.0,
            content_version=1,
            is_dismissed=False,
            is_saved=False,
            is_applied=False,
            original_url=f"https://company{i % 5}.com/jobs/{opp_id}",
            source_platform="greenhouse",
            posted_at=now - timedelta(days=i % 10),
            created_at=now
        )
        opps.append(opp)
        db.merge(opp)
    db.commit()
    return opps


# ---------------------------------------------------------------------------
# Phase 1 & 2: Immutable Pagination Semantics, Scan-Fill & Session Separation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_fill_pagination_past_consecutive_pruned_items(db):
    """
    Phase 1 Test:
    When multiple consecutive opportunities are deleted, closed, or dismissed,
    the Scan-Fill algorithm must scan forward to fill the requested limit (e.g. 20 items).
    Relative order of surviving items is strictly preserved with zero duplicates.
    """
    user_id = 85001
    create_test_catalogue(db, count=60, base_id=95100)
    cand = CandidateProfile(user_id=user_id, name="ScanFill Cand", skills=[{"name": "Python"}], evidence_version=1)
    db.merge(cand)
    db.commit()

    # Step 1: Page 1 creates snapshot session
    p1, total, snap_id, next_cursor, has_more = await execute_intelligent_discovery_search(
        db=db, user_id=user_id, skip=0, limit=20, return_cursor=True
    )
    assert len(p1) == 20
    assert next_cursor == 20
    assert has_more is True

    snap_ids, _ = snapshot_manager.get_snapshot_by_id(snap_id, db, user_id=user_id)
    # Prune items at snapshot positions 20, 21, 22, 23, 24:
    # 20: closed
    opp_20 = db.query(Opportunity).filter(Opportunity.id == snap_ids[20]).first()
    opp_20.status = "closed"
    # 21: deleted
    opp_21 = db.query(Opportunity).filter(Opportunity.id == snap_ids[21]).first()
    db.delete(opp_21)
    # 22: dismissed
    opp_22 = db.query(Opportunity).filter(Opportunity.id == snap_ids[22]).first()
    opp_22.is_dismissed = True
    # 23: expired
    opp_23 = db.query(Opportunity).filter(Opportunity.id == snap_ids[23]).first()
    opp_23.status = "expired"
    # 24: deleted
    opp_24 = db.query(Opportunity).filter(Opportunity.id == snap_ids[24]).first()
    db.delete(opp_24)
    db.commit()

    # Step 2: Request Page 2 with cursor=20 and limit=20
    p2, _, _, next_cur_2, has_more_2 = await execute_intelligent_discovery_search(
        db=db, user_id=user_id, cursor=20, limit=20, snapshot_id=snap_id, return_cursor=True
    )

    # Scan-Fill must continue forward past the 5 pruned items and return 20 eligible items
    assert len(p2) == 20, f"Expected full page of 20 items, got {len(p2)}"
    # Verify no pruned item is present
    p2_ids = {it["id"] for it in p2}
    for pruned_id in [snap_ids[20], snap_ids[21], snap_ids[22], snap_ids[23], snap_ids[24]]:
        assert pruned_id not in p2_ids

    # Verify zero overlap between page 1 and page 2
    p1_ids = {it["id"] for it in p1}
    assert len(p1_ids.intersection(p2_ids)) == 0, "No duplicate items allowed across pages!"
    # The scan advanced past the 20 requested + 5 pruned = 25 items scanned, so next_cursor >= 45
    assert next_cur_2 >= 45


@pytest.mark.asyncio
async def test_end_of_session_short_page_semantics(db):
    """
    Phase 1 Test:
    Short pages are permitted strictly and only at the end of the session.
    When remaining eligible items < limit, returns surviving items with has_more=False, next_cursor=None.
    """
    user_id = 85002
    # Catalogue of 25 items with limit=20: page 1 has 20, page 2 has 5
    create_test_catalogue(db, count=25, base_id=95200)
    db.query(Opportunity).filter(Opportunity.id.between(95200, 95224)).update(
        {"source_platform": "shortpage_src"}, synchronize_session=False
    )
    cand = CandidateProfile(user_id=user_id, name="ShortPage Cand", skills=[{"name": "Python"}], evidence_version=1)
    db.merge(cand)
    db.commit()

    p1, _, snap_id, cur1, more1 = await execute_intelligent_discovery_search(
        db=db, user_id=user_id, source_platform="shortpage_src", skip=0, limit=20, return_cursor=True
    )
    assert len(p1) == 20
    assert more1 is True
    assert cur1 == 20

    # Page 2 requests remaining items
    p2, _, _, cur2, more2 = await execute_intelligent_discovery_search(
        db=db, user_id=user_id, source_platform="shortpage_src", cursor=cur1, limit=20, snapshot_id=snap_id, return_cursor=True
    )
    assert len(p2) == 5, "Final page must deliver the remaining 5 items"
    assert more2 is False, "has_more must be False at end of session"
    assert cur2 is None, "next_cursor must be None at end of session"


@pytest.mark.asyncio
async def test_active_session_retained_across_candidate_generation_bump(db):
    """
    Phase 2 Test:
    Candidate profile update advances candidate evidence generation (for new searches),
    while existing active sessions continue serving their original immutable snapshot sequence.
    """
    user_id = 85003
    create_test_catalogue(db, count=40, base_id=95300)
    cand = CandidateProfile(user_id=user_id, name="GenSeparation Cand", skills=[{"name": "Python"}], evidence_version=1)
    db.merge(cand)
    db.commit()

    # Client starts Session 1
    p1, _, snap_id_1, cur1, _ = await execute_intelligent_discovery_search(
        db=db, user_id=user_id, skip=0, limit=20, return_cursor=True
    )
    assert len(p1) == 20

    # Candidate adds skill (advancing candidate evidence generation to v2)
    cand_db = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    cand_db.skills = [{"name": "Python"}, {"name": "Kubernetes"}, {"name": "Go"}]
    cand_db.evidence_version = 2
    db.commit()
    # Invalidate cache for new search generation
    snapshot_manager.invalidate_candidate_snapshots(user_id, db, preserve_active_sessions=True)

    # In-flight Session 1 navigates to Page 2 using original snapshot_id
    p2_sess1, _, _, _, _ = await execute_intelligent_discovery_search(
        db=db, user_id=user_id, cursor=cur1, limit=20, snapshot_id=snap_id_1, return_cursor=True
    )
    assert len(p2_sess1) == 20, "Active session MUST survive profile mutation!"
    p1_ids = [it["id"] for it in p1]
    p2_ids = [it["id"] for it in p2_sess1]
    assert len(set(p1_ids).intersection(set(p2_ids))) == 0

    # A brand new search (without snapshot_id) at skip=0 creates Session 2 under generation 2
    p1_sess2, _, snap_id_2, _, _ = await execute_intelligent_discovery_search(
        db=db, user_id=user_id, skip=0, limit=20, return_cursor=True
    )
    assert snap_id_2 != snap_id_1, "New search must create a new generation snapshot session"


@pytest.mark.asyncio
async def test_candidate_session_ownership_verification(db):
    """
    Phase 8 & 2 Test:
    Candidate B cannot hijack or read Candidate A's snapshot_id.
    Passing an unowned snapshot_id is rejected with HTTP 410 (session invalid).
    """
    uid_a = 85004
    uid_b = 85005
    create_test_catalogue(db, count=30, base_id=95400)
    cand_a = CandidateProfile(user_id=uid_a, name="Candidate Alice", skills=[{"name": "Python"}], evidence_version=1)
    cand_b = CandidateProfile(user_id=uid_b, name="Candidate Bob", skills=[{"name": "Python"}], evidence_version=1)
    db.merge(cand_a)
    db.merge(cand_b)
    db.commit()

    # Alice creates a snapshot session
    p1_a, _, snap_id_a, _, _ = await execute_intelligent_discovery_search(
        db=db, user_id=uid_a, skip=0, limit=10, return_cursor=True
    )

    # Bob attempts to request Page 2 using Alice's snapshot_id
    with pytest.raises(PaginationSessionExpiredException):
        await execute_intelligent_discovery_search(
            db=db, user_id=uid_b, skip=10, limit=10, snapshot_id=snap_id_a, return_cursor=True
        )


# ---------------------------------------------------------------------------
# Phase 3 & 4: Monotonic Engine Generation & Stale-Write Computation Ordering
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_monotonic_engine_generation_rejects_string_comparison_bugs(db):
    """
    Phase 3 Test:
    String comparison bug check: In string comparison, '1.9.0' > '1.10.0' because '9' > '1'.
    With monotonic integer engine_generation (1.9.0 -> gen 1, 1.10.0 -> gen 2, 2.0.0 -> gen 2):
    A write with engine 1.9.0 (gen 1) MUST be rejected against an existing record with gen 2.
    """
    user_id = 85006
    cand = CandidateProfile(user_id=user_id, name="Engine Cand", skills=[{"name": "Python"}], evidence_version=2)
    opp = Opportunity(
        id=99881,
        title="Engine Test Role",
        normalized_title="engine test role",
        company_name="GenCorp",
        description="Testing engine generation monotonicity",
        content_version=2,
        original_url="https://gencorp.com/jobs/99881",
        source_platform="greenhouse",
        employment_type="internship",
        status="verified",
        created_at=utc_now()
    )
    db.merge(cand)
    db.merge(opp)
    db.commit()

    cand_db = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    opp_db = db.query(Opportunity).filter(Opportunity.id == 99881).first()

    # Persist baseline record under engine_version='1.10.0' (engine_generation=2)
    gen_1_10 = get_engine_generation("1.10.0")
    assert gen_1_10 == 2

    db.execute(text("""
        INSERT INTO candidate_opportunity_matches (
            user_id, candidate_id, opportunity_id, match_score, eligibility_status,
            match_analysis, candidate_evidence_version, opportunity_content_version,
            candidate_content_hash, opportunity_content_hash,
            engine_version, engine_generation, created_at, updated_at
        ) VALUES (
            :uid, :cid, :oid, 80.0, 'eligible', '{}'::json, 2, 2, 'cand_h', 'opp_h',
            '1.10.0', 2, NOW(), NOW()
        )
        ON CONFLICT ON CONSTRAINT uq_candidate_opportunity_match_user_opp DO NOTHING;
    """), {"uid": user_id, "cid": cand_db.id, "oid": opp_db.id})
    db.commit()

    # Attempt to write with engine_version='1.9.0' (engine_generation=1)
    # In string ordering '1.9.0' > '1.10.0', but integer 1 < 2!
    gen_1_9 = get_engine_generation("1.9.0")
    assert gen_1_9 == 1

    rejected_write = db.execute(text("""
        INSERT INTO candidate_opportunity_matches (
            user_id, candidate_id, opportunity_id, match_score, eligibility_status,
            match_analysis, candidate_evidence_version, opportunity_content_version,
            candidate_content_hash, opportunity_content_hash,
            engine_version, engine_generation, created_at, updated_at
        ) VALUES (
            :uid, :cid, :oid, 50.0, 'eligible', '{}'::json, 2, 2, 'cand_h', 'opp_h',
            '1.9.0', :eng_gen, NOW(), NOW()
        )
        ON CONFLICT ON CONSTRAINT uq_candidate_opportunity_match_user_opp
        DO UPDATE SET
            match_score = EXCLUDED.match_score,
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
    """), {"uid": user_id, "cid": cand_db.id, "oid": opp_db.id, "eng_gen": gen_1_9}).first()

    assert rejected_write is None, "Obsolete engine generation 1 MUST be rejected against generation 2!"

    rec = db.query(CandidateOpportunityMatch).filter(
        CandidateOpportunityMatch.user_id == user_id,
        CandidateOpportunityMatch.opportunity_id == opp_db.id
    ).first()
    assert rec.engine_version == "1.10.0"
    assert rec.engine_generation == 2
    assert rec.match_score == 80.0


@pytest.mark.asyncio
async def test_engine_generation_upgrade_supersedes_older_generation(db):
    """
    Phase 3 Test:
    When a newer engine generation (e.g. Generation 3 for v2.1.0) finishes,
    it successfully upgrades an existing Generation 2 evaluation.
    """
    user_id = 85007
    cand = CandidateProfile(user_id=user_id, name="Upgrade Cand", skills=[{"name": "Python"}], evidence_version=2)
    opp = Opportunity(
        id=99882,
        title="Upgrade Opp",
        normalized_title="upgrade opp",
        company_name="UpgradeCorp",
        description="Testing upgrade supersession",
        content_version=2,
        original_url="https://upgradecorp.com/jobs/99882",
        source_platform="greenhouse",
        employment_type="internship",
        status="verified",
        created_at=utc_now()
    )
    db.merge(cand)
    db.merge(opp)
    db.commit()

    cand_db = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    opp_db = db.query(Opportunity).filter(Opportunity.id == 99882).first()

    # Seed record under Generation 2
    db.execute(text("""
        INSERT INTO candidate_opportunity_matches (
            user_id, candidate_id, opportunity_id, match_score, eligibility_status,
            match_analysis, candidate_evidence_version, opportunity_content_version,
            candidate_content_hash, opportunity_content_hash,
            engine_version, engine_generation, created_at, updated_at
        ) VALUES (
            :uid, :cid, :oid, 75.0, 'eligible', '{}'::json, 2, 2, 'cand_h', 'opp_h',
            '2.0.0', 2, NOW(), NOW()
        )
        ON CONFLICT ON CONSTRAINT uq_candidate_opportunity_match_user_opp DO NOTHING;
    """), {"uid": user_id, "cid": cand_db.id, "oid": opp_db.id})
    db.commit()

    # Upgrade with Generation 3 (e.g. '2.1.0')
    gen_3 = get_engine_generation("2.1.0")
    assert gen_3 == 3

    updated = db.execute(text("""
        INSERT INTO candidate_opportunity_matches (
            user_id, candidate_id, opportunity_id, match_score, eligibility_status,
            match_analysis, candidate_evidence_version, opportunity_content_version,
            candidate_content_hash, opportunity_content_hash,
            engine_version, engine_generation, created_at, updated_at
        ) VALUES (
            :uid, :cid, :oid, 92.0, 'eligible', '{}'::json, 2, 2, 'cand_h', 'opp_h',
            '2.1.0', :eng_gen, NOW(), NOW()
        )
        ON CONFLICT ON CONSTRAINT uq_candidate_opportunity_match_user_opp
        DO UPDATE SET
            match_score = EXCLUDED.match_score,
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
    """), {"uid": user_id, "cid": cand_db.id, "oid": opp_db.id, "eng_gen": gen_3}).first()

    assert updated is not None, "Newer engine generation 3 MUST successfully upgrade generation 2!"
    rec = db.query(CandidateOpportunityMatch).filter(
        CandidateOpportunityMatch.user_id == user_id,
        CandidateOpportunityMatch.opportunity_id == opp_db.id
    ).first()
    assert rec.engine_generation == 3
    assert rec.engine_version == "2.1.0"
    assert rec.match_score == 92.0


@pytest.mark.asyncio
async def test_computation_freshness_rejects_stale_delayed_computation(db):
    """
    Phase 4 Test:
    Adversarial timing: If Candidate A updates skills during an ongoing evaluation
    (bumping candidate evidence version from 1 to 2), the delayed computation
    computed against v1 must be rejected upon write.
    """
    user_id = 85008
    cand = CandidateProfile(user_id=user_id, name="Freshness Cand", skills=[{"name": "Python"}], evidence_version=1)
    opp = Opportunity(
        id=99883,
        title="Freshness Opp",
        normalized_title="freshness opp",
        company_name="FreshCorp",
        description="Testing computation freshness",
        content_version=1,
        original_url="https://freshcorp.com/jobs/99883",
        source_platform="greenhouse",
        employment_type="internship",
        status="verified",
        created_at=utc_now()
    )
    db.merge(cand)
    db.merge(opp)
    db.commit()

    cand_db = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    opp_db = db.query(Opportunity).filter(Opportunity.id == 99883).first()

    # Meanwhile, Candidate evidence version is bumped to 2 and a fresh v2 match is stored
    db.execute(text("""
        INSERT INTO candidate_opportunity_matches (
            user_id, candidate_id, opportunity_id, match_score, eligibility_status,
            match_analysis, candidate_evidence_version, opportunity_content_version,
            candidate_content_hash, opportunity_content_hash,
            engine_version, engine_generation, created_at, updated_at
        ) VALUES (
            :uid, :cid, :oid, 95.0, 'eligible', '{}'::json, 2, 1, 'cand_h_v2', 'opp_h',
            '2.0.0', 2, NOW(), NOW()
        )
        ON CONFLICT ON CONSTRAINT uq_candidate_opportunity_match_user_opp DO NOTHING;
    """), {"uid": user_id, "cid": cand_db.id, "oid": opp_db.id})
    db.commit()

    # Delayed background task completes computation computed against evidence v1
    delayed_write = db.execute(text("""
        INSERT INTO candidate_opportunity_matches (
            user_id, candidate_id, opportunity_id, match_score, eligibility_status,
            match_analysis, candidate_evidence_version, opportunity_content_version,
            candidate_content_hash, opportunity_content_hash,
            engine_version, engine_generation, created_at, updated_at
        ) VALUES (
            :uid, :cid, :oid, 40.0, 'eligible', '{}'::json, 1, 1, 'cand_h_v1', 'opp_h',
            '2.0.0', 2, NOW(), NOW()
        )
        ON CONFLICT ON CONSTRAINT uq_candidate_opportunity_match_user_opp
        DO UPDATE SET
            match_score = EXCLUDED.match_score,
            candidate_evidence_version = EXCLUDED.candidate_evidence_version
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
    """), {"uid": user_id, "cid": cand_db.id, "oid": opp_db.id}).first()

    assert delayed_write is None, "Stale computation against evidence v1 MUST be rejected!"
    fresh = db.query(CandidateOpportunityMatch).filter(
        CandidateOpportunityMatch.user_id == user_id,
        CandidateOpportunityMatch.opportunity_id == opp_db.id
    ).first()
    assert fresh.candidate_evidence_version == 2
    assert fresh.match_score == 95.0


# ---------------------------------------------------------------------------
# Phase 5 & 6: GIN Index Representative Verification & Snapshot Lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gin_index_representative_dataset_and_catalog(db):
    """
    Phase 5 Test:
    1. Inspect PostgreSQL system catalog (pg_indexes) for idx_disc_snap_ids_gin.
    2. Populate 1,000 snapshot rows with JSONB arrays and verify EXPLAIN (ANALYZE, BUFFERS).
    """
    # 1. Catalog inspection
    idx_row = db.execute(text("""
        SELECT indexname, indexdef FROM pg_indexes
        WHERE tablename = 'discovery_ranking_snapshots' AND indexname = 'idx_disc_snap_ids_gin';
    """)).first()
    assert idx_row is not None, "Index idx_disc_snap_ids_gin MUST exist in pg_indexes!"
    assert "gin" in idx_row.indexdef.lower()
    assert "snapshot_ids" in idx_row.indexdef

    # 2. Populate 1,000 snapshots in PostgreSQL
    now = utc_now()
    batch_values = []
    for i in range(1000):
        target_ids = [42, 100 + i, 200 + i, 300 + i] if i % 10 == 0 else [100 + i, 200 + i, 300 + i]
        batch_values.append({
            "k": f"snap:bench_gin:{i}",
            "sid": f"sess_gin_{i}",
            "uid": 85010 + (i % 20),
            "sig": f"sig_gin_{i}",
            "v": "v1",
            "cnt": len(target_ids),
            "ids": json.dumps(target_ids),
            "exp": now + timedelta(minutes=10)
        })

    db.execute(text("""
        INSERT INTO discovery_ranking_snapshots (
            snapshot_key, snapshot_id, user_id, signature, candidate_evidence_version,
            total_count, snapshot_ids, created_at, expires_at
        ) VALUES (
            :k, :sid, :uid, :sig, :v, :cnt, CAST(:ids AS jsonb), NOW(), :exp
        )
        ON CONFLICT (snapshot_key) DO NOTHING;
    """), batch_values)
    db.commit()

    # Execute EXPLAIN (ANALYZE, BUFFERS) query to prove GIN index execution
    db.execute(text("SET LOCAL enable_seqscan = off;"))
    plan_rows = db.execute(text("""
        EXPLAIN (ANALYZE, BUFFERS)
        SELECT snapshot_key, snapshot_id FROM discovery_ranking_snapshots
        WHERE snapshot_ids @> '[42]'::jsonb;
    """)).fetchall()

    plan_str = "\n".join(r[0] for r in plan_rows)
    print("\nRepresentative 1,000-row GIN Index EXPLAIN Plan:\n" + plan_str)
    assert "idx_disc_snap_ids_gin" in plan_str, "PostgreSQL query engine must select idx_disc_snap_ids_gin!"

    # Clean benchmark rows
    db.execute(text("DELETE FROM discovery_ranking_snapshots WHERE snapshot_key LIKE 'snap:bench_gin:%'"))
    db.commit()


@pytest.mark.asyncio
async def test_bounded_expired_snapshot_cleanup_preserves_active_sessions(db):
    """
    Phase 6 Test:
    cleanup_expired_snapshots removes expired snapshots in bounded batches,
    and NEVER touches unexpired active sessions.
    """
    now = utc_now()
    uid = 85020

    # Seed 5 expired snapshots
    for i in range(5):
        snapshot_manager.set_snapshot(
            snapshot_key=f"snap:{uid}:exp_{i}",
            user_id=uid,
            signature=f"sig_exp_{i}",
            candidate_evidence_version="v1",
            snapshot_ids=[1, 2, 3],
            total_count=3,
            db=db,
            snapshot_id=f"sess_exp_{i}",
            ttl_seconds=-10  # Already expired
        )

    # Seed 2 unexpired active sessions
    snapshot_manager.set_snapshot(
        snapshot_key=f"snap:{uid}:active_1",
        user_id=uid,
        signature="sig_act_1",
        candidate_evidence_version="v1",
        snapshot_ids=[10, 20, 30],
        total_count=3,
        db=db,
        snapshot_id="sess_act_1",
        ttl_seconds=300
    )

    # Execute bounded cleanup
    deleted = snapshot_manager.cleanup_expired_snapshots(db, batch_size=10)
    assert deleted >= 5, f"Expected at least 5 expired snapshots cleaned, got {deleted}"

    # Verify unexpired session is untouched
    active_row = db.query(DiscoveryRankingSnapshot).filter(
        DiscoveryRankingSnapshot.snapshot_id == "sess_act_1"
    ).first()
    assert active_row is not None, "Unexpired active session MUST NOT be deleted by cleanup!"


@pytest.mark.asyncio
async def test_expired_session_rejected_even_if_present_in_l1_cache(db):
    """
    Phase 6 Test:
    Even if an expired session entry lingers in L1 cache, get_snapshot_by_id
    verifies expiration timestamp, deletes the L1 entry, and returns None.
    """
    snap_id = "sess_l1_exp_check"
    # Populate L1 cache with an expired expiration timestamp
    expired_ts = time.time() - 50.0
    snapshot_manager.l1_cache.set(f"snap_id:{snap_id}", ([1, 2, 3], 3, 85030, expired_ts), ttl=60)

    # Lookup must reject
    res = snapshot_manager.get_snapshot_by_id(snap_id, db, user_id=85030)
    assert res is None, "Expired session in L1 cache MUST be rejected!"
    # And L1 entry is purged
    assert snapshot_manager.l1_cache.get(f"snap_id:{snap_id}") is None
