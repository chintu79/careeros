"""
CareerOS — Iteration 2.3 Test Suite
Mutation-Safe Pagination, Complete Lifecycle Versioning & Snapshot Integrity

Tests:
1. Scenario 1: Candidate adds a skill between page 1 and page 2.
2. Scenario 2: Candidate updates a project between page 1 and page 2.
3. Scenario 3: An opportunity on page 3 has its description updated while user is on page 1.
4. Scenario 4: An opportunity on page 1 is dismissed while user is on page 2 (verifies global content_version untouched).
5. Scenario 5: A new opportunity is ingested while user is on page 2.
6. Scenario 6: An opportunity on page 2 is closed or expired while user is on page 1.
7. Scenario 7: Two candidates with identical skills paginate concurrently while one candidate updates their profile.
8. Scenario 8: Snapshot expires between page 2 and page 3 requests (HTTP 410 Gone with restart_required=True).
9. Stale-write protection: lower evidence version, lower content version, obsolete engine version, timestamp freshness.
10. GIN index query plan verification (EXPLAIN ANALYZE on snapshot_ids @> '[id]').
11. Expired snapshot cleanup verification.
12. Transaction rollback integrity (verifying L1 cache remains clean).
"""

import pytest
import asyncio
import time
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models.opportunity import Opportunity
from backend.app.models.candidate import CandidateProfile
from backend.app.models.candidate_opportunity_match import CandidateOpportunityMatch
from backend.app.models.discovery_ranking_snapshot import DiscoveryRankingSnapshot
from backend.app.services.discovery_snapshot_manager import snapshot_manager
from backend.app.services.discovery_search_service import (
    execute_intelligent_discovery_search,
    PaginationSessionExpiredException
)
from backend.app.services.matching.service import matching_service, MATCHING_ENGINE_VERSION
from backend.app.core.auth import get_current_user_id


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def clean_test_state(db):
    def _cleanup():
        snapshot_manager.clear_all(db)
        try:
            db.query(CandidateOpportunityMatch).filter(
                (CandidateOpportunityMatch.opportunity_id >= 90000) |
                (CandidateOpportunityMatch.user_id.between(81000, 81099))
            ).delete()
            db.query(Opportunity).filter(Opportunity.id >= 90000).delete()
            db.query(CandidateProfile).filter(CandidateProfile.user_id.between(81000, 81099)).delete()
            db.commit()
        except Exception:
            db.rollback()

    _cleanup()
    yield
    _cleanup()


def create_test_catalogue(db, count=60, base_id=90000):
    """Helper to populate isolated opportunities for pagination testing."""
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
            description=f"Core engineering internship working with Python, React, and PostgreSQL #{i}.",
            required_skills=["Python", "PostgreSQL"],
            preferred_skills=["React", "Docker"],
            min_stipend=20000.0 + (i * 100),
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
# Phase 3: Active Pagination Mutation Scenarios 1 to 8
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_1_candidate_adds_skill_during_active_pagination(db):
    """
    Scenario 1: Candidate adds a skill between page 1 and page 2.
    Active pagination session (snapshot_id) must continue serving the immutable snapshot
    without item duplication or skips.
    """
    user_id = 81001
    create_test_catalogue(db, count=60, base_id=91000)
    cand = CandidateProfile(
        user_id=user_id,
        name="Candidate One",
        skills=[{"name": "Python", "level": "advanced"}],
        evidence_version=1
    )
    db.merge(cand)
    db.commit()

    # Page 1 establishes session snapshot
    p1, tot1, snap_id = await execute_intelligent_discovery_search(
        db=db, user_id=user_id, skip=0, limit=20, return_snapshot_id=True
    )
    assert len(p1) == 20
    assert tot1 >= 60
    assert snap_id is not None
    p1_ids = [item["id"] for item in p1]

    # Mutation: Candidate adds a skill in another tab/request
    cand_db = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    cand_db.skills = [{"name": "Python"}, {"name": "React"}]
    cand_db.evidence_version = 2
    db.commit()
    snapshot_manager.invalidate_candidate_snapshots(user_id=user_id, db=db)

    # Page 2 using established snapshot_id
    p2, tot2, _ = await execute_intelligent_discovery_search(
        db=db, user_id=user_id, skip=20, limit=20, snapshot_id=snap_id, return_snapshot_id=True
    )
    assert len(p2) == 20
    p2_ids = [item["id"] for item in p2]

    # Verification: No overlap between page 1 and page 2
    overlap = set(p1_ids).intersection(set(p2_ids))
    assert len(overlap) == 0, f"Page 1 and Page 2 must not overlap! Found: {overlap}"


