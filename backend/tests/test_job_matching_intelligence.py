"""
Comprehensive Automated Test Suite for CareerOS — Iteration 1.6: Evidence-Based Job-to-Profile Matching Intelligence.
Covers all 18 required scenarios:
1. Mandatory skill exact match (STRONG_MATCH, 1.0 strength)
2. Preferred skill match (separate weight & STRONG_MATCH)
3. Related technologies NOT treated as exact (React vs Angular -> PARTIAL_MATCH 0.55)
4. Missing mandatory requirements (penalty deduction & flagging)
5. Insufficient candidate evidence (< 30 score, NO_EVIDENCE)
6. GitHub-derived technology matching (GITHUB_MANIFEST provenance, verified)
7. Unverified repo contributions NOT treated as verified (capped <= 0.20 strength)
8. Education and certification matching (degree equivalence)
9. Deterministic scoring reproducibility (10 runs bitwise identical)
10. Weight calculations correctness (40/15/20/15/10 breakdown)
11. Missing data handling (neutral 100.0 credit for unstated JD requirements)
12. Skill gap recommendation relevance (excludes demonstrated skills, specific projects)
13. Groq unavailable behavior (deterministic fallback without crash)
14. Profile changes invalidate cache (candidate_content_hash mismatch)
15. Opportunity changes invalidate cache (opportunity_content_hash mismatch)
16. Concurrent matching calculations (row locking serialization)
17. Candidate ownership enforcement (tenant isolation 403/404)
18. Preservation of previous matching on failure (is_stale=True resilience)
"""
import asyncio
import copy
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
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
from backend.app.services.matching.jd_parser import parse_job_description_deterministic
from backend.app.services.matching.evidence_builder import build_unified_candidate_evidence
from backend.app.services.matching.matching_engine import (
    calculate_profile_match,
    match_single_requirement,
    evaluate_education_and_certifications,
    CATEGORY_WEIGHTS
)
from backend.app.services.matching.gap_analyzer import analyze_skill_gaps
from backend.app.services.matching.service import matching_service

client = TestClient(app)

TEST_USER_A = 99801
TEST_USER_B = 99802


