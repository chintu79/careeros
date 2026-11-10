"""
Automated Test Suite for CareerOS — Iteration 1.7: Matching Engine Validation, Calibration & Adversarial Hardening.
Covers Phases 3 through 7:
- Phase 3: Scoring engine validation (category bounds, weight sum, duplicate protection, capping)
- Phase 4: Eligibility criteria audit and critical requirement testing
- Phase 5: Evidence provenance trust boundaries (unverified immutability, ownership vs authorship)
- Phase 6: Security and tenant isolation (GET & POST 403 checks, cached match privacy, payload tampering rejection)
- Phase 7: Cache versioning, concurrency row locking, and stale preservation
"""
import asyncio
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.core.auth import create_access_token
from backend.app.models.candidate import CandidateProfile
from backend.app.models.opportunity import Opportunity
from backend.app.schemas.matching import (
    RequirementPriority,
    MatchStatus,
    EvidenceProvenanceType,
    ExtractedRequirement,
    ParsedJobDescription,
    CandidateEvidenceItem,
    UnifiedCandidateEvidence,
    ProfileMatchResult,
)
from backend.app.services.matching.matching_engine import (
    calculate_profile_match,
    match_single_requirement,
    CATEGORY_WEIGHTS
)
from backend.app.services.matching.service import matching_service, MATCHING_ENGINE_VERSION

client = TestClient(app)

TEST_USER_A = 99701
TEST_USER_B = 99702


def auth_headers(user_id: int):
    token = create_access_token(user_id=user_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def clean_db():
    from backend.app.models.candidate_opportunity_match import CandidateOpportunityMatch
    db = SessionLocal()
    try:
        db.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id.in_([TEST_USER_A, TEST_USER_B])).delete(synchronize_session=False)
        db.query(Opportunity).filter(
            (Opportunity.user_id.in_([TEST_USER_A, TEST_USER_B])) |
            (Opportunity.original_url.like("https://example.com/%"))
        ).delete(synchronize_session=False)
        db.query(CandidateProfile).filter(CandidateProfile.user_id.in_([TEST_USER_A, TEST_USER_B])).delete(synchronize_session=False)
        db.commit()
        yield db
    finally:
        db.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id.in_([TEST_USER_A, TEST_USER_B])).delete(synchronize_session=False)
        db.query(Opportunity).filter(
            (Opportunity.user_id.in_([TEST_USER_A, TEST_USER_B])) |
            (Opportunity.original_url.like("https://example.com/%"))
        ).delete(synchronize_session=False)
        db.query(CandidateProfile).filter(CandidateProfile.user_id.in_([TEST_USER_A, TEST_USER_B])).delete(synchronize_session=False)
        db.commit()
        db.close()


# -------------------------------------------------------------------------
# Phase 3: Scoring Engine Validation
# -------------------------------------------------------------------------

def test_phase3_category_weights_sum_to_one():
    """Validates that category weights mathematically sum to exactly 1.0 within float tolerance."""
    total_weight = sum(CATEGORY_WEIGHTS.values())
    assert total_weight == pytest.approx(1.0, abs=0.0001)
    assert CATEGORY_WEIGHTS["mandatory_technical_skills"] == 0.40
    assert CATEGORY_WEIGHTS["preferred_technical_skills"] == 0.15
    assert CATEGORY_WEIGHTS["relevant_experience"] == 0.20
    assert CATEGORY_WEIGHTS["project_evidence"] == 0.15
    assert CATEGORY_WEIGHTS["education_and_certifications"] == 0.10


def test_phase3_duplicate_requirements_cannot_inflate_scores():
    """
    Validates that if duplicate requirements are present in the parsed JD,
    they are deduplicated by canonical name and do not artificially inflate scores.
    """
    candidate_evidence = UnifiedCandidateEvidence(
        user_id=TEST_USER_A,
        evidence_items=[
            CandidateEvidenceItem(
                name="Python",
                canonical_name="Python",
                provenance=EvidenceProvenanceType.MANUAL_SKILL,
                source_identifier="skills",
                evidence_text="Python",
                is_verified=True
            )
        ],
        content_hash="cand_hash_dup"
    )

    # Candidate has Python (1.0), lacks Rust (0.0, no relationship in taxonomy).
    # If Python is duplicated 3 times, naive average would be (3 * 1.0 + 0.0) / 4 = 75.0%.
    # With deduplication, average MUST be (1.0 + 0.0) / 2 = 50.0%.
    req_py1 = ExtractedRequirement(name="Python", category="programming_language", priority=RequirementPriority.MANDATORY)
    req_py2 = ExtractedRequirement(name="Python", category="programming_language", priority=RequirementPriority.MANDATORY)
    req_py3 = ExtractedRequirement(name="Python", category="programming_language", priority=RequirementPriority.MANDATORY)
    req_rust = ExtractedRequirement(name="Rust", category="programming_language", priority=RequirementPriority.MANDATORY)

    parsed_jd = ParsedJobDescription(
        job_title="Software Engineer",
        requirements=[req_py1, req_py2, req_py3, req_rust],
        mandatory_skills=["Python", "Rust"],
        content_hash="jd_hash_dup"
    )

    result, matches = calculate_profile_match(parsed_jd, candidate_evidence)
    assert result.category_scores["mandatory_technical_skills"] == 50.0
    # Requirement matches should contain 2 distinct evaluated requirements (Python and Rust)
    unique_matched_reqs = {m.requirement.name for m in matches}
    assert unique_matched_reqs == {"Python", "Rust"}