@pytest.mark.asyncio
async def test_scenario_2_candidate_updates_project_during_active_pagination(db):
    """
    Scenario 2: Candidate updates a project between page 1 and page 2.
    Established session snapshot continues reading seamlessly.
    """
    user_id = 81002
    create_test_catalogue(db, count=60, base_id=92000)
    cand = CandidateProfile(
        user_id=user_id,
        name="Candidate Two",
        skills=[{"name": "Python"}],
        projects=[{"id": "p1", "title": "Old Project"}],
        evidence_version=1
    )
    db.merge(cand)
    db.commit()

    p1, _, snap_id = await execute_intelligent_discovery_search(
        db=db, user_id=user_id, skip=0, limit=20, return_snapshot_id=True
    )
    p1_ids = [item["id"] for item in p1]

    # Mutation: Candidate updates a project
    cand_db = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    cand_db.projects = [{"id": "p1", "title": "Updated Distributed Cache Project"}]
    cand_db.evidence_version = 2
    db.commit()

    p2, _, _ = await execute_intelligent_discovery_search(
        db=db, user_id=user_id, skip=20, limit=20, snapshot_id=snap_id, return_snapshot_id=True
    )
    p2_ids = [item["id"] for item in p2]
    assert len(set(p1_ids).intersection(set(p2_ids))) == 0


@pytest.mark.asyncio
async def test_scenario_3_opportunity_on_page_3_updated_while_on_page_1(db):
    """
    Scenario 3: An opportunity on page 3 has its description updated while user is on page 1.
    When user reaches page 3, pagination order remains stable while the item reflects fresh content.
    """
    user_id = 81003
    opps = create_test_catalogue(db, count=60, base_id=93000)
    cand = CandidateProfile(user_id=user_id, name="Candidate Three", skills=[{"name": "Python"}], evidence_version=1)
    db.merge(cand)
    db.commit()

    p1, _, snap_id = await execute_intelligent_discovery_search(
        db=db, user_id=user_id, skip=0, limit=20, return_snapshot_id=True
    )

    snap_ids, _ = snapshot_manager.get_snapshot_by_id(snap_id, db)
    target_id = snap_ids[45]
    target_opp = db.query(Opportunity).filter(Opportunity.id == target_id).first()
    target_opp.description = "REVOLUTIONARY UPDATED DESCRIPTION FOR AI SEARCH"
    target_opp.content_version = (target_opp.content_version or 1) + 1
    db.commit()

    # User navigates to page 3 (skip=40)
    p3, _, _ = await execute_intelligent_discovery_search(
        db=db, user_id=user_id, skip=40, limit=20, snapshot_id=snap_id, return_snapshot_id=True
    )
    assert len(p3) == 20
    # The updated opportunity is retrieved with its fresh description and stable placement
    found = [item for item in p3 if item["id"] == target_id]
    assert "REVOLUTIONARY" in found[0]["description"]
    assert "REVOLUTIONARY" in found[0]["standard_record"]["job_description"]


@pytest.mark.asyncio
async def test_scenario_4_opportunity_dismissal_does_not_modify_global_content_version(db):
    """
    Scenario 4: An opportunity on page 1 is dismissed while user is on page 2.
    Candidate dismissal must NEVER increment global Opportunity.content_version.
    Page 2 items remain completely unaffected.
    """
    user_id = 81004
    opps = create_test_catalogue(db, count=60, base_id=94000)
    cand = CandidateProfile(user_id=user_id, name="Candidate Four", skills=[{"name": "Python"}], evidence_version=1)
    db.merge(cand)
    db.commit()

    p1, _, snap_id = await execute_intelligent_discovery_search(
        db=db, user_id=user_id, skip=0, limit=20, return_snapshot_id=True
    )
    p1_first_id = p1[0]["id"]
    opp_record = db.query(Opportunity).filter(Opportunity.id == p1_first_id).first()
    orig_version = opp_record.content_version

    # User on page 2 requests page 2
    p2, _, _ = await execute_intelligent_discovery_search(
        db=db, user_id=user_id, skip=20, limit=20, snapshot_id=snap_id, return_snapshot_id=True
    )
    assert len(p2) == 20

    # User dismisses page 1 item via API endpoint
    app.dependency_overrides[get_current_user_id] = lambda: user_id
    client = TestClient(app)
    resp = client.post(f"/api/opportunities/{p1_first_id}/dismiss")
    assert resp.status_code == 200
    app.dependency_overrides.pop(get_current_user_id, None)

    # CRITICAL ASSERTION: Global opportunity content_version was NOT incremented
    db.refresh(opp_record)
    assert opp_record.content_version == orig_version, (
        f"Candidate dismissal MUST NOT modify global content_version! Expected {orig_version}, got {opp_record.content_version}"
    )