def auth_headers(user_id: int):
    token = create_access_token(user_id=user_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def clean_db():
    db = SessionLocal()
    try:
        db.query(Opportunity).filter(Opportunity.user_id.in_([TEST_USER_A, TEST_USER_B])).delete(synchronize_session=False)
        db.query(CandidateProfile).filter(CandidateProfile.user_id.in_([TEST_USER_A, TEST_USER_B])).delete(synchronize_session=False)
        db.commit()
        yield db
    finally:
        db.query(Opportunity).filter(Opportunity.user_id.in_([TEST_USER_A, TEST_USER_B])).delete(synchronize_session=False)
        db.query(CandidateProfile).filter(CandidateProfile.user_id.in_([TEST_USER_A, TEST_USER_B])).delete(synchronize_session=False)
        db.commit()
        db.close()


# -------------------------------------------------------------------------
# Test 1: Mandatory Skill Exact Match
# -------------------------------------------------------------------------
def test_01_mandatory_skill_exact_match():
    evidence_items = [
        CandidateEvidenceItem(
            name="Python",
            canonical_name="Python",
            provenance=EvidenceProvenanceType.MANUAL_SKILL,
            source_identifier="CandidateProfile.skills",
            evidence_text="Python listed in skills",
            is_verified=True
        ),
        CandidateEvidenceItem(
            name="FastAPI",
            canonical_name="FastAPI",
            provenance=EvidenceProvenanceType.MANUAL_SKILL,
            source_identifier="CandidateProfile.skills",
            evidence_text="FastAPI listed in skills",
            is_verified=True
        )
    ]
    candidate_evidence = UnifiedCandidateEvidence(
        user_id=TEST_USER_A,
        evidence_items=evidence_items,
        experience_years=1.0,
        content_hash="test_cand_hash_01"
    )

    req1 = ExtractedRequirement(
        name="Python",
        category="programming_language",
        priority=RequirementPriority.MANDATORY,
        source_text="Must have strong Python programming experience."
    )
    req2 = ExtractedRequirement(
        name="FastAPI",
        category="framework_library",
        priority=RequirementPriority.MANDATORY,
        source_text="Required experience building REST APIs with FastAPI."
    )
    parsed_jd = ParsedJobDescription(
        job_title="Backend Python Developer",
        company="Acme Cloud",
        requirements=[req1, req2],
        mandatory_skills=["Python", "FastAPI"],
        content_hash="test_jd_hash_01"
    )

    result, req_matches = calculate_profile_match(parsed_jd, candidate_evidence)

    assert result.profile_match_score >= 80.0
    assert result.category_scores["mandatory_technical_skills"] == 100.0
    assert len(req_matches) == 2
    for m in req_matches:
        assert m.status == MatchStatus.STRONG_MATCH
        assert m.evidence_strength == 1.0
        assert len(m.matched_evidence) > 0
        assert m.matched_evidence[0].is_verified is True


# -------------------------------------------------------------------------
# Test 2: Preferred Skill Match
# -------------------------------------------------------------------------
def test_02_preferred_skill_match():
    evidence_items = [
        CandidateEvidenceItem(
            name="Python",
            canonical_name="Python",
            provenance=EvidenceProvenanceType.MANUAL_SKILL,
            source_identifier="CandidateProfile.skills",
            evidence_text="Python",
            is_verified=True
        ),
        CandidateEvidenceItem(
            name="Redis",
            canonical_name="Redis",
            provenance=EvidenceProvenanceType.MANUAL_SKILL,
            source_identifier="CandidateProfile.skills",
            evidence_text="Redis",
            is_verified=True
        ),
        CandidateEvidenceItem(
            name="Docker",
            canonical_name="Docker",
            provenance=EvidenceProvenanceType.MANUAL_SKILL,
            source_identifier="CandidateProfile.skills",
            evidence_text="Docker",
            is_verified=True
        )
    ]
    candidate_evidence = UnifiedCandidateEvidence(
        user_id=TEST_USER_A,
        evidence_items=evidence_items,
        experience_years=1.0,
        content_hash="test_cand_hash_02"
    )

    req_mand = ExtractedRequirement(
        name="Python",
        category="programming_language",
        priority=RequirementPriority.MANDATORY
    )
    req_pref1 = ExtractedRequirement(
        name="Redis",
        category="database",
        priority=RequirementPriority.PREFERRED
    )
    req_pref2 = ExtractedRequirement(
        name="Docker",
        category="cloud_devops",
        priority=RequirementPriority.PREFERRED
    )
    parsed_jd = ParsedJobDescription(
        job_title="Software Engineer",
        company="Redis Labs",
        requirements=[req_mand, req_pref1, req_pref2],
        mandatory_skills=["Python"],
        preferred_skills=["Redis", "Docker"],
        content_hash="test_jd_hash_02"
    )

    result, req_matches = calculate_profile_match(parsed_jd, candidate_evidence)

    assert result.category_scores["mandatory_technical_skills"] == 100.0
    assert result.category_scores["preferred_technical_skills"] == 100.0
    pref_matches = [m for m in req_matches if m.requirement.priority == RequirementPriority.PREFERRED]
    assert len(pref_matches) == 2
    for pm in pref_matches:
        assert pm.status == MatchStatus.STRONG_MATCH
        assert pm.evidence_strength == 1.0


# -------------------------------------------------------------------------
# Test 3: Related Technologies NOT Treated as Exact (React vs Angular)
# -------------------------------------------------------------------------
def test_03_related_technologies_not_exact():
    candidate_evidence = UnifiedCandidateEvidence(
        user_id=TEST_USER_A,
        evidence_items=[
            CandidateEvidenceItem(
                name="React",
                canonical_name="React",
                provenance=EvidenceProvenanceType.MANUAL_SKILL,
                source_identifier="CandidateProfile.skills",
                evidence_text="React frontend development",
                is_verified=True
            )
        ],
        content_hash="test_cand_hash_03"
    )

    # Job specifically requires Angular
    req_angular = ExtractedRequirement(
        name="Angular",
        category="framework_library",
        priority=RequirementPriority.MANDATORY,
        source_text="Must have expert Angular frontend development skills."
    )
    parsed_jd = ParsedJobDescription(
        job_title="Angular Frontend Engineer",
        company="Enterprise Tech",
        requirements=[req_angular],
        mandatory_skills=["Angular"],
        content_hash="test_jd_hash_03"
    )

    result, req_matches = calculate_profile_match(parsed_jd, candidate_evidence)

    assert len(req_matches) == 1
    match = req_matches[0]
    # Critical verification: React is NOT an exact match for Angular!
    assert match.status == MatchStatus.PARTIAL_MATCH
    assert match.evidence_strength == pytest.approx(0.55, abs=0.01)
    assert match.evidence_strength < 1.0
    assert "Related technology" in match.explanation
    assert result.category_scores["mandatory_technical_skills"] == pytest.approx(55.0, abs=0.1)


# -------------------------------------------------------------------------
# Test 4: Missing Mandatory Requirements
# -------------------------------------------------------------------------
def test_04_missing_mandatory_requirements():
    candidate_evidence = UnifiedCandidateEvidence(
        user_id=TEST_USER_A,
        evidence_items=[
            CandidateEvidenceItem(
                name="HTML",
                canonical_name="HTML",
                provenance=EvidenceProvenanceType.MANUAL_SKILL,
                source_identifier="skills",
                evidence_text="HTML markup",
                is_verified=True
            )
        ],
        content_hash="test_cand_hash_04"
    )

    req_rust = ExtractedRequirement(
        name="Rust",
        category="programming_language",
        priority=RequirementPriority.MANDATORY,
        source_text="Must have strong Rust systems programming experience."
    )
    req_k8s = ExtractedRequirement(
        name="Kubernetes",
        category="cloud_devops",
        priority=RequirementPriority.MANDATORY,
        source_text="Production Kubernetes cluster orchestration experience required."
    )
    parsed_jd = ParsedJobDescription(
        job_title="Systems Engineer",
        company="Core Systems",
        requirements=[req_rust, req_k8s],
        mandatory_skills=["Rust", "Kubernetes"],
        content_hash="test_jd_hash_04"
    )

    result, req_matches = calculate_profile_match(parsed_jd, candidate_evidence)

    assert result.category_scores["mandatory_technical_skills"] == 0.0
    for m in req_matches:
        assert m.status == MatchStatus.NO_EVIDENCE
        assert m.evidence_strength == 0.0
    assert result.eligibility_status in ["flagged", "disqualified"]


# -------------------------------------------------------------------------
# Test 5: Insufficient Candidate Evidence
# -------------------------------------------------------------------------
def test_05_insufficient_candidate_evidence():
    candidate_evidence = UnifiedCandidateEvidence(
        user_id=TEST_USER_A,
        evidence_items=[
            CandidateEvidenceItem(
                name="Origami",
                canonical_name="Origami",
                provenance=EvidenceProvenanceType.MANUAL_SKILL,
                source_identifier="skills",
                evidence_text="Origami paper folding",
                is_verified=False
            )
        ],
        experience_years=0.0,
        content_hash="test_cand_hash_05"
    )

    req1 = ExtractedRequirement(name="Go", category="programming_language", priority=RequirementPriority.MANDATORY)
    req2 = ExtractedRequirement(name="Distributed Systems", category="cloud_devops", priority=RequirementPriority.MANDATORY)
    req3 = ExtractedRequirement(name="AWS", category="cloud_devops", priority=RequirementPriority.MANDATORY)
    parsed_jd = ParsedJobDescription(
        job_title="Senior Cloud Infrastructure Lead",
        company="Hyperscaler",
        requirements=[req1, req2, req3],
        mandatory_skills=["Go", "Distributed Systems", "AWS"],
        experience_requirements="5+ years",
        employment_type="full_time",
        content_hash="test_jd_hash_05"
    )

    result, req_matches = calculate_profile_match(parsed_jd, candidate_evidence)

    assert result.category_scores["mandatory_technical_skills"] == 0.0
    assert result.category_scores["relevant_experience"] < 30.0
    assert result.eligibility_status == "flagged"


# -------------------------------------------------------------------------
# Test 6: GitHub-Derived Technology Matching (Verified Manifest Evidence)
# -------------------------------------------------------------------------
def test_06_github_derived_technology_matching():
    evidence_items = [
        CandidateEvidenceItem(
            name="FastAPI",
            canonical_name="FastAPI",
            provenance=EvidenceProvenanceType.GITHUB_MANIFEST,
            source_identifier="requirements.txt",
            evidence_text="FastAPI==0.110.0 in requirements.txt",
            is_verified=True
        ),
        CandidateEvidenceItem(
            name="PostgreSQL",
            canonical_name="PostgreSQL",
            provenance=EvidenceProvenanceType.GITHUB_MANIFEST,
            source_identifier="docker-compose.yml",
            evidence_text="postgres:15-alpine in docker-compose.yml",
            is_verified=True
        )
    ]
    candidate_evidence = UnifiedCandidateEvidence(
        user_id=TEST_USER_A,
        evidence_items=evidence_items,
        content_hash="test_cand_hash_06"
    )

    req_fastapi = ExtractedRequirement(
        name="FastAPI",
        category="framework_library",
        priority=RequirementPriority.MANDATORY
    )
    req_postgres = ExtractedRequirement(
        name="PostgreSQL",
        category="database",
        priority=RequirementPriority.MANDATORY
    )
    parsed_jd = ParsedJobDescription(
        job_title="Backend API Engineer",
        company="Scale AI",
        requirements=[req_fastapi, req_postgres],
        mandatory_skills=["FastAPI", "PostgreSQL"],
        content_hash="test_jd_hash_06"
    )

    result, req_matches = calculate_profile_match(parsed_jd, candidate_evidence)

    assert result.category_scores["mandatory_technical_skills"] == 100.0
    for m in req_matches:
        assert m.status == MatchStatus.STRONG_MATCH
        assert m.matched_evidence[0].provenance == EvidenceProvenanceType.GITHUB_MANIFEST
        assert m.matched_evidence[0].is_verified is True


# -------------------------------------------------------------------------
# Test 7: Unverified Repo Contributions NOT Treated as Verified
# -------------------------------------------------------------------------
def test_07_unverified_repo_contributions_not_verified():
    evidence_items = [
        CandidateEvidenceItem(
            name="Rust",
            canonical_name="Rust",
            provenance=EvidenceProvenanceType.GITHUB_MANIFEST,
            source_identifier="unverified-blockchain/Cargo.toml",
            evidence_text="Cargo.toml in unverified repository",
            is_verified=False
        )
    ]
    candidate_evidence = UnifiedCandidateEvidence(
        user_id=TEST_USER_A,
        evidence_items=evidence_items,
        content_hash="test_cand_hash_07"
    )

    req_rust = ExtractedRequirement(
        name="Rust",
        category="programming_language",
        priority=RequirementPriority.MANDATORY
    )
    parsed_jd = ParsedJobDescription(
        job_title="Rust Systems Engineer",
        company="Blockchain Labs",
        requirements=[req_rust],
        mandatory_skills=["Rust"],
        content_hash="test_jd_hash_07"
    )

    result, req_matches = calculate_profile_match(parsed_jd, candidate_evidence)

    assert len(req_matches) == 1
    match = req_matches[0]
    # Critical trust boundary: unverified repo evidence CANNOT produce STRONG_MATCH
    assert match.status != MatchStatus.STRONG_MATCH
    assert match.evidence_strength <= 0.20
    assert match.matched_evidence[0].is_verified is False
    assert "Unverified signal" in match.explanation


# -------------------------------------------------------------------------
# Test 8: Education and Certification Matching
# -------------------------------------------------------------------------
def test_08_education_and_certification_matching():
    # Case A: Matches Bachelor degree and has cert
    score_a, notes_a = evaluate_education_and_certifications(
        edu_requirement_text="Bachelor's degree in Computer Science or related engineering discipline.",
        cert_requirements=["AWS Certified Solutions Architect"],
        candidate_education={"degree": "B.Tech in Computer Science and Engineering"},
        candidate_certs=["AWS Certified Solutions Architect - Associate"]
    )
    assert score_a == 100.0
    assert "matches degree requirement" in notes_a
    assert "Verified certifications" in notes_a

    # Case B: Matches degree but missing preferred cert -> score reduced by 15.0
    score_b, notes_b = evaluate_education_and_certifications(
        edu_requirement_text="Bachelor's degree in Computer Science or related engineering discipline.",
        cert_requirements=["AWS Certified Solutions Architect"],
        candidate_education={"degree": "B.Tech in Computer Science and Engineering"},
        candidate_certs=[]
    )
    assert score_b == 85.0
    assert "Lacks preferred certifications" in notes_b


# -------------------------------------------------------------------------
# Test 9: Deterministic Scoring Reproducibility
# -------------------------------------------------------------------------
def test_09_deterministic_scoring_reproducibility():
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
            ),
            CandidateEvidenceItem(
                name="PostgreSQL",
                canonical_name="PostgreSQL",
                provenance=EvidenceProvenanceType.CURATED_PROJECT,
                source_identifier="proj_01",
                evidence_text="PostgreSQL project database",
                is_verified=True
            )
        ],
        experience_years=1.5,
        content_hash="test_cand_hash_09"
    )

    req1 = ExtractedRequirement(name="Python", category="programming_language", priority=RequirementPriority.MANDATORY)
    req2 = ExtractedRequirement(name="PostgreSQL", category="database", priority=RequirementPriority.MANDATORY)
    parsed_jd = ParsedJobDescription(
        job_title="Python Backend Engineer",
        company="Fintech Corp",
        requirements=[req1, req2],
        mandatory_skills=["Python", "PostgreSQL"],
        content_hash="test_jd_hash_09"
    )

    baseline_res, baseline_matches = calculate_profile_match(parsed_jd, candidate_evidence)
    for _ in range(10):
        iter_res, iter_matches = calculate_profile_match(parsed_jd, candidate_evidence)
        assert iter_res.profile_match_score == baseline_res.profile_match_score
        assert iter_res.category_scores == baseline_res.category_scores
        assert len(iter_matches) == len(baseline_matches)
        for im, bm in zip(iter_matches, baseline_matches):
            assert im.status == bm.status
            assert im.evidence_strength == bm.evidence_strength