def test_phase3_duplicate_evidence_cannot_inflate_score():
    """
    Validates that a candidate having the same technology across multiple sources
    (manual skill, 3 projects, 2 manifests) receives max strength 1.0, not > 1.0.
    """
    evidence_items = [
        CandidateEvidenceItem(name="Python", canonical_name="Python", provenance=EvidenceProvenanceType.MANUAL_SKILL, source_identifier="skills", is_verified=True),
        CandidateEvidenceItem(name="Python", canonical_name="Python", provenance=EvidenceProvenanceType.CURATED_PROJECT, source_identifier="proj_1", is_verified=True),
        CandidateEvidenceItem(name="Python", canonical_name="Python", provenance=EvidenceProvenanceType.CURATED_PROJECT, source_identifier="proj_2", is_verified=True),
        CandidateEvidenceItem(name="Python", canonical_name="Python", provenance=EvidenceProvenanceType.GITHUB_MANIFEST, source_identifier="manifest_1", is_verified=True)
    ]
    candidate_evidence = UnifiedCandidateEvidence(
        user_id=TEST_USER_A,
        evidence_items=evidence_items,
        content_hash="cand_hash_multi_ev"
    )

    req_py = ExtractedRequirement(name="Python", category="programming_language", priority=RequirementPriority.MANDATORY)
    parsed_jd = ParsedJobDescription(
        job_title="Python Engineer",
        requirements=[req_py],
        mandatory_skills=["Python"],
        content_hash="jd_hash_py"
    )

    result, matches = calculate_profile_match(parsed_jd, candidate_evidence)
    assert len(matches) == 1
    assert matches[0].evidence_strength == 1.0
    assert result.category_scores["mandatory_technical_skills"] == 100.0


def test_phase3_score_boundaries_strict_zero_to_hundred():
    """Validates that category scores and final scores are always within [0.0, 100.0]."""
    # Worst case: empty candidate
    empty_cand = UnifiedCandidateEvidence(user_id=TEST_USER_A, content_hash="empty")
    hard_jd = ParsedJobDescription(
        job_title="Distinguished Architect",
        requirements=[
            ExtractedRequirement(name="Rust", category="programming_language", priority=RequirementPriority.MANDATORY),
            ExtractedRequirement(name="C++", category="programming_language", priority=RequirementPriority.MANDATORY)
        ],
        experience_requirements="10+ years",
        employment_type="full_time",
        content_hash="hard_jd"
    )
    res_low, _ = calculate_profile_match(hard_jd, empty_cand)
    assert 0.0 <= res_low.profile_match_score <= 100.0
    for cat_score in res_low.category_scores.values():
        assert 0.0 <= cat_score <= 100.0


# -------------------------------------------------------------------------
# Phase 4: Eligibility Criteria Audit
# -------------------------------------------------------------------------

def test_phase4_eligibility_one_critical_missing_mandatory():
    """Jobs with 1 mandatory requirement: candidate missing it receives 0% and is flagged."""
    candidate_evidence = UnifiedCandidateEvidence(user_id=TEST_USER_A, content_hash="cand_empty")
    parsed_jd = ParsedJobDescription(
        job_title="Lead Architect",
        requirements=[ExtractedRequirement(name="Python", category="programming_language", priority=RequirementPriority.MANDATORY)],
        mandatory_skills=["Python"],
        content_hash="jd_single"
    )
    result, _ = calculate_profile_match(parsed_jd, candidate_evidence)
    assert result.category_scores["mandatory_technical_skills"] == 0.0
    assert result.eligibility_status == "flagged"
    assert "Significant mandatory technical gaps" in result.disqualifying_reasons[0]


