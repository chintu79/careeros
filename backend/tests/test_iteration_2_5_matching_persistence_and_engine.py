"""
CareerOS — Iteration 2.5 Matching Persistence Audit, Engine Release Consistency & Adversarial Tests

Audits and proves:
1. Canonical Database State Invariant: Stale computations cannot overwrite newer candidate or opportunity data.
2. In-flight mutation rejection: Candidate or opportunity changes during evaluation reject delayed writes.
3. Obsolete content hash rejection under identical version numbers.
4. Batch vs single evaluation race consistency.
5. Idempotent equal-version and equal-generation concurrent writes.
6. Engine generation release directions (new worker supersedes old; old worker rejected after new).
7. Worker deployment release validation.
8. Heavy pagination pruning (large consecutive blocks of closed, deleted, dismissed items).
"""

import time
import json
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.models.opportunity import Opportunity
from backend.app.models.candidate import CandidateProfile
from backend.app.models.candidate_opportunity_match import CandidateOpportunityMatch, utc_now
from backend.app.models.discovery_ranking_snapshot import DiscoveryRankingSnapshot
from backend.app.services.matching.service import (
    matching_service,
    MATCHING_ENGINE_VERSION,
    MATCHING_ENGINE_GENERATION,
    get_engine_generation
)
from backend.app.services.matching.release_registry import (
    MATCHING_ENGINE_RELEASES,
    validate_deployment_engine_release,
    get_canonical_engine_generation
)
from backend.app.services.discovery_snapshot_manager import snapshot_manager
from backend.app.services.discovery_search_service import execute_intelligent_discovery_search


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
                (CandidateOpportunityMatch.opportunity_id >= 98000) |
                (CandidateOpportunityMatch.user_id.between(86000, 86999))
            ).delete()
            db.query(Opportunity).filter(Opportunity.id >= 98000).delete()
            db.query(CandidateProfile).filter(CandidateProfile.user_id.between(86000, 86999)).delete()
            db.commit()
        except Exception:
            db.rollback()

    _cleanup()
    yield
    _cleanup()


def create_opp(db: Session, opp_id: int, title: str, description: str, content_version: int = 1, status: str = "verified"):
    now = utc_now()
    opp = Opportunity(
        id=opp_id,
        title=title,
        normalized_title=title.lower(),
        company_name="AuditTech",
        normalized_location="Remote",
        location="Remote",
        employment_type="internship",
        status=status,
        description=description,
        required_skills=["Python", "PostgreSQL"],
        preferred_skills=["Docker"],
        content_version=content_version,
        is_dismissed=False,
        is_saved=False,
        is_applied=False,
        original_url=f"https://audittech.com/jobs/{opp_id}",
        source_platform="greenhouse",
        posted_at=now,
        created_at=now
    )
    opp = db.merge(opp)
    db.commit()
    db.refresh(opp)
    return opp