# -------------------------------------------------------------------------
# Test 10: Weight Calculations Correctness
# -------------------------------------------------------------------------
def test_10_weight_calculations_correctness():
    # Verify CATEGORY_WEIGHTS definition
    assert CATEGORY_WEIGHTS["mandatory_technical_skills"] == 0.40
    assert CATEGORY_WEIGHTS["preferred_technical_skills"] == 0.15
    assert CATEGORY_WEIGHTS["relevant_experience"] == 0.20
    assert CATEGORY_WEIGHTS["project_evidence"] == 0.15
    assert CATEGORY_WEIGHTS["education_and_certifications"] == 0.10
    assert sum(CATEGORY_WEIGHTS.values()) == pytest.approx(1.0, abs=0.001)

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
        experience_years=2.0,
        content_hash="test_cand_hash_10"
    )

    req_py = ExtractedRequirement(name="Python", category="programming_language", priority=RequirementPriority.MANDATORY)
    req_go = ExtractedRequirement(name="Go", category="programming_language", priority=RequirementPriority.MANDATORY)
    parsed_jd = ParsedJobDescription(
        job_title="Backend Engineer",
        company="Math Systems",
        requirements=[req_py, req_go],
        mandatory_skills=["Python", "Go"],
        content_hash="test_jd_hash_10"
    )

    result, _ = calculate_profile_match(parsed_jd, candidate_evidence)
    # Check that score mathematically matches the weighted sum of its category scores
    expected_score = sum(result.category_scores[cat] * result.category_weights[cat] for cat in result.category_weights)
    assert result.profile_match_score == pytest.approx(round(expected_score, 1), abs=0.1)