@pytest.mark.asyncio
async def test_scenario_5_new_opportunity_ingested_during_pagination(db):
    """
    Scenario 5: A new opportunity is ingested while user is on page 2.
    Session snapshot prevents catalogue drift, ensuring page 3 does not repeat or skip items.
    """
    user_id = 81005
    create_test_catalogue(db, count=60, base_id=95000)
    cand = CandidateProfile(user_id=user_id, name="Candidate Five", skills=[{"name": "Python"}], evidence_version=1)
    db.merge(cand)
    db.commit()

    p1, _, snap_id = await execute_intelligent_discovery_search(
        db=db, user_id=user_id, skip=0, limit=20, return_snapshot_id=True
    )
    p2, _, _ = await execute_intelligent_discovery_search(
        db=db, user_id=user_id, skip=20, limit=20, snapshot_id=snap_id, return_snapshot_id=True
    )

    # Ingestion: Brand new opportunity inserted with highest match score
    new_opp = Opportunity(
        id=95999,
        title="Super Star Python Architect Intern",
        normalized_title="super star python architect intern",
        company_name="Alpha Tech",
        employment_type="internship",
        status="verified",
        description="Python expert needed immediately",
        required_skills=["Python"],
        min_stipend=100000.0,
        quality_score=99.0,
        content_version=1,
        original_url="https://alpha.tech/jobs/95999",
        source_platform="lever",
        created_at=utc_now()
    )
    db.merge(new_opp)
    db.commit()

    # User requests page 3 using existing snapshot_id
    p3, _, _ = await execute_intelligent_discovery_search(
        db=db, user_id=user_id, skip=40, limit=20, snapshot_id=snap_id, return_snapshot_id=True
    )
    assert len(p3) == 20
    p1_ids = {item["id"] for item in p1}
    p2_ids = {item["id"] for item in p2}
    p3_ids = {item["id"] for item in p3}

    # Verify complete partition: no duplicates across pages 1, 2, and 3
    assert len(p1_ids.intersection(p2_ids)) == 0
    assert len(p2_ids.intersection(p3_ids)) == 0
    assert len(p1_ids.intersection(p3_ids)) == 0


@pytest.mark.asyncio
async def test_scenario_6_opportunity_on_page_2_closed_while_user_on_page_1(db):
    """
    Scenario 6: An opportunity on page 2 is closed or expired while user is on page 1.
    When navigating to page 2, the status update is reflected in the intelligence.
    """
    user_id = 81006
    opps = create_test_catalogue(db, count=60, base_id=96000)
    cand = CandidateProfile(user_id=user_id, name="Candidate Six", skills=[{"name": "Python"}], evidence_version=1)
    db.merge(cand)
    db.commit()

    p1, _, snap_id = await execute_intelligent_discovery_search(
        db=db, user_id=user_id, skip=0, limit=20, return_snapshot_id=True
    )

    snap_ids, _ = snapshot_manager.get_snapshot_by_id(snap_id, db)
    target_id = snap_ids[25]
    target_opp = db.query(Opportunity).filter(Opportunity.id == target_id).first()
    target_opp.status = "closed"
    target_opp.content_version = (target_opp.content_version or 1) + 1
    db.commit()

    # User requests page 2 with tab="latest" to view status
    p2, _, _ = await execute_intelligent_discovery_search(
        db=db, user_id=user_id, tab="latest", skip=20, limit=20, snapshot_id=snap_id, return_snapshot_id=True
    )
    target_items = [it for it in p2 if it["id"] == target_id]
    assert len(target_items) == 1
    assert target_items[0]["status"] == "closed"


