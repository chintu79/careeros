import time
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.app.main import app
from backend.app.database import get_db, SessionLocal
from backend.app.models.candidate import CandidateProfile
from backend.app.models.opportunity import Opportunity
from backend.app.models.candidate_opportunity_match import CandidateOpportunityMatch
from backend.app.models.preferences import UserPreferences
from backend.app.core.auth import create_access_token
from backend.app.services.matching import matching_service
from backend.app.services.discovery_search_service import execute_intelligent_discovery_search


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


def test_database_composite_foreign_key_enforcement(db_session: Session):
    """
    Phase 1 Test:
    Verify that the composite foreign key (candidate_id, user_id) on candidate_opportunity_matches
    strictly prevents inserting a record where user_id does not match the candidate's actual user_id.
    """
    test_uid = 88001
    cand = CandidateProfile(
        user_id=test_uid,
        name="Candidate Identity Test",
        email="identity_test@careeros.internal"
    )
    db_session.add(cand)
    db_session.commit()
    db_session.refresh(cand)

    opp = db_session.query(Opportunity).first()
    assert opp is not None

    try:
        # Attempt 1: Malicious / mismatched insert (candidate_id=cand.id, but user_id=99999)
        mismatched_match = CandidateOpportunityMatch(
            user_id=99999,  # Deliberately mismatched user_id
            candidate_id=cand.id,
            opportunity_id=opp.id,
            match_score=85.0,
            candidate_content_hash="test_cand_hash",
            opportunity_content_hash="test_opp_hash",
            engine_version="1.9.0"
        )
        db_session.add(mismatched_match)
        with pytest.raises(IntegrityError) as exc_info:
            db_session.commit()
        db_session.rollback()
        assert "fk_cand_opp_match_cand_user" in str(exc_info.value) or "foreign key" in str(exc_info.value).lower()

        # Attempt 2: Valid insert with matching (candidate_id=cand.id, user_id=cand.user_id)
        valid_match = CandidateOpportunityMatch(
            user_id=cand.user_id,
            candidate_id=cand.id,
            opportunity_id=opp.id,
            match_score=92.5,
            candidate_content_hash="test_cand_hash_valid",
            opportunity_content_hash="test_opp_hash_valid",
            engine_version="1.9.0"
        )
        db_session.add(valid_match)
        db_session.commit()

        stored = (
            db_session.query(CandidateOpportunityMatch)
            .filter(
                CandidateOpportunityMatch.user_id == cand.user_id,
                CandidateOpportunityMatch.opportunity_id == opp.id
            )
            .first()
        )
        assert stored is not None
        assert stored.match_score == 92.5
    finally:
        db_session.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == cand.user_id).delete(synchronize_session=False)
        db_session.query(CandidateProfile).filter(CandidateProfile.id == cand.id).delete(synchronize_session=False)
        db_session.commit()