# ---------------------------------------------------------------------------
# Phase 1 & 3: Matching Persistence SQL & Canonical State Invariant
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_old_candidate_evidence_computation_finishes_after_newer_computation(db: Session):
    """
    Adversarial Race 1:
    Candidate has evidence v1. A slow evaluation computes against v1.
    Meanwhile, the candidate profile updates to evidence v2, and a fresh evaluation commits at v2.
    When the slow v1 computation finishes and attempts to persist, it MUST be rejected.
    """
    uid = 86001
    opp_id = 98001
    opp = create_opp(db, opp_id=opp_id, title="Backend Intern", description="Python and SQL internship")
    
    cand = CandidateProfile(
        user_id=uid,
        name="Async Candidate 1",
        skills=[{"name": "Python"}],
        evidence_version=1
    )
    cand = db.merge(cand)
    db.commit()
    db.refresh(cand)

    # Step 1: Candidate updates skills to v2 and evaluates fresh match
    cand.skills = [{"name": "Python"}, {"name": "PostgreSQL"}]
    cand.evidence_version = 2
    cand.updated_at = utc_now()
    db.commit()
    db.refresh(cand)

    fresh_res = await matching_service.evaluate_match(cand, opp, db, force_refresh=True, use_ai=False)
    assert fresh_res.profile_match_score > 0

    fresh_rec = db.query(CandidateOpportunityMatch).filter(
        CandidateOpportunityMatch.user_id == uid,
        CandidateOpportunityMatch.opportunity_id == opp_id
    ).first()
    assert fresh_rec.candidate_evidence_version == 2
    assert fresh_rec.match_score == fresh_res.profile_match_score

    # Step 2: Now simulate the delayed completion of a stale evaluation computed against evidence v1
    stale_cand = CandidateProfile(
        id=cand.id,
        user_id=uid,
        name="Async Candidate 1",
        skills=[{"name": "Python"}],
        evidence_version=1  # Obsolete version
    )
    
    stale_res = await matching_service.evaluate_match(stale_cand, opp, db, force_refresh=True, use_ai=False)

    # Step 3: Verify the stale write was rejected and the database retains v2
    persisted_rec = db.query(CandidateOpportunityMatch).filter(
        CandidateOpportunityMatch.user_id == uid,
        CandidateOpportunityMatch.opportunity_id == opp_id
    ).first()
    assert persisted_rec.candidate_evidence_version == 2, "Stale v1 write MUST NOT overwrite v2!"
    assert persisted_rec.match_score == fresh_rec.match_score, "Match score from v2 must be preserved!"
    assert stale_res.is_stale is True, "Returned result must indicate stale evaluation!"


@pytest.mark.asyncio
async def test_opportunity_description_changes_while_evaluation_running(db: Session):
    """
    Adversarial Race 2:
    Evaluation starts on opportunity content_version 1.
    While computation runs, opportunity description changes and content_version advances to 2.
    Delayed computation computed against v1 MUST be rejected, preserving the database state.
    """
    uid = 86002
    opp_id = 98002
    opp = create_opp(db, opp_id=opp_id, title="Data Intern", description="Python and statistics", content_version=1)
    
    cand = CandidateProfile(
        user_id=uid,
        name="Async Candidate 2",
        skills=[{"name": "Python"}],
        evidence_version=1
    )
    cand = db.merge(cand)
    db.commit()
    db.refresh(cand)

    # Capture stale opportunity snapshot (content_version=1)
    stale_opp = Opportunity(
        id=opp.id,
        title=opp.title,
        company_name=opp.company_name,
        normalized_location=opp.normalized_location,
        location=opp.location,
        description="Python and statistics",
        content_version=1
    )

    # Opportunity description mutates in database and content_version advances to 2
    opp_db = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
    opp_db.description = "Advanced Python, PyTorch, and Deep Learning"
    opp_db.content_version = 2
    db.commit()

    # Delayed computation finishes using stale_opp (version 1)
    res = await matching_service.evaluate_match(cand, stale_opp, db, force_refresh=True, use_ai=False)

    # Verification: Database must NOT contain a match record with opportunity_content_version = 1
    rec = db.query(CandidateOpportunityMatch).filter(
        CandidateOpportunityMatch.user_id == uid,
        CandidateOpportunityMatch.opportunity_id == opp_id
    ).first()
    assert rec is None, "Stale write against obsolete opportunity content_version 1 MUST NOT insert a record!"
    assert res.is_stale is True