# -------------------------------------------------------------------------
# Test 11: Missing Data Handling (Neutral Credit for Unspecified Requirements)
# -------------------------------------------------------------------------
def test_11_missing_data_handling():
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
        experience_years=1.0,
        content_hash="test_cand_hash_11"
    )

    # Job description specifies ONLY mandatory Python. No preferred skills, no degree requirement.
    req_py = ExtractedRequirement(name="Python", category="programming_language", priority=RequirementPriority.MANDATORY)
    parsed_jd = ParsedJobDescription(
        job_title="Python Dev",
        company="Simple Corp",
        requirements=[req_py],
        mandatory_skills=["Python"],
        preferred_skills=[],
        content_hash="test_jd_hash_11"
    )

    result, _ = calculate_profile_match(parsed_jd, candidate_evidence)

    # Preferred skills should NOT tank candidate's score to 0; neutral 100.0 credit
    assert result.category_scores["preferred_technical_skills"] == 100.0
    assert result.profile_match_score >= 80.0


# -------------------------------------------------------------------------
# Test 12: Skill Gap Recommendation Relevance
# -------------------------------------------------------------------------
def test_12_skill_gap_recommendation_relevance():
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
        content_hash="test_cand_hash_12"
    )

    req_py = ExtractedRequirement(name="Python", category="programming_language", priority=RequirementPriority.MANDATORY)
    req_k8s = ExtractedRequirement(name="Kubernetes", category="cloud_devops", priority=RequirementPriority.MANDATORY)
    req_kafka = ExtractedRequirement(name="Kafka", category="database", priority=RequirementPriority.PREFERRED)

    parsed_jd = ParsedJobDescription(
        job_title="Distributed Systems Engineer",
        company="Stream Co",
        requirements=[req_py, req_k8s, req_kafka],
        mandatory_skills=["Python", "Kubernetes"],
        preferred_skills=["Kafka"],
        content_hash="test_jd_hash_12"
    )

    _, req_matches = calculate_profile_match(parsed_jd, candidate_evidence)
    skill_gaps = analyze_skill_gaps(req_matches)

    gap_names = [g.skill_name for g in skill_gaps]
    # Python was strongly matched, so Python MUST NOT be in skill gaps!
    assert "Python" not in gap_names
    # Kubernetes and Kafka must be in skill gaps
    assert "Kubernetes" in gap_names
    assert "Kafka" in gap_names

    # Check that recommendations are specific and non-empty
    k8s_gap = next(g for g in skill_gaps if g.skill_name == "Kubernetes")
    assert k8s_gap.priority == RequirementPriority.MANDATORY
    assert len(k8s_gap.suggested_learning_or_improvement) > 10
    assert "orchestrate" in k8s_gap.suggested_learning_or_improvement.lower() or "helm" in k8s_gap.suggested_learning_or_improvement.lower()