@pytest.mark.asyncio
async def test_candidate_aware_search_ranking_divergence(client: TestClient, db_session: Session):
    """
    Phase 3 & Phase 7 Test:
    Candidate Alpha (Python specialist) and Candidate Beta (Java Android specialist)
    must experience distinct, personalized rankings on the exact same opportunity catalog.
    Neither candidate must receive the other candidate's scores.
    """
    ts = int(time.time() * 1000)
    uid_alpha = 88101
    uid_beta = 88102

    token_alpha = create_access_token(user_id=uid_alpha)
    token_beta = create_access_token(user_id=uid_beta)

    headers_alpha = {"Authorization": f"Bearer {token_alpha}"}
    headers_beta = {"Authorization": f"Bearer {token_beta}"}

    # 1. Setup Candidate Alpha (Python Focus)
    cand_alpha = CandidateProfile(
        user_id=uid_alpha,
        name="Alpha Python Engineer",
        email="alpha@python.internal",
        skills=[
            {"name": "Python", "level": "advanced", "category": "language"},
            {"name": "FastAPI", "level": "advanced", "category": "framework"},
            {"name": "PostgreSQL", "level": "advanced", "category": "database"}
        ],
        projects=[
            {
                "title": "Argus AI Discovery",
                "tech_stack": ["Python", "FastAPI", "PostgreSQL"],
                "description": "High throughput async backend"
            }
        ]
    )
    # 2. Setup Candidate Beta (Java / Android Focus)
    cand_beta = CandidateProfile(
        user_id=uid_beta,
        name="Beta Android Engineer",
        email="beta@android.internal",
        skills=[
            {"name": "Java", "level": "advanced", "category": "language"},
            {"name": "Android", "level": "advanced", "category": "framework"},
            {"name": "Spring Boot", "level": "advanced", "category": "framework"}
        ],
        projects=[
            {
                "title": "Mobile Banking Android App",
                "tech_stack": ["Java", "Android", "Spring Boot"],
                "description": "Native Android finance app"
            }
        ]
    )
    db_session.add_all([cand_alpha, cand_beta])
    db_session.commit()
    db_session.refresh(cand_alpha)
    db_session.refresh(cand_beta)

    # 3. Create two public opportunities
    opp_python = Opportunity(
        title="Python Backend Engineering Intern",
        normalized_title="Python Backend Engineering Intern",
        company_name="PyTech Global",
        original_url=f"https://careeros.internal/jobs/python-intern-{ts}",
        source_platform="greenhouse",
        location="Remote",
        workplace_type="remote",
        employment_type="internship",
        status="verified",
        eligibility_status="eligible",
        required_skills=["Python", "FastAPI", "PostgreSQL"],
        description="Build async APIs using Python, FastAPI, and PostgreSQL."
    )
    opp_java = Opportunity(
        title="Android Native App Developer Intern",
        normalized_title="Android Native App Developer Intern",
        company_name="DroidWorks Corp",
        original_url=f"https://careeros.internal/jobs/android-intern-{ts}",
        source_platform="greenhouse",
        location="Remote",
        workplace_type="remote",
        employment_type="internship",
        status="verified",
        eligibility_status="eligible",
        required_skills=["Java", "Android", "Spring Boot"],
        description="Build native Android applications with Java and Spring Boot backend."
    )
    db_session.add_all([opp_python, opp_java])
    db_session.commit()
    db_session.refresh(opp_python)
    db_session.refresh(opp_java)

    try:
        # 4. Evaluate both opportunities for both candidates
        await matching_service.evaluate_match(cand_alpha, opp_python, db_session, use_ai=False)
        await matching_service.evaluate_match(cand_alpha, opp_java, db_session, use_ai=False)

        await matching_service.evaluate_match(cand_beta, opp_python, db_session, use_ai=False)
        await matching_service.evaluate_match(cand_beta, opp_java, db_session, use_ai=False)

        # 5. Search opportunities as Candidate Alpha
        res_alpha = client.get(
            "/api/opportunities?sort_by=match_score&sort_order=desc&tab=all&limit=50",
            headers=headers_alpha
        )
        assert res_alpha.status_code == 200, res_alpha.text
        items_alpha = res_alpha.json()["items"]

        alpha_py_item = next(it for it in items_alpha if it["id"] == opp_python.id)
        alpha_java_item = next(it for it in items_alpha if it["id"] == opp_java.id)

        # Candidate Alpha: Python score must be high (> 80%), Java score must be lower
        assert alpha_py_item["match_score"] >= 80.0
        assert alpha_py_item["match_score"] > alpha_java_item["match_score"]

        # In Candidate Alpha's sorted list, Python must appear before Java
        alpha_py_idx = next(i for i, it in enumerate(items_alpha) if it["id"] == opp_python.id)
        alpha_java_idx = next(i for i, it in enumerate(items_alpha) if it["id"] == opp_java.id)
        assert alpha_py_idx < alpha_java_idx, f"Alpha ranking inverted: Py@{alpha_py_idx}, Java@{alpha_java_idx}"

        # Verify structured ranking reasons
        assert alpha_py_item["ranking_reasons"]["primary_factor"] == "evaluated_candidate_match"
        assert alpha_py_item["ranking_reasons"]["is_evaluated"] is True
        assert round(alpha_py_item["ranking_reasons"]["match_score"]) == alpha_py_item["match_score"]

        # 6. Search opportunities as Candidate Beta
        res_beta = client.get(
            "/api/opportunities?sort_by=match_score&sort_order=desc&tab=all&limit=50",
            headers=headers_beta
        )
        assert res_beta.status_code == 200, res_beta.text
        items_beta = res_beta.json()["items"]

        beta_py_item = next(it for it in items_beta if it["id"] == opp_python.id)
        beta_java_item = next(it for it in items_beta if it["id"] == opp_java.id)

        # Candidate Beta: Java score must be high (> 80%), Python score must be lower
        assert beta_java_item["match_score"] >= 80.0
        assert beta_java_item["match_score"] > beta_py_item["match_score"]

        # In Candidate Beta's sorted list, Java must appear before Python
        beta_java_idx = next(i for i, it in enumerate(items_beta) if it["id"] == opp_java.id)
        beta_py_idx = next(i for i, it in enumerate(items_beta) if it["id"] == opp_python.id)
        assert beta_java_idx < beta_py_idx, f"Beta ranking inverted: Java@{beta_java_idx}, Py@{beta_py_idx}"

        # 7. Candidate Isolation Verification
        assert alpha_java_item["match_score"] != beta_java_item["match_score"]
        assert alpha_py_item["match_score"] != beta_py_item["match_score"]
    finally:
        db_session.query(CandidateOpportunityMatch).filter(
            CandidateOpportunityMatch.opportunity_id.in_([opp_python.id, opp_java.id])
        ).delete(synchronize_session=False)
        db_session.query(Opportunity).filter(Opportunity.id.in_([opp_python.id, opp_java.id])).delete(synchronize_session=False)
        db_session.query(CandidateProfile).filter(CandidateProfile.id.in_([cand_alpha.id, cand_beta.id])).delete(synchronize_session=False)
        db_session.commit()