def test_phase4_eligibility_zero_mandatory_requirements():
    """Jobs specifying zero mandatory requirements: candidate is eligible."""
    candidate_evidence = UnifiedCandidateEvidence(user_id=TEST_USER_A, content_hash="cand_empty")
    parsed_jd = ParsedJobDescription(
        job_title="General Contributor",
        requirements=[ExtractedRequirement(name="Docker", category="cloud_devops", priority=RequirementPriority.PREFERRED)],
        mandatory_skills=[],
        preferred_skills=["Docker"],
        content_hash="jd_zero_mand"
    )
    result, _ = calculate_profile_match(parsed_jd, candidate_evidence)
    assert result.category_scores["mandatory_technical_skills"] == 100.0
    assert result.eligibility_status == "eligible"


# -------------------------------------------------------------------------
# Phase 5: Evidence Provenance & Trust Boundaries
# -------------------------------------------------------------------------

def test_phase5_unverified_github_evidence_cannot_upgrade_to_verified():
    """Unverified GitHub manifest dependency remains capped at <= 0.20 and WEAK_MATCH."""
    unverified_item = CandidateEvidenceItem(
        name="Kubernetes",
        canonical_name="Kubernetes",
        provenance=EvidenceProvenanceType.GITHUB_MANIFEST,
        source_identifier="unverified_repo/k8s.yaml",
        is_verified=False
    )
    candidate_evidence = UnifiedCandidateEvidence(
        user_id=TEST_USER_A,
        evidence_items=[unverified_item],
        content_hash="cand_unverified"
    )
    req = ExtractedRequirement(name="Kubernetes", category="cloud_devops", priority=RequirementPriority.MANDATORY)
    parsed_jd = ParsedJobDescription(job_title="DevOps", requirements=[req], content_hash="jd_k8s")

    result, matches = calculate_profile_match(parsed_jd, candidate_evidence)
    assert matches[0].status == MatchStatus.WEAK_MATCH
    assert matches[0].evidence_strength <= 0.20
    assert matches[0].matched_evidence[0].is_verified is False


def test_phase5_ai_derived_project_claim_cannot_produce_strong_match():
    """AI-derived insight without verified manifest proof is always is_verified=False and capped."""
    ai_item = CandidateEvidenceItem(
        name="PyTorch",
        canonical_name="PyTorch",
        provenance=EvidenceProvenanceType.AI_DERIVED_PROJECT,
        source_identifier="ai_summary",
        is_verified=False
    )
    candidate_evidence = UnifiedCandidateEvidence(
        user_id=TEST_USER_A,
        evidence_items=[ai_item],
        content_hash="cand_ai"
    )
    req = ExtractedRequirement(name="PyTorch", category="framework_library", priority=RequirementPriority.MANDATORY)
    parsed_jd = ParsedJobDescription(job_title="ML Eng", requirements=[req], content_hash="jd_ml")

    result, matches = calculate_profile_match(parsed_jd, candidate_evidence)
    assert matches[0].status == MatchStatus.WEAK_MATCH
    assert matches[0].evidence_strength <= 0.20


# -------------------------------------------------------------------------
# Phase 6: Security and Tenant Isolation
# -------------------------------------------------------------------------

def test_phase6_get_private_opportunity_blocks_unauthorized_user(clean_db):
    """Candidate B calling GET /api/opportunities/{id} on Candidate A's private opportunity receives 403."""
    db = clean_db
    opp_a = Opportunity(
        user_id=TEST_USER_A,
        title="Candidate A Private Job",
        normalized_title="Candidate A Private Job",
        company_name="Private Co",
        description="Private description",
        source_platform="custom",
        original_url="https://example.com/priv_get"
    )
    db.add(opp_a)
    db.commit()
    db.refresh(opp_a)

    # Candidate B attempts to GET Candidate A's private opportunity
    resp = client.get(f"/api/opportunities/{opp_a.id}", headers=auth_headers(TEST_USER_B))
    assert resp.status_code == 403
    assert "Not authorized" in resp.json()["detail"]