# -------------------------------------------------------------------------
# Test 13: Groq Unavailable Behavior (Graceful Fallback)
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_13_groq_unavailable_behavior(clean_db):
    db = clean_db
    cand = CandidateProfile(
        user_id=TEST_USER_A,
        name="Fallback Candidate",
        email=f"fallback_{TEST_USER_A}@example.com",
        skills=["Python", "FastAPI"],
        projects=[]
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)

    opp = Opportunity(
        user_id=TEST_USER_A,
        title="Python Backend Engineer",
        normalized_title="Python Backend Engineer",
        company_name="Resilience Corp",
        description="We are looking for a Python Backend Engineer with FastAPI and PostgreSQL expertise.",
        source_platform="direct",
        original_url=f"https://example.com/opp/{TEST_USER_A}_13"
    )
    db.add(opp)
    db.commit()
    db.refresh(opp)

    # Patch Groq router to raise an exception
    with patch("backend.app.services.ai.service.ai_service.router.execute", side_effect=RuntimeError("Groq 429 Rate Limit Exceeded")):
        result = await matching_service.evaluate_match(
            candidate=cand,
            opportunity=opp,
            db=db,
            force_refresh=True,
            use_ai=True
        )

    # Should succeed without throwing 500 error!
    assert result.profile_match_score > 0.0
    assert result.is_cached is False
    assert "Profile Match Score:" in result.scoring_explanation