def test_candidate_aware_min_score_filter_isolation(client: TestClient, db_session: Session):
    """
    Verify that min_score filter operates exclusively on the authenticated candidate's score.
    Candidate Alpha with 90% score sees the job; Candidate Beta with 30% score does not.
    """
    ts = int(time.time() * 1000)
    uid_alpha = 88201
    uid_beta = 88202

    token_alpha = create_access_token(user_id=uid_alpha)
    token_beta = create_access_token(user_id=uid_beta)

    cand_alpha = CandidateProfile(user_id=uid_alpha, name="Score Iso Alpha")
    cand_beta = CandidateProfile(user_id=uid_beta, name="Score Iso Beta")
    db_session.add_all([cand_alpha, cand_beta])
    db_session.commit()
    db_session.refresh(cand_alpha)
    db_session.refresh(cand_beta)

    opp = Opportunity(
        title="Selective Threshold Intern",
        normalized_title="Selective Threshold Intern",
        company_name="Selective Corp",
        original_url=f"https://careeros.internal/jobs/selective-intern-{ts}",
        source_platform="greenhouse",
        employment_type="internship",
        status="verified",
        match_score=99.0  # Legacy shared score that should NOT be used
    )
    db_session.add(opp)
    db_session.commit()
    db_session.refresh(opp)

    try:
        # Candidate Alpha gets high match (88.0)
        match_alpha = CandidateOpportunityMatch(
            user_id=uid_alpha,
            candidate_id=cand_alpha.id,
            opportunity_id=opp.id,
            match_score=88.0,
            candidate_content_hash="hash_a",
            opportunity_content_hash="hash_o",
            engine_version="1.9.0"
        )
        # Candidate Beta gets low match (42.0)
        match_beta = CandidateOpportunityMatch(
            user_id=uid_beta,
            candidate_id=cand_beta.id,
            opportunity_id=opp.id,
            match_score=42.0,
            candidate_content_hash="hash_b",
            opportunity_content_hash="hash_o",
            engine_version="1.9.0"
        )
        db_session.add_all([match_alpha, match_beta])
        db_session.commit()

        # Alpha searches with min_score=75 -> must include opp
        res_a = client.get(
            "/api/opportunities?min_score=75.0&tab=all",
            headers={"Authorization": f"Bearer {token_alpha}"}
        )
        assert res_a.status_code == 200
        ids_a = [item["id"] for item in res_a.json()["items"]]
        assert opp.id in ids_a

        # Beta searches with min_score=75 -> must exclude opp
        res_b = client.get(
            "/api/opportunities?min_score=75.0&tab=all",
            headers={"Authorization": f"Bearer {token_beta}"}
        )
        assert res_b.status_code == 200
        ids_b = [item["id"] for item in res_b.json()["items"]]
        assert opp.id not in ids_b
    finally:
        db_session.query(CandidateOpportunityMatch).filter(
            CandidateOpportunityMatch.opportunity_id == opp.id
        ).delete(synchronize_session=False)
        db_session.query(Opportunity).filter(Opportunity.id == opp.id).delete(synchronize_session=False)
        db_session.query(CandidateProfile).filter(CandidateProfile.id.in_([cand_alpha.id, cand_beta.id])).delete(synchronize_session=False)
        db_session.commit()