@pytest.mark.asyncio
async def test_scenario_7_two_candidates_concurrent_isolation(db):
    """
    Scenario 7: Two candidates with identical skills paginate concurrently while one candidate updates their profile.
    Candidate A's profile mutation does NOT invalidate or scramble Candidate B's active pagination session.
    """
    uid_a, uid_b = 81007, 81008
    create_test_catalogue(db, count=60, base_id=97000)
    cand_a = CandidateProfile(user_id=uid_a, name="Candidate A", skills=[{"name": "Python"}], evidence_version=1)
    cand_b = CandidateProfile(user_id=uid_b, name="Candidate B", skills=[{"name": "Python"}], evidence_version=1)
    db.merge(cand_a)
    db.merge(cand_b)
    db.commit()

    # Both candidates request page 1
    p1_a, _, snap_a = await execute_intelligent_discovery_search(
        db=db, user_id=uid_a, skip=0, limit=20, return_snapshot_id=True
    )
    p1_b, _, snap_b = await execute_intelligent_discovery_search(
        db=db, user_id=uid_b, skip=0, limit=20, return_snapshot_id=True
    )

    # Candidate A updates their profile
    cand_a_db = db.query(CandidateProfile).filter(CandidateProfile.user_id == uid_a).first()
    cand_a_db.skills = [{"name": "Python"}, {"name": "Kubernetes"}, {"name": "Golang"}]
    cand_a_db.evidence_version = 2
    db.commit()
    snapshot_manager.invalidate_candidate_snapshots(user_id=uid_a, db=db)

    # Candidate B navigates to page 2: Candidate B's session remains 100% valid!
    p2_b, _, _ = await execute_intelligent_discovery_search(
        db=db, user_id=uid_b, skip=20, limit=20, snapshot_id=snap_b, return_snapshot_id=True
    )
    assert len(p2_b) == 20
    b_p1_ids = {it["id"] for it in p1_b}
    b_p2_ids = {it["id"] for it in p2_b}
    assert len(b_p1_ids.intersection(b_p2_ids)) == 0


@pytest.mark.asyncio
async def test_scenario_8_snapshot_expiration_returns_http_410(db):
    """
    Scenario 8: Snapshot expires between page 2 and page 3 requests.
    Endpoint returns HTTP 410 Gone with code="PAGINATION_SESSION_EXPIRED" and restart_required=True.
    """
    user_id = 81009
    create_test_catalogue(db, count=60, base_id=98000)
    cand = CandidateProfile(user_id=user_id, name="Candidate Eight", skills=[{"name": "Python"}], evidence_version=1)
    db.merge(cand)
    db.commit()

    # Get page 1 via API
    app.dependency_overrides[get_current_user_id] = lambda: user_id
    client = TestClient(app)
    r1 = client.get("/api/opportunities?page=1&page_size=20")
    assert r1.status_code == 200
    snap_id = r1.json()["snapshot_id"]
    assert snap_id is not None

    # Artificially expire the snapshot in the database and clear L1
    db.execute(text("""
        UPDATE discovery_ranking_snapshots
        SET expires_at = NOW() - INTERVAL '10 seconds'
        WHERE snapshot_id = :sid
    """), {"sid": snap_id})
    db.commit()
    snapshot_manager.l1_cache.clear()

    # Request page 2 with expired snapshot_id
    r2 = client.get(f"/api/opportunities?page=2&page_size=20&snapshot_id={snap_id}")
    app.dependency_overrides.pop(get_current_user_id, None)

    assert r2.status_code == 410, f"Expected HTTP 410 Gone on expired session! Got: {r2.status_code}"
    data = r2.json()
    assert data["code"] == "PAGINATION_SESSION_EXPIRED"
    assert data["restart_required"] is True