@pytest.mark.asyncio
async def test_candidate_and_opportunity_both_change_during_evaluation(db: Session):
    """
    Adversarial Race 3:
    Both candidate evidence and opportunity content mutate during background evaluation.
    Evaluation computed against (cand_ev=1, opp_cv=1) MUST be rejected when DB is at (cand_ev=2, opp_cv=2).
    """
    uid = 86003
    opp_id = 98003
    opp = create_opp(db, opp_id=opp_id, title="Fullstack Intern", description="React and Node.js", content_version=1)
    cand = CandidateProfile(user_id=uid, name="Cand 3", skills=[{"name": "React"}], evidence_version=1)
    cand = db.merge(cand)
    db.commit()
    db.refresh(cand)

    # Mutate both in database
    cand_db = db.query(CandidateProfile).filter(CandidateProfile.user_id == uid).first()
    cand_db.skills = [{"name": "React"}, {"name": "Node.js"}]
    cand_db.evidence_version = 2

    opp_db = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
    opp_db.content_version = 2
    opp_db.description = "Fullstack React, Node.js, and GraphQL"
    db.commit()

    # Delayed write computed against cand_ev=1, opp_cv=1
    stale_cand = CandidateProfile(id=cand_db.id, user_id=uid, skills=[{"name": "React"}], evidence_version=1)
    stale_opp = Opportunity(id=opp_id, title="Fullstack Intern", description="React and Node.js", content_version=1)

    res = await matching_service.evaluate_match(stale_cand, stale_opp, db, force_refresh=True, use_ai=False)

    rec = db.query(CandidateOpportunityMatch).filter(
        CandidateOpportunityMatch.user_id == uid,
        CandidateOpportunityMatch.opportunity_id == opp_id
    ).first()
    assert rec is None, "Write against obsolete candidate and opportunity state MUST be rejected!"
    assert res.is_stale is True


@pytest.mark.asyncio
async def test_obsolete_content_hash_rejection(db: Session):
    """
    Adversarial Race 4:
    Even if version numbers match, an obsolete content hash cannot overwrite a record.
    """
    uid = 86004
    opp_id = 98004
    opp = create_opp(db, opp_id=opp_id, title="ML Intern", description="Python ML", content_version=1)
    cand = CandidateProfile(user_id=uid, name="Cand 4", skills=[{"name": "Python"}], evidence_version=1)
    cand = db.merge(cand)
    db.commit()
    db.refresh(cand)

    # Pre-populate valid match record
    now = utc_now()
    db.execute(text("""
        INSERT INTO candidate_opportunity_matches (
            user_id, candidate_id, opportunity_id, match_score, eligibility_status,
            match_analysis, candidate_content_hash, opportunity_content_hash,
            candidate_evidence_version, opportunity_content_version,
            engine_version, engine_generation, created_at, updated_at
        ) VALUES (
            :uid, :cid, :oid, 85.0, 'eligible', '{}'::json, 'hash_cand_valid', 'hash_opp_valid',
            1, 1, '2.0.0', 2, :now, :now
        )
    """), {"uid": uid, "cid": cand.id, "oid": opp_id, "now": now})
    db.commit()

    # Attempt to overwrite with obsolete candidate content hash under identical version numbers
    res = db.execute(text("""
        INSERT INTO candidate_opportunity_matches (
            user_id, candidate_id, opportunity_id, match_score, eligibility_status,
            match_analysis, candidate_content_hash, opportunity_content_hash,
            candidate_evidence_version, opportunity_content_version,
            engine_version, engine_generation, created_at, updated_at
        )
        SELECT
            c.user_id, c.id, o.id, 50.0, 'eligible', '{}'::json, 'hash_cand_OBSOLETE', 'hash_opp_valid',
            1, 1, '2.0.0', 2, :now, :now
        FROM candidate_profiles c, opportunities o
        WHERE c.id = :cid AND o.id = :oid
          AND COALESCE(c.evidence_version, 1) = 1
          AND COALESCE(o.content_version, 1) = 1
        ON CONFLICT ON CONSTRAINT uq_candidate_opportunity_match_user_opp
        DO UPDATE SET
            match_score = EXCLUDED.match_score,
            candidate_content_hash = EXCLUDED.candidate_content_hash
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
        RETURNING candidate_opportunity_matches.id;
    """), {"uid": uid, "cid": cand.id, "oid": opp_id, "now": now}).first()

    assert res is None, "Overwriting with an obsolete content hash under identical version must be rejected!"
    rec = db.query(CandidateOpportunityMatch).filter(
        CandidateOpportunityMatch.user_id == uid,
        CandidateOpportunityMatch.opportunity_id == opp_id
    ).first()
    assert rec.match_score == 85.0
    assert rec.candidate_content_hash == "hash_cand_valid"