def test_unevaluated_candidate_receives_neutral_state_in_discovery(client: TestClient, db_session: Session):
    """
    Phase 4 Test:
    When an un-evaluated candidate searches discovery, public opportunities that have
    been evaluated by other candidates must NOT leak those other candidates' scores.
    The un-evaluated candidate receives clean neutral match status.
    """
    ts = int(time.time() * 1000)
    uid_other = 88301
    uid_new = 88302

    cand_other = CandidateProfile(user_id=uid_other, name="Other Candidate")
    cand_new = CandidateProfile(user_id=uid_new, name="New Unevaluated Candidate")
    db_session.add_all([cand_other, cand_new])
    db_session.commit()
    db_session.refresh(cand_other)
    db_session.refresh(cand_new)

    opp = Opportunity(
        title="Public Neutral Check Intern",
        normalized_title="Public Neutral Check Intern",
        company_name="Neutral Corp",
        original_url=f"https://careeros.internal/jobs/neutral-intern-{ts}",
        source_platform="greenhouse",
        employment_type="internship",
        status="verified",
        match_score=95.0
    )
    db_session.add(opp)
    db_session.commit()
    db_session.refresh(opp)

    try:
        # Other candidate has a high score recorded
        match_other = CandidateOpportunityMatch(
            user_id=uid_other,
            candidate_id=cand_other.id,
            opportunity_id=opp.id,
            match_score=97.0,
            candidate_content_hash="h1",
            opportunity_content_hash="h2",
            engine_version="1.9.0"
        )
        db_session.add(match_other)
        db_session.commit()

        token_new = create_access_token(user_id=uid_new)
        res = client.get(
            f"/api/opportunities?tab=all",
            headers={"Authorization": f"Bearer {token_new}"}
        )
        assert res.status_code == 200
        items = res.json()["items"]
        target = next((it for it in items if it["id"] == opp.id), None)
        assert target is not None

        # Must NOT see Other Candidate's 97.0 score or legacy 95.0
        assert target["match_score"] != 97.0
        assert target["match_score"] != 95.0
    finally:
        db_session.query(CandidateOpportunityMatch).filter(
            CandidateOpportunityMatch.opportunity_id == opp.id
        ).delete(synchronize_session=False)
        db_session.query(Opportunity).filter(Opportunity.id == opp.id).delete(synchronize_session=False)
        db_session.query(CandidateProfile).filter(CandidateProfile.id.in_([cand_other.id, cand_new.id])).delete(synchronize_session=False)
        db_session.commit()