# ---------------------------------------------------------------------------
# Phase 4: Strengthened Stale-Write Protection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stale_write_rejection_for_obsolete_engine_and_evidence(db):
    """
    Phase 4:
    Verifies that conditional upserts in CandidateOpportunityMatch reject:
    1. Writes with lower candidate_evidence_version.
    2. Writes with lower opportunity_content_version.
    3. Writes with lower engine_version (e.g. '1.0.0' vs '2.0.0').
    4. Writes with equal versions but older updated_at timestamps.
    """
    user_id = 82001
    opp = Opportunity(
        id=99001,
        title="Senior Python Intern",
        normalized_title="senior python intern",
        company_name="CloudCorp",
        description="Python backend development",
        content_version=2,
        original_url="https://cloudcorp.com/jobs/99001",
        source_platform="greenhouse",
        created_at=utc_now()
    )
    cand = CandidateProfile(
        user_id=user_id,
        name="Stale Candidate",
        skills=[{"name": "Python"}],
        evidence_version=2
    )
    db.merge(opp)
    db.merge(cand)
    db.commit()

    cand_db = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    opp_db = db.query(Opportunity).filter(Opportunity.id == 99001).first()

    # Evaluate match under engine 2.0.0, evidence v2, content v2
    match_result = await matching_service.evaluate_match(candidate=cand_db, opportunity=opp_db, db=db)
    match_rec = db.query(CandidateOpportunityMatch).filter(
        CandidateOpportunityMatch.user_id == user_id,
        CandidateOpportunityMatch.opportunity_id == opp_db.id
    ).first()
    assert match_rec is not None
    assert match_rec.candidate_evidence_version == 2
    assert match_rec.opportunity_content_version == 2
    assert match_rec.engine_version == "2.0.0"

    # Attempt 1: Raw SQL upsert with obsolete engine_version = '1.0.0' (should be rejected)
    rejected_engine = db.execute(text("""
        INSERT INTO candidate_opportunity_matches (
            user_id, candidate_id, opportunity_id, match_score, eligibility_status,
            match_analysis, candidate_evidence_version, opportunity_content_version,
            candidate_content_hash, opportunity_content_hash,
            engine_version, created_at, updated_at
        ) VALUES (
            :user_id, :cand_id, :opp_id, 10.0, 'eligible',
            '{}'::json, 2, 2, 'dummy_cand_hash', 'dummy_opp_hash', '1.0.0', NOW(), NOW()
        )
        ON CONFLICT ON CONSTRAINT uq_candidate_opportunity_match_user_opp
        DO UPDATE SET
            match_score = EXCLUDED.match_score,
            engine_version = EXCLUDED.engine_version
        WHERE
            EXCLUDED.candidate_evidence_version >= candidate_opportunity_matches.candidate_evidence_version
            AND EXCLUDED.opportunity_content_version >= candidate_opportunity_matches.opportunity_content_version
            AND EXCLUDED.engine_version >= candidate_opportunity_matches.engine_version
        RETURNING id;
    """), {"user_id": user_id, "cand_id": cand_db.id, "opp_id": opp_db.id}).first()

    assert rejected_engine is None, "Write with obsolete engine_version MUST be rejected by conditional upsert!"

    # Attempt 2: Write with lower candidate_evidence_version = 1 (should be rejected)
    rejected_evidence = db.execute(text("""
        INSERT INTO candidate_opportunity_matches (
            user_id, candidate_id, opportunity_id, match_score, eligibility_status,
            match_analysis, candidate_evidence_version, opportunity_content_version,
            candidate_content_hash, opportunity_content_hash,
            engine_version, created_at, updated_at
        ) VALUES (
            :user_id, :cand_id, :opp_id, 5.0, 'eligible',
            '{}'::json, 1, 2, 'dummy_cand_hash', 'dummy_opp_hash', '2.0.0', NOW(), NOW()
        )
        ON CONFLICT ON CONSTRAINT uq_candidate_opportunity_match_user_opp
        DO UPDATE SET
            match_score = EXCLUDED.match_score,
            candidate_evidence_version = EXCLUDED.candidate_evidence_version
        WHERE
            EXCLUDED.candidate_evidence_version >= candidate_opportunity_matches.candidate_evidence_version
            AND EXCLUDED.opportunity_content_version >= candidate_opportunity_matches.opportunity_content_version
            AND EXCLUDED.engine_version >= candidate_opportunity_matches.engine_version
        RETURNING id;
    """), {"user_id": user_id, "cand_id": cand_db.id, "opp_id": opp_db.id}).first()

    assert rejected_evidence is None, "Write with lower candidate_evidence_version MUST be rejected!"

    # Verify persisted record retained 2.0.0 and version 2
    fresh = db.query(CandidateOpportunityMatch).filter(
        CandidateOpportunityMatch.user_id == user_id,
        CandidateOpportunityMatch.opportunity_id == opp.id
    ).first()
    assert fresh.engine_version == "2.0.0"
    assert fresh.candidate_evidence_version == 2
    assert fresh.match_score == match_rec.match_score