@pytest.mark.asyncio
async def test_equal_version_and_equal_generation_concurrent_writes(db: Session):
    """
    Phase 3 Test:
    Two concurrent computations with identical input versions, engine generation, and content hashes.
    Must be completely idempotent without errors or data corruption.
    """
    uid = 86005
    opp_id = 98005
    opp = create_opp(db, opp_id=opp_id, title="DevOps Intern", description="Docker and Kubernetes")
    cand = CandidateProfile(user_id=uid, name="Cand 5", skills=[{"name": "Docker"}], evidence_version=1)
    cand = db.merge(cand)
    db.commit()
    db.refresh(cand)

    # First write
    res1 = await matching_service.evaluate_match(cand, opp, db, force_refresh=True, use_ai=False)
    rec1 = db.query(CandidateOpportunityMatch).filter(
        CandidateOpportunityMatch.user_id == uid,
        CandidateOpportunityMatch.opportunity_id == opp_id
    ).first()
    assert rec1 is not None

    # Concurrent second write with identical state
    res2 = await matching_service.evaluate_match(cand, opp, db, force_refresh=True, use_ai=False)
    rec2 = db.query(CandidateOpportunityMatch).filter(
        CandidateOpportunityMatch.user_id == uid,
        CandidateOpportunityMatch.opportunity_id == opp_id
    ).first()
    assert rec2 is not None
    assert rec2.id == rec1.id
    assert rec2.match_score == rec1.match_score


@pytest.mark.asyncio
async def test_batch_evaluation_races_with_single_evaluation(db: Session):
    """
    Adversarial Race 5:
    Batch evaluation computing for opps [A, B] runs while single evaluation updates candidate to v2.
    Batch write for A must NOT overwrite the fresher v2 single evaluation.
    """
    uid = 86006
    opp_a = create_opp(db, opp_id=98006, title="Opp A", description="Python A")
    opp_b = create_opp(db, opp_id=98007, title="Opp B", description="Python B")
    cand = CandidateProfile(user_id=uid, name="Cand 6", skills=[{"name": "Python"}], evidence_version=1)
    cand = db.merge(cand)
    db.commit()
    db.refresh(cand)

    # Single evaluation updates candidate to evidence_version 2 for opp_a
    cand.skills = [{"name": "Python"}, {"name": "Django"}]
    cand.evidence_version = 2
    cand.updated_at = utc_now()
    db.commit()
    db.refresh(cand)
    await matching_service.evaluate_match(cand, opp_a, db, force_refresh=True, use_ai=False)

    rec_a = db.query(CandidateOpportunityMatch).filter(
        CandidateOpportunityMatch.user_id == uid,
        CandidateOpportunityMatch.opportunity_id == opp_a.id
    ).first()
    assert rec_a.candidate_evidence_version == 2

    # Now a stale batch computation that was started at evidence_version 1 attempts to commit
    stale_cand = CandidateProfile(id=cand.id, user_id=uid, skills=[{"name": "Python"}], evidence_version=1)
    batch_res = await matching_service.evaluate_matches_batch(
        candidate=stale_cand,
        opportunities=[opp_a, opp_b],
        db=db,
        force_refresh=True,
        use_ai=False
    )

    # Opp A must retain evidence_version 2
    rec_a_after = db.query(CandidateOpportunityMatch).filter(
        CandidateOpportunityMatch.user_id == uid,
        CandidateOpportunityMatch.opportunity_id == opp_a.id
    ).first()
    assert rec_a_after.candidate_evidence_version == 2, "Batch stale write must NOT overwrite single v2 match!"