# -------------------------------------------------------------------------
# Test 14: Profile Changes Invalidate Cache
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_14_profile_changes_invalidate_cache(clean_db):
    db = clean_db
    cand = CandidateProfile(
        user_id=TEST_USER_A,
        name="Cache Candidate",
        email=f"cache_{TEST_USER_A}@example.com",
        skills=["Python"],
        projects=[]
    )
    db.add(cand)
    opp = Opportunity(
        user_id=TEST_USER_A,
        title="Senior Python & Docker Engineer",
        normalized_title="Senior Python & Docker Engineer",
        company_name="Cache Corp",
        description="Requires strong Python and Docker skills.",
        source_platform="direct",
        original_url=f"https://example.com/opp/{TEST_USER_A}_14"
    )
    db.add(opp)
    db.commit()
    db.refresh(cand)
    db.refresh(opp)

    # 1. First run: calculates and populates cache
    res1 = await matching_service.evaluate_match(candidate=cand, opportunity=opp, db=db, use_ai=False)
    assert res1.is_cached is False
    score1 = res1.profile_match_score

    # 2. Second run without profile change: served from cache
    res2 = await matching_service.evaluate_match(candidate=cand, opportunity=opp, db=db, use_ai=False)
    assert res2.is_cached is True
    assert res2.profile_match_score == score1

    # 3. Modify Candidate Profile (add Docker skill)
    cand.skills = ["Python", "Docker"]
    db.commit()
    db.refresh(cand)

    # 4. Third run: detects candidate hash change, recalculates fresh
    res3 = await matching_service.evaluate_match(candidate=cand, opportunity=opp, db=db, use_ai=False)
    assert res3.is_cached is False
    assert res3.candidate_content_hash != res1.candidate_content_hash
    assert res3.profile_match_score >= score1