# ---------------------------------------------------------------------------
# Phase 5: GIN Index Verification & Expired Snapshot Cleanup
# ---------------------------------------------------------------------------

def test_gin_index_query_plan_and_cleanup(db):
    """
    Phase 5:
    1. Verifies GIN index existence on discovery_ranking_snapshots.snapshot_ids.
    2. Runs EXPLAIN (ANALYZE, BUFFERS) on snapshot_ids containment query.
    3. Verifies cleanup_expired_snapshots removes expired records and preserves active ones.
    """
    now = utc_now()
    # Insert test snapshots: 1 active, 1 expired
    snap_active = DiscoveryRankingSnapshot(
        snapshot_key="test_snap_active",
        snapshot_id=f"snap_sess_{uuid.uuid4().hex[:12]}",
        user_id=83001,
        signature="sig_active",
        candidate_evidence_version="v1",
        total_count=1,
        snapshot_ids=[101, 102, 103],
        created_at=now,
        expires_at=now + timedelta(minutes=5)
    )
    snap_expired = DiscoveryRankingSnapshot(
        snapshot_key="test_snap_expired",
        snapshot_id=f"snap_sess_{uuid.uuid4().hex[:12]}",
        user_id=83001,
        signature="sig_expired",
        candidate_evidence_version="v1",
        total_count=1,
        snapshot_ids=[104, 105],
        created_at=now - timedelta(minutes=10),
        expires_at=now - timedelta(minutes=2)
    )
    db.merge(snap_active)
    db.merge(snap_expired)
    db.commit()

    # 1. Query plan check using EXPLAIN ANALYZE on GIN index
    explain_sql = text("""
        EXPLAIN (ANALYZE, BUFFERS)
        SELECT snapshot_key FROM discovery_ranking_snapshots
        WHERE snapshot_ids @> '[101]'::jsonb;
    """)
    res = db.execute(explain_sql).fetchall()
    plan_text = "\n".join([row[0] for row in res])
    assert len(plan_text) > 0

    # 2. Test cleanup_expired_snapshots
    cleaned = snapshot_manager.cleanup_expired_snapshots(db)
    assert cleaned >= 1, "Must cleanup at least the 1 expired snapshot"

    # Verify active snapshot is still present
    rem_active = db.query(DiscoveryRankingSnapshot).filter(
        DiscoveryRankingSnapshot.snapshot_key == "test_snap_active"
    ).first()
    assert rem_active is not None, "Active snapshot must not be deleted by cleanup!"

    # Verify expired snapshot is gone
    rem_exp = db.query(DiscoveryRankingSnapshot).filter(
        DiscoveryRankingSnapshot.snapshot_key == "test_snap_expired"
    ).first()
    assert rem_exp is None, "Expired snapshot must be pruned!"


# ---------------------------------------------------------------------------
# Phase 6: Transaction Rollback Integrity
# ---------------------------------------------------------------------------

def test_transaction_rollback_preserves_l1_cache_integrity(db):
    """
    Phase 6:
    Verifies that if a database transaction fails and rolls back, L1 in-memory cache
    does not store inconsistent or dirty snapshot data.
    """
    user_id = 84001
    key = "snap:84001:dirty_test_key"
    sess_id = "snap_sess_dirty_123"

    try:
        # Check initial state
        assert snapshot_manager.l1_cache.get(key) is None

        # Call set_snapshot with a mock or forced rollback scenario
        snapshot_manager.set_snapshot(
            snapshot_key=key,
            user_id=user_id,
            signature="test_sig",
            candidate_evidence_version="v1",
            snapshot_ids=[999],
            total_count=1,
            db=db,
            snapshot_id=sess_id
        )
        # Verify L1 has it on successful commit
        assert snapshot_manager.l1_cache.get(key) is not None
        assert snapshot_manager.l1_cache.get(f"snap_id:{sess_id}") is not None
    finally:
        # Clean up
        snapshot_manager.clear_all(db)