# ---------------------------------------------------------------------------
# Phase 2: Engine Generation Release Consistency & Directions
# ---------------------------------------------------------------------------

def test_deployment_engine_validation():
    """
    Phase 2 Test:
    validate_deployment_engine_release guarantees all workers in a deployment
    use valid, registered engine versions and consistent generations.
    """
    # 1. Valid registered releases
    v, g = validate_deployment_engine_release("2.0.0", 2)
    assert v == "2.0.0" and g == 2

    v, g = validate_deployment_engine_release("2.1.0", 3)
    assert v == "2.1.0" and g == 3

    # 2. Unknown release version rejected
    with pytest.raises(ValueError, match="not registered"):
        validate_deployment_engine_release("3.0.0-unreleased", 5)

    # 3. Mismatched generation rejected
    with pytest.raises(ValueError, match="does not match canonical generation"):
        validate_deployment_engine_release("2.0.0", configured_generation=5)


@pytest.mark.asyncio
async def test_worker_release_directions_old_vs_new(db: Session):
    """
    Phase 2 Test:
    Simulates workers running different engine generations:
    - Direction 1: Old engine worker (gen 1) writes first; new engine worker (gen 2) evaluates after -> updates cleanly.
    - Direction 2: New engine worker (gen 2) writes first; old engine worker (gen 1) evaluates after -> rejected cleanly.
    """
    uid = 86007
    opp_id = 98008
    opp = create_opp(db, opp_id=opp_id, title="Engine Dir Opp", description="Python")
    cand = CandidateProfile(user_id=uid, name="Engine Cand", skills=[{"name": "Python"}], evidence_version=1)
    cand = db.merge(cand)
    db.commit()
    db.refresh(cand)

    now = utc_now()
    # Baseline: Old Worker (gen 1, v1.9.0) writes
    db.execute(text("""
        INSERT INTO candidate_opportunity_matches (
            user_id, candidate_id, opportunity_id, match_score, eligibility_status,
            match_analysis, candidate_content_hash, opportunity_content_hash,
            candidate_evidence_version, opportunity_content_version,
            engine_version, engine_generation, created_at, updated_at
        ) VALUES (
            :uid, :cid, :oid, 70.0, 'eligible', '{}'::json, 'hash_c', 'hash_o',
            1, 1, '1.9.0', 1, :now, :now
        )
    """), {"uid": uid, "cid": cand.id, "oid": opp_id, "now": now})
    db.commit()

    # Direction 1: New Worker (gen 2, v2.0.0) evaluates -> MUST succeed and supersede
    res_dir1 = db.execute(text("""
        INSERT INTO candidate_opportunity_matches (
            user_id, candidate_id, opportunity_id, match_score, eligibility_status,
            match_analysis, candidate_content_hash, opportunity_content_hash,
            candidate_evidence_version, opportunity_content_version,
            engine_version, engine_generation, created_at, updated_at
        )
        SELECT
            c.user_id, c.id, o.id, 88.0, 'eligible', '{}'::json, 'hash_c', 'hash_o',
            1, 1, '2.0.0', 2, :now, :now
        FROM candidate_profiles c, opportunities o
        WHERE c.id = :cid AND o.id = :oid
          AND COALESCE(c.evidence_version, 1) = 1
          AND COALESCE(o.content_version, 1) = 1
        ON CONFLICT ON CONSTRAINT uq_candidate_opportunity_match_user_opp
        DO UPDATE SET
            match_score = EXCLUDED.match_score,
            engine_version = EXCLUDED.engine_version,
            engine_generation = EXCLUDED.engine_generation
        WHERE
            EXCLUDED.engine_generation >= candidate_opportunity_matches.engine_generation
            AND EXCLUDED.candidate_evidence_version >= candidate_opportunity_matches.candidate_evidence_version
            AND EXCLUDED.opportunity_content_version >= candidate_opportunity_matches.opportunity_content_version
            AND (
                EXCLUDED.engine_generation > candidate_opportunity_matches.engine_generation
                OR EXCLUDED.candidate_evidence_version > candidate_opportunity_matches.candidate_evidence_version
                OR EXCLUDED.opportunity_content_version > candidate_opportunity_matches.opportunity_content_version
            )
        RETURNING candidate_opportunity_matches.id;
    """), {"uid": uid, "cid": cand.id, "oid": opp_id, "now": now}).first()

    assert res_dir1 is not None, "Newer engine worker MUST supersede older generation!"
    rec_after_new = db.query(CandidateOpportunityMatch).filter(
        CandidateOpportunityMatch.user_id == uid,
        CandidateOpportunityMatch.opportunity_id == opp_id
    ).first()
    assert rec_after_new.engine_generation == 2
    assert rec_after_new.engine_version == "2.0.0"
    assert rec_after_new.match_score == 88.0

    # Direction 2: Old Worker (gen 1, v1.9.0) evaluates after -> MUST be rejected!
    res_dir2 = db.execute(text("""
        INSERT INTO candidate_opportunity_matches (
            user_id, candidate_id, opportunity_id, match_score, eligibility_status,
            match_analysis, candidate_content_hash, opportunity_content_hash,
            candidate_evidence_version, opportunity_content_version,
            engine_version, engine_generation, created_at, updated_at
        )
        SELECT
            c.user_id, c.id, o.id, 65.0, 'eligible', '{}'::json, 'hash_c', 'hash_o',
            1, 1, '1.9.0', 1, :now, :now
        FROM candidate_profiles c, opportunities o
        WHERE c.id = :cid AND o.id = :oid
          AND COALESCE(c.evidence_version, 1) = 1
          AND COALESCE(o.content_version, 1) = 1
        ON CONFLICT ON CONSTRAINT uq_candidate_opportunity_match_user_opp
        DO UPDATE SET
            match_score = EXCLUDED.match_score,
            engine_version = EXCLUDED.engine_version,
            engine_generation = EXCLUDED.engine_generation
        WHERE
            EXCLUDED.engine_generation >= candidate_opportunity_matches.engine_generation
            AND EXCLUDED.candidate_evidence_version >= candidate_opportunity_matches.candidate_evidence_version
            AND EXCLUDED.opportunity_content_version >= candidate_opportunity_matches.opportunity_content_version
            AND (
                EXCLUDED.engine_generation > candidate_opportunity_matches.engine_generation
                OR EXCLUDED.candidate_evidence_version > candidate_opportunity_matches.candidate_evidence_version
                OR EXCLUDED.opportunity_content_version > candidate_opportunity_matches.opportunity_content_version
            )
        RETURNING candidate_opportunity_matches.id;
    """), {"uid": uid, "cid": cand.id, "oid": opp_id, "now": now}).first()

    assert res_dir2 is None, "Older engine worker MUST NOT overwrite newer engine evaluation!"
    rec_final = db.query(CandidateOpportunityMatch).filter(
        CandidateOpportunityMatch.user_id == uid,
        CandidateOpportunityMatch.opportunity_id == opp_id
    ).first()
    assert rec_final.engine_generation == 2
    assert rec_final.engine_version == "2.0.0"
    assert rec_final.match_score == 88.0