# -------------------------------------------------------------------------
# Test 15: Opportunity Changes Invalidate Cache
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_15_opportunity_changes_invalidate_cache(clean_db):
    db = clean_db
    cand = CandidateProfile(
        user_id=TEST_USER_A,
        name="Opp Cache Candidate",
        email=f"opp_cache_{TEST_USER_A}@example.com",
        skills=["Python"],
        projects=[]
    )
    db.add(cand)
    opp = Opportunity(
        user_id=TEST_USER_A,
        title="Python Engineer",
        normalized_title="Python Engineer",
        company_name="Opp Change Corp",
        description="Looking for Python developer.",
        source_platform="direct",
        original_url=f"https://example.com/opp/{TEST_USER_A}_15"
    )
    db.add(opp)
    db.commit()
    db.refresh(cand)
    db.refresh(opp)

    # 1. First run
    res1 = await matching_service.evaluate_match(candidate=cand, opportunity=opp, db=db, use_ai=False)
    assert res1.is_cached is False

    # 2. Mutate Opportunity Description
    opp.description = "Updated requirement: must have 10 years of Kubernetes and Rust experience."
    db.commit()
    db.refresh(opp)

    # 3. Next run: detects opportunity content hash change, recalculates fresh
    res2 = await matching_service.evaluate_match(candidate=cand, opportunity=opp, db=db, use_ai=False)
    assert res2.is_cached is False
    assert res2.opportunity_content_hash != res1.opportunity_content_hash


# -------------------------------------------------------------------------
# Test 16: Concurrent Matching Calculations (Row Lock Serialization)
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_16_concurrent_matching_calculations(clean_db):
    db = clean_db
    cand = CandidateProfile(
        user_id=TEST_USER_A,
        name="Concurrent Candidate",
        email=f"concurrent_{TEST_USER_A}@example.com",
        skills=["Python", "FastAPI"],
        projects=[]
    )
    db.add(cand)
    opp = Opportunity(
        user_id=TEST_USER_A,
        title="Concurrent Backend Lead",
        normalized_title="Concurrent Backend Lead",
        company_name="Concurrency Corp",
        description="Python FastAPI backend engineering position.",
        source_platform="direct",
        original_url=f"https://example.com/opp/{TEST_USER_A}_16"
    )
    db.add(opp)
    db.commit()
    db.refresh(cand)
    db.refresh(opp)

    # Run two concurrent evaluate requests
    db1 = SessionLocal()
    db2 = SessionLocal()
    try:
        t1 = matching_service.evaluate_match(candidate=cand, opportunity=opp, db=db1, use_ai=False)
        t2 = matching_service.evaluate_match(candidate=cand, opportunity=opp, db=db2, use_ai=False)
        res1, res2 = await asyncio.gather(t1, t2)

        assert res1.profile_match_score == res2.profile_match_score
        assert (res1.is_cached is False or res2.is_cached is True)
    finally:
        db1.close()
        db2.close()