def test_curated_recommendations_candidate_personalization(client: TestClient, db_session: Session):
    """
    Phase 4 Test:
    GET /api/opportunities/recommendations must personalize Section 1 ('Best Matches')
    and Section 7 ('Based on My Projects') according to the authenticated candidate.
    """
    ts = int(time.time() * 1000)
    uid_alpha = 88401
    uid_beta = 88402

    token_alpha = create_access_token(user_id=uid_alpha)
    token_beta = create_access_token(user_id=uid_beta)

    cand_alpha = CandidateProfile(
        user_id=uid_alpha,
        name="Personalized Alpha",
        projects=[{"title": "Distributed Kafka Microservices", "tech_stack": ["Kafka", "Go"]}]
    )
    cand_beta = CandidateProfile(
        user_id=uid_beta,
        name="Personalized Beta",
        projects=[{"title": "Computer Vision Classifier", "tech_stack": ["PyTorch", "OpenCV"]}]
    )
    db_session.add_all([cand_alpha, cand_beta])
    db_session.commit()
    db_session.refresh(cand_alpha)
    db_session.refresh(cand_beta)

    # Opportunities
    opp_kafka = Opportunity(
        title="Go Kafka Systems Intern",
        normalized_title="Go Kafka Systems Intern",
        company_name="StreamTech",
        original_url=f"https://careeros.internal/jobs/kafka-intern-{ts}",
        source_platform="greenhouse",
        employment_type="internship",
        status="verified",
        eligibility_status="eligible",
        required_skills=["Kafka", "Go"],
        description="High throughput event streaming with Kafka and Go."
    )
    opp_cv = Opportunity(
        title="Computer Vision AI Intern",
        normalized_title="Computer Vision AI Intern",
        company_name="VisionAI Labs",
        original_url=f"https://careeros.internal/jobs/cv-intern-{ts}",
        source_platform="greenhouse",
        employment_type="internship",
        status="verified",
        eligibility_status="eligible",
        required_skills=["PyTorch", "OpenCV"],
        description="Deep learning object detection with PyTorch and OpenCV."
    )
    db_session.add_all([opp_kafka, opp_cv])
    db_session.commit()
    db_session.refresh(opp_kafka)
    db_session.refresh(opp_cv)

    try:
        # Matches: Alpha high for Kafka (85.0), Beta high for CV (90.0)
        match_a_k = CandidateOpportunityMatch(
            user_id=uid_alpha, candidate_id=cand_alpha.id, opportunity_id=opp_kafka.id,
            match_score=85.0, candidate_content_hash="h", opportunity_content_hash="h", engine_version="1.9.0"
        )
        match_b_cv = CandidateOpportunityMatch(
            user_id=uid_beta, candidate_id=cand_beta.id, opportunity_id=opp_cv.id,
            match_score=90.0, candidate_content_hash="h", opportunity_content_hash="h", engine_version="1.9.0"
        )
        db_session.add_all([match_a_k, match_b_cv])
        db_session.commit()

        # 1. Candidate Alpha Recommendations
        res_a = client.get("/api/opportunities/recommendations", headers={"Authorization": f"Bearer {token_alpha}"})
        assert res_a.status_code == 200
        data_a = res_a.json()
        best_a_ids = [c["id"] for c in data_a["best_matches"]]
        assert opp_kafka.id in best_a_ids
        assert opp_cv.id not in best_a_ids  # Alpha has 0 score for CV, cannot be in best matches
        assert data_a["meta"]["candidate_name"] == "Personalized Alpha"

        # 2. Candidate Beta Recommendations
        res_b = client.get("/api/opportunities/recommendations", headers={"Authorization": f"Bearer {token_beta}"})
        assert res_b.status_code == 200
        data_b = res_b.json()
        best_b_ids = [c["id"] for c in data_b["best_matches"]]
        assert opp_cv.id in best_b_ids
        assert opp_kafka.id not in best_b_ids  # Beta has 0 score for Kafka, cannot be in best matches
        assert data_b["meta"]["candidate_name"] == "Personalized Beta"
    finally:
        db_session.query(CandidateOpportunityMatch).filter(
            CandidateOpportunityMatch.opportunity_id.in_([opp_kafka.id, opp_cv.id])
        ).delete(synchronize_session=False)
        db_session.query(Opportunity).filter(Opportunity.id.in_([opp_kafka.id, opp_cv.id])).delete(synchronize_session=False)
        db_session.query(CandidateProfile).filter(CandidateProfile.id.in_([cand_alpha.id, cand_beta.id])).delete(synchronize_session=False)
        db_session.commit()


@pytest.mark.asyncio
async def test_bounded_latency_and_query_efficiency_benchmark(db_session: Session):
    """
    Phase 8 Benchmark:
    Measure latency and cache performance for candidate-aware discovery search.
    Assert that warm candidate-aware discovery queries execute in under 100ms.
    """
    cand = db_session.query(CandidateProfile).first()
    assert cand is not None

    # Warmup queries to populate cache for pool
    for _ in range(4):
        await execute_intelligent_discovery_search(
            db=db_session,
            tab="recommended",
            sort_by="match_score",
            sort_order="desc",
            limit=25,
            user_id=cand.user_id
        )

    # Measure 5 consecutive searches
    latencies = []
    for _ in range(5):
        t0 = time.perf_counter()
        results, total = await execute_intelligent_discovery_search(
            db=db_session,
            tab="recommended",
            sort_by="match_score",
            sort_order="desc",
            limit=25,
            user_id=cand.user_id
        )
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)

    avg_ms = sum(latencies) / len(latencies)
    print(f"\n[Benchmark] Candidate-Aware Discovery Latency (5 runs): avg {avg_ms:.2f}ms (min {min(latencies):.2f}ms, max {max(latencies):.2f}ms)")
    assert avg_ms < 100.0, f"Candidate-aware search too slow: {avg_ms:.2f}ms (threshold 100ms)"


def test_tamper_resistance_and_header_isolation(client: TestClient, db_session: Session):
    """
    Phase 7 Test:
    Verify that client-injected headers (e.g. attempting to override X-User-Id)
    are strictly rejected, preventing identity spoofing and unauthorized access
    to other candidates' match scores.
    """
    # Direct X-User-Id spoofing without internal secret must fail with 401
    spoof_res = client.get(
        "/api/opportunities",
        headers={"X-User-Id": "1"}
    )
    assert spoof_res.status_code == 401
    assert "Untrusted client identity" in spoof_res.json()["detail"]