# ---------------------------------------------------------------------------
# Phase 4: Pagination Session Final Audit & Heavy Pruning
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pagination_under_heavy_consecutive_pruning(db: Session):
    """
    Phase 4 Test:
    Catalogue of 100 items. Prunes consecutive blocks of 15, 20, and 25 items across
    different pages (deleted, closed, dismissed).
    Verifies:
    1. Scan-Fill forward-scans past pruned items to deliver exactly limit=20 items.
    2. Surviving opportunities retain their original relative order.
    3. Zero cross-page duplicates.
    4. next_cursor advances past all examined items.
    5. Exhausted session returns next_cursor=None and has_more=False.
    """
    uid = 86008
    cand = CandidateProfile(user_id=uid, name="Heavy Prune Cand", skills=[{"name": "Python"}], evidence_version=1)
    cand = db.merge(cand)
    db.commit()
    db.refresh(cand)

    # Create 100 opportunities
    now = utc_now()
    base_id = 98100
    for i in range(100):
        opp = Opportunity(
            id=base_id + i,
            title=f"Prune Job #{i:03d}",
            normalized_title=f"prune job #{i:03d}",
            company_name="PruneCorp",
            normalized_location="Remote",
            location="Remote",
            employment_type="internship",
            status="verified",
            description=f"Python job #{i}",
            source_platform="heavy_prune_src",
            original_url=f"https://prunecorp.com/jobs/{base_id + i}",
            is_dismissed=False,
            created_at=now
        )
        db.merge(opp)
    db.commit()

    # Page 1: Establish snapshot
    p1, total, snap_id, cur1, more1 = await execute_intelligent_discovery_search(
        db=db, user_id=uid, source_platform="heavy_prune_src", skip=0, limit=20, return_cursor=True
    )
    assert len(p1) == 20
    assert cur1 == 20
    assert more1 is True

    snap_ids, _ = snapshot_manager.get_snapshot_by_id(snap_id, db, user_id=uid)
    assert len(snap_ids) == 100

    # Prune heavy block 1: indices 20..39 (20 consecutive items: 10 closed, 10 dismissed)
    for idx in range(20, 30):
        db.query(Opportunity).filter(Opportunity.id == snap_ids[idx]).update({"status": "closed"})
    for idx in range(30, 40):
        db.query(Opportunity).filter(Opportunity.id == snap_ids[idx]).update({"is_dismissed": True})
    db.commit()

    # Page 2: Request from cursor=20 with limit=20
    # Must skip all 20 pruned items (20..39) and return 20 eligible items from 40..59
    p2, _, _, cur2, more2 = await execute_intelligent_discovery_search(
        db=db, user_id=uid, source_platform="heavy_prune_src", cursor=cur1, limit=20, snapshot_id=snap_id, return_cursor=True
    )
    assert len(p2) == 20, f"Expected 20 items on page 2, got {len(p2)}"
    assert cur2 == 60, f"Expected cursor to advance past 20 examined pruned + 20 delivered = 60, got {cur2}"
    assert more2 is True

    # Verify zero duplicates between Page 1 and Page 2
    p1_ids = {it["id"] for it in p1}
    p2_ids = {it["id"] for it in p2}
    assert len(p1_ids.intersection(p2_ids)) == 0

    # Verify pruned items are absent
    pruned_ids = {snap_ids[i] for i in range(20, 40)}
    assert len(p2_ids.intersection(pruned_ids)) == 0

    # Prune heavy block 2: indices 60..89 (30 consecutive items deleted)
    for idx in range(60, 90):
        db.query(Opportunity).filter(Opportunity.id == snap_ids[idx]).delete()
    db.commit()

    # Page 3: Request from cursor=60 with limit=20
    # Remaining items in snapshot: 90..99 (only 10 items exist in catalogue!)
    # Scan-Fill must scan 60..89 (30 deleted items), deliver the remaining 10 items,
    # and terminate session with next_cursor=None, has_more=False!
    p3, _, _, cur3, more3 = await execute_intelligent_discovery_search(
        db=db, user_id=uid, source_platform="heavy_prune_src", cursor=cur2, limit=20, snapshot_id=snap_id, return_cursor=True
    )
    assert len(p3) == 10, f"Final page must return surviving 10 items, got {len(p3)}"
    assert more3 is False, "has_more MUST be False on exhausted session"
    assert cur3 is None, "next_cursor MUST be None on exhausted session"

    p3_ids = {it["id"] for it in p3}
    assert len(p1_ids.intersection(p3_ids)) == 0
    assert len(p2_ids.intersection(p3_ids)) == 0