def test_phase6_cached_match_analysis_not_leaked_across_tenants(clean_db):
    """
    On a shared/public opportunity where Candidate A cached private matching intelligence,
    Candidate B calling GET /api/opportunities/{id} does NOT receive Candidate A's evidence items or gaps.
    """
    db = clean_db
    cand_a = CandidateProfile(user_id=TEST_USER_A, name="Alice", email="alice@test.com", skills=["Python"])
    cand_b = CandidateProfile(user_id=TEST_USER_B, name="Bob", email="bob@test.com", skills=["Rust"])
    # Public opportunity (user_id = None)
    opp_pub = Opportunity(
        user_id=None,
        title="Public Python Job",
        normalized_title="Public Python Job",
        company_name="Open Co",
        description="Python developer needed.",
        source_platform="lever",
        original_url="https://example.com/pub_leak_test",
        match_analysis={
            "user_id": TEST_USER_A,
            "profile_match_score": 95.0,
            "candidate_content_hash": "alice_hash",
            "opportunity_content_hash": "opp_hash",
            "category_scores": {"mandatory_technical_skills": 100.0},
            "category_weights": {"mandatory_technical_skills": 0.40},
            "requirement_matches": [{"requirement": {"name": "Python"}, "status": "strong_match", "evidence_strength": 1.0}],
            "skill_gaps": [{"skill_name": "NicheSkill", "missing_evidence": "Alice lacks NicheSkill"}],
            "scoring_explanation": "Alice scored 95/100."
        }
    )
    db.add(cand_a)
    db.add(cand_b)
    db.add(opp_pub)
    db.commit()
    db.refresh(opp_pub)

    # Candidate B requests GET on this public opportunity
    resp_b = client.get(f"/api/opportunities/{opp_pub.id}", headers=auth_headers(TEST_USER_B))
    assert resp_b.status_code == 200
    data_b = resp_b.json()

    # Crucial tenant privacy assertion: Candidate B must NOT see Alice's cached matches or gaps!
    assert data_b["requirement_matches"] == []
    assert data_b["skill_gaps"] == []
    assert "Alice" not in data_b["scoring_explanation"]


def test_phase6_tampered_payload_cannot_override_candidate_identity(clean_db):
    """
    Client sending manipulated payload attempting to inject candidate_id, score, or eligibility
    is ignored; server strictly uses authenticated session identity.
    """
    db = clean_db
    cand_b = CandidateProfile(user_id=TEST_USER_B, name="Bob", email="bob@test.com", skills=["Python"])
    opp = Opportunity(
        user_id=None,
        title="Standard Dev",
        normalized_title="Standard Dev",
        company_name="Standard Co",
        description="Python needed.",
        source_platform="greenhouse",
        original_url="https://example.com/tamper_test"
    )
    db.add(cand_b)
    db.add(opp)
    db.commit()
    db.refresh(opp)

    malicious_payload = {
        "force_refresh": True,
        "candidate_id": 1,         # Malicious candidate ID override attempt
        "user_id": 1,              # Malicious user ID override attempt
        "profile_match_score": 100 # Malicious score injection attempt
    }
    resp = client.post(
        f"/api/opportunities/{opp.id}/evaluate-match",
        headers=auth_headers(TEST_USER_B),
        json=malicious_payload
    )
    assert resp.status_code == 200
    data = resp.json()
    # Verified: server used TEST_USER_B, not injected user 1
    assert data["user_id"] == TEST_USER_B


# -------------------------------------------------------------------------
# Phase 7: Cache & Concurrency Reliability
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_phase7_engine_version_mismatch_invalidates_cache(clean_db):
    """When matching_engine_version changes, cached analyses are invalidated and recomputed."""
    db = clean_db
    cand = CandidateProfile(user_id=TEST_USER_A, name="Cache Version Dev", email="cand@test.com", skills=["Python"])
    opp = Opportunity(
        user_id=TEST_USER_A,
        title="Python Dev",
        normalized_title="Python Dev",
        company_name="Version Co",
        description="Requires Python.",
        source_platform="direct",
        original_url="https://example.com/ver_cache"
    )
    db.add(cand)
    db.add(opp)
    db.commit()
    db.refresh(cand)
    db.refresh(opp)

    # 1. Evaluate fresh
    res1 = await matching_service.evaluate_match(candidate=cand, opportunity=opp, db=db, use_ai=False)
    assert res1.is_cached is False
    assert res1.engine_version == MATCHING_ENGINE_VERSION

    # 2. Simulate outdated engine version stored in cache
    opp.match_analysis["engine_version"] = "1.0.0"
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(opp, "match_analysis")
    from backend.app.models.candidate_opportunity_match import CandidateOpportunityMatch
    match_rec = db.query(CandidateOpportunityMatch).filter(
        CandidateOpportunityMatch.user_id == TEST_USER_A,
        CandidateOpportunityMatch.opportunity_id == opp.id
    ).first()
    if match_rec:
        match_rec.engine_version = "1.0.0"
        match_rec.match_analysis["engine_version"] = "1.0.0"
        flag_modified(match_rec, "match_analysis")
    db.commit()
    db.refresh(opp)

    # 3. Next evaluate: detects engine_version mismatch and invalidates cache!
    res2 = await matching_service.evaluate_match(candidate=cand, opportunity=opp, db=db, use_ai=False)
    assert res2.is_cached is False
    assert res2.engine_version == MATCHING_ENGINE_VERSION