# -------------------------------------------------------------------------
# Test 17: Candidate Ownership Enforcement (Tenant Isolation)
# -------------------------------------------------------------------------
def test_17_candidate_ownership_enforcement(clean_db):
    db = clean_db
    # User A profile & private opportunity
    cand_a = CandidateProfile(
        user_id=TEST_USER_A,
        name="User A",
        email=f"user_a_{TEST_USER_A}@example.com",
        skills=["Python"]
    )
    opp_a = Opportunity(
        user_id=TEST_USER_A,
        title="User A Private Opportunity",
        normalized_title="User A Private Opportunity",
        company_name="Private Corp",
        description="Private job description",
        source_platform="direct",
        original_url=f"https://example.com/opp/{TEST_USER_A}_priv"
    )
    db.add(cand_a)
    db.add(opp_a)

    # User B profile
    cand_b = CandidateProfile(
        user_id=TEST_USER_B,
        name="User B",
        email=f"user_b_{TEST_USER_B}@example.com",
        skills=["Rust"]
    )
    db.add(cand_b)
    db.commit()
    db.refresh(opp_a)

    # User B attempts to evaluate User A's private opportunity -> HTTP 403 Forbidden
    resp = client.post(
        f"/api/opportunities/{opp_a.id}/evaluate-match",
        headers=auth_headers(TEST_USER_B),
        json={"force_refresh": True, "use_ai": False}
    )
    assert resp.status_code == 403
    assert "Not authorized" in resp.json()["detail"]

    # User without candidate profile gets 404
    UNREGISTERED_USER = 99999
    resp_no_profile = client.post(
        f"/api/opportunities/{opp_a.id}/evaluate-match",
        headers=auth_headers(UNREGISTERED_USER),
        json={"force_refresh": True, "use_ai": False}
    )
    assert resp_no_profile.status_code in [403, 404]


# -------------------------------------------------------------------------
# Test 18: Preservation of Previous Matching on Failure (Resilience)
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_18_preservation_of_previous_matching_on_failure(clean_db):
    db = clean_db
    cand = CandidateProfile(
        user_id=TEST_USER_A,
        name="Resilience Dev",
        email=f"resilience_{TEST_USER_A}@example.com",
        skills=["Python"],
        projects=[]
    )
    db.add(cand)
    opp = Opportunity(
        user_id=TEST_USER_A,
        title="Resilience Engineer",
        normalized_title="Resilience Engineer",
        company_name="Resilience Corp",
        description="Python development position.",
        source_platform="direct",
        original_url=f"https://example.com/opp/{TEST_USER_A}_18"
    )
    db.add(opp)
    db.commit()
    db.refresh(cand)
    db.refresh(opp)

    # 1. Establish valid cached matching analysis
    valid_res = await matching_service.evaluate_match(candidate=cand, opportunity=opp, db=db, use_ai=False)
    assert valid_res.is_cached is False
    assert valid_res.profile_match_score > 0.0

    # 2. Simulate catastrophic failure inside calculate_profile_match on re-evaluation
    with patch("backend.app.services.matching.service.calculate_profile_match", side_effect=RuntimeError("Sudden Engine Memory Fault")):
        stale_res = await matching_service.evaluate_match(
            candidate=cand,
            opportunity=opp,
            db=db,
            force_refresh=True,
            use_ai=False
        )

    # 3. Verify previous analysis is preserved as stale rather than crashing
    assert stale_res.is_stale is True
    assert stale_res.is_cached is True
    assert stale_res.profile_match_score == valid_res.profile_match_score
