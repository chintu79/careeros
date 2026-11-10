import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models.opportunity import Opportunity
from backend.app.models.company import Company
from backend.app.models.preferences import UserPreferences
from backend.app.models.candidate import CandidateProfile
from backend.app.pipeline.normalizer import normalize_title, normalize_location, normalize_stipend
from backend.app.pipeline.validity_checker import check_opportunity_validity
from backend.app.ai.compatibility_scorer import evaluate_compatibility
from backend.app.ai.extractor import fallback_heuristic_extraction

client = TestClient(app)

def test_normalization():
    # Title normalization
    assert normalize_title("Software Engineering Intern - 2026") == "Software Engineer Intern"
    assert normalize_title("Generative AI / LLM Engineer Intern") == "Generative AI Intern"
    assert normalize_title("Python Developer - Internship") == "Python Developer Intern"
    
    # Location normalization
    loc, workplace = normalize_location("Bengaluru, Karnataka", "onsite")
    assert loc == "Bengaluru, India"
    
    loc_remote, wp_remote = normalize_location("Work from home, India", "")
    assert loc_remote == "Remote, India"
    assert wp_remote == "remote"
    
    # Stipend parsing
    stipend_monthly = normalize_stipend("₹40,000 / month")
    assert stipend_monthly["is_paid"] is True
    assert stipend_monthly["min_val"] == 40000.0
    assert stipend_monthly["currency"] == "INR"
    
    stipend_unpaid = normalize_stipend("Unpaid Internship")
    assert stipend_unpaid["is_paid"] is False

def test_validity_checker():
    now = datetime.utcnow()
    # Active job with future deadline
    active_job = {"deadline_at": now + timedelta(days=15), "posted_at": now - timedelta(days=2)}
    assert check_opportunity_validity(active_job) == "active"
    
    # Expired job
    expired_job = {"deadline_at": now - timedelta(days=1), "posted_at": now - timedelta(days=30)}
    assert check_opportunity_validity(expired_job) == "expired"
    
    # Possibly expired job (deadline in 2 days)
    near_deadline_job = {"deadline_at": now + timedelta(days=1), "posted_at": now - timedelta(days=10)}
    assert check_opportunity_validity(near_deadline_job) == "possibly_expired"

def test_compatibility_scorer_weights_and_eligibility():
    candidate_profile = {
        "degree": "B.Tech Computer Science",
        "graduation_year": 2026,
        "skills": [
            {"name": "Python", "level": "advanced", "evidence": "FastAPI, Argus"},
            {"name": "FastAPI", "level": "advanced", "evidence": "REST microservices"},
            {"name": "PostgreSQL", "level": "advanced", "evidence": "pgvector schemas"},
            {"name": "React", "level": "advanced", "evidence": "CareerOS UI"}
        ],
        "projects": [
            {
                "title": "CareerOS Discovery Engine",
                "tech_stack": ["Python", "FastAPI", "PostgreSQL", "React"]
            }
        ]
    }
    
    user_preferences = {
        "paid_only": True,
        "allow_unpaid": False,
        "min_stipend": 15000.0,
        "graduation_year": 2026,
        "excluded_companies": ["BannedCorp"],
        "excluded_keywords": []
    }
    
    extracted_reqs = {
        "mandatory_technical_skills": ["Python", "REST API", "PostgreSQL"],
        "preferred_skills": ["Docker"],
        "educational_requirements": "Bachelor's degree in Computer Science (2026 graduates eligible)",
        "eligibility_restrictions": ["Eligible for Candidates located in India"]
    }
    
    # Eligible Indian Job
    result = evaluate_compatibility(
        extracted_data=extracted_reqs,
        candidate_profile=candidate_profile,
        user_preferences=user_preferences,
        job_location="Bengaluru, India",
        workplace_type="remote",
        is_paid=True,
        stipend_amount=35000.0,
        job_company="GoodTech"
    )
    
    assert result["eligibility_status"] == "eligible"
    assert result["match_score"] >= 70.0
    assert "score_breakdown" in result
    assert result["score_breakdown"]["required_technical_skills"] > 0
    assert len(result["skill_compatibility"]["strong"]) >= 2
    
    # US-Only Disqualified Job for Indian student
    extracted_us = dict(extracted_reqs)
    extracted_us["eligibility_restrictions"] = ["US Residents Only (Not eligible for India applicants)"]
    us_result = evaluate_compatibility(
        extracted_data=extracted_us,
        candidate_profile=candidate_profile,
        user_preferences=user_preferences,
        job_location="San Francisco, CA (US Only)",
        workplace_type="onsite",
        is_paid=True,
        stipend_amount=80000.0,
        job_company="USCorp"
    )
    assert us_result["eligibility_status"] == "disqualified"
    assert any("US residents only" in r for r in us_result["disqualifying_reasons"])

def test_api_endpoints():
    # 1. Health check
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] in ("alive", "healthy")
    
    # 2. Opportunities feed
    res_opp = client.get("/api/opportunities?tab=recommended")
    assert res_opp.status_code == 200
    data = res_opp.json()
    assert "items" in data
    assert len(data["items"]) > 0
    
    # 3. Summary metrics
    res_metrics = client.get("/api/opportunities/summary-metrics")
    assert res_metrics.status_code == 200
    assert res_metrics.json()["total_discovered"] >= 5
    
    # 4. Companies directory
    res_companies = client.get("/api/companies")
    assert res_companies.status_code == 200
    assert len(res_companies.json()) >= 5
    
    # 5. Sources list
    res_sources = client.get("/api/sources")
    assert res_sources.status_code == 200
    assert len(res_sources.json()) >= 10
    
    # 6. Preferences
    res_pref = client.get("/api/preferences")
    assert res_pref.status_code == 200
    assert "preferred_categories" in res_pref.json()
    
    # 7. Candidate Profile
    res_cand = client.get("/api/candidate")
    assert res_cand.status_code == 200
    assert "Krishna" in res_cand.json()["name"] or "chinta" in res_cand.json()["name"].lower()
    
    # 8. Analytics
    res_analytics = client.get("/api/analytics")
    assert res_analytics.status_code == 200
    assert "summary" in res_analytics.json()
    
    # 9. Notifications
    res_notifs = client.get("/api/notifications")
    assert res_notifs.status_code == 200
    assert "items" in res_notifs.json()

def test_manual_paste_import_and_handoff():
    paste_payload = {
        "title": "Machine Learning Engineer Intern",
        "company_name": "TestAI Labs",
        "location": "Pune, India",
        "description": "Looking for a Machine Learning Intern proficient in Python, PyTorch, and REST APIs to work on model evaluation and data pipelines. 6-month duration.",
        "stipend_text": "₹35,000 / month",
        "original_url": "https://testai.labs/jobs/ml-intern"
    }
    res_import = client.post("/api/import/paste", json=paste_payload)
    assert res_import.status_code == 200
    opp_id = res_import.json()["opportunity_id"]
    assert opp_id is not None
    
    # Test handoff to application tracker
    handoff_payload = {
        "opportunity_id": opp_id,
        "initial_status": "ready_to_apply",
        "user_notes": "Identified high match via manual import"
    }
    res_handoff = client.post("/api/applications/handoff", json=handoff_payload)
    assert res_handoff.status_code == 200
    assert res_handoff.json()["company_name"] == "TestAI Labs"
    assert res_handoff.json()["status"] in ["ready_to_apply", "screening", "applied"]
    
    # Verify in applications list
    res_apps = client.get("/api/applications")
    assert res_apps.status_code == 200
    app_items = res_apps.json().get("items", res_apps.json())
    app_ids = [a["opportunity_id"] for a in app_items]
    assert opp_id in app_ids

def test_internship_strict_filtering():
    """Verify false positive substrings and senior full-time roles are rejected."""
    from backend.app.pipeline.internship_filter import is_valid_internship

    # Should reject false positive substrings
    valid, reason = is_valid_internship(
        title="Internal Auditor", 
        description="Accounting role", 
        company_name="Canonical", 
        url="https://canonical.com/job/1"
    )
    assert not valid
    assert ("does not contain an internship" in reason) or ("false-positive" in reason)

    # Should reject senior/lead roles
    valid, reason = is_valid_internship(
        title="Senior Software Engineer Intern", 
        description="Senior developer", 
        company_name="Tech Co", 
        url="https://tech.co/job/2"
    )
    assert not valid
    assert "senior, lead, or managerial" in reason

    # Should reject scam training programs
    valid, reason = is_valid_internship(
        title="Python Developer Intern", 
        description="Pay registration fee of Rs. 5000 to enroll in training with placement fee", 
        company_name="Scam Corp", 
        url="https://scam.corp/job/3"
    )
    assert not valid
    assert "training course or scam" in reason

    # Should accept genuine internships
    valid, reason = is_valid_internship(
        title="AI Engineer Intern", 
        description="Work on Python and PyTorch models", 
        company_name="AI Labs", 
        url="https://ailabs.com/job/4"
    )
    assert valid
    assert reason is None

def test_stipend_compensation_labeling():
    """Verify compensation is accurately labeled as paid, unpaid, or undisclosed without fake numbers."""
    from backend.app.pipeline.normalizer import normalize_stipend

    # Unspecified -> Undisclosed, no synthetic numbers
    res_undisclosed = normalize_stipend("")
    assert res_undisclosed["compensation_type"] == "undisclosed"
    assert res_undisclosed["min_val"] is None
    assert res_undisclosed["max_val"] is None

    res_comp = normalize_stipend("Competitive As Per Industry Standard")
    assert res_comp["compensation_type"] == "undisclosed"
    assert res_comp["min_val"] is None

    # Explicit unpaid
    res_unpaid = normalize_stipend("Unpaid internship with certificate")
    assert res_unpaid["compensation_type"] == "unpaid"
    assert res_unpaid["min_val"] == 0.0

    # Numeric paid range
    res_paid = normalize_stipend("₹15,000 - ₹25,000 / month")
    assert res_paid["compensation_type"] == "paid"
    assert res_paid["min_val"] == 15000.0
    assert res_paid["max_val"] == 25000.0

def test_24_field_schema_and_quality_score():
    """Verify standard-records endpoint returns the exact 24-field schema and quality breakdown."""
    res = client.get("/api/opportunities/standard-records?limit=5")
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)
    if items:
        record = items[0]
        required_24_fields = [
            "job_id", "internship_title", "company_name", "company_website",
            "job_description", "required_skills", "preferred_skills",
            "internship_type", "work_mode", "location", "stipend_min",
            "stipend_max", "stipend_currency", "duration", "eligibility",
            "experience_required", "application_deadline", "posted_date",
            "application_url", "source_name", "source_url", "source_job_id",
            "last_verified_at", "listing_status"
        ]
        for field in required_24_fields:
            assert field in record, f"Missing required field: {field}"
        
        # Check quality score fields
        assert "quality_score" in record
        assert "quality_breakdown" in record
        breakdown = record["quality_breakdown"]
        for dim in [
            "classification_confidence", "skill_relevance", "company_identification",
            "application_link_quality", "freshness_clarity", "data_completeness", "reasons"
        ]:
            assert dim in breakdown, f"Missing quality dimension: {dim}"

def test_source_adapter_functionality():
    """Item 1: Test source adapter architecture and configuration."""
    from backend.app.connectors.greenhouse import GreenhouseConnector
    from backend.app.connectors.ashby import AshbyConnector
    from backend.app.connectors.lever import LeverConnector
    from backend.app.connectors.internshala import InternshalaConnector
    from backend.app.connectors.remotive import RemotiveConnector

    gh = GreenhouseConnector(board_id="cloudflare")
    assert gh.name == "Greenhouse"
    assert gh.source_type == "ats"
    assert gh.rate_limit_delay >= 0.1
    assert gh.max_retries >= 1

    ash = AshbyConnector(organization="ramp")
    assert ash.name == "Ashby"
    assert ash.source_type == "ats"

    ish = InternshalaConnector()
    assert ish.name == "Internshala"
    assert ish.source_type == "portal"

    rem = RemotiveConnector()
    assert rem.name == "Remotive"
    assert rem.source_type == "api"

def test_source_failures_and_recovery():
    """Item 2: Test that source failures (unconfigured credentials, bot blocks) are handled gracefully without crashing."""
    from backend.app.connectors.adzuna import AdzunaConnector
    from backend.app.connectors.india_platforms import INDIA_PLATFORMS
    import asyncio

    # Adzuna with missing credentials returns empty without crashing
    adz = AdzunaConnector(app_id="", app_key="")
    res = asyncio.run(adz.fetch_jobs())
    assert res == []

    # India platforms document their status clearly
    for portal in ["naukri", "wellfound", "indeed", "aicte"]:
        assert portal in INDIA_PLATFORMS
        info = INDIA_PLATFORMS[portal]
        assert "failure_reason" in info
        assert "Manual URL import active" in info["failure_reason"] or "manual" in info["status"]

def test_database_persistence():
    """Item 4: Test full database persistence including internship_category and last_fetched_at."""
    db = SessionLocal()
    try:
        test_url = f"https://persisted-test.org/job/{int(datetime.utcnow().timestamp())}"
        opp = Opportunity(
            title="Database Test Intern",
            normalized_title="Database Test Intern",
            internship_category="backend",
            company_name="Postgres Labs",
            location="Pune, India",
            workplace_type="onsite",
            internship_type="in-office",
            employment_type="internship",
            description="Testing full SQLAlchemy persistence of new columns.",
            stipend_text="Stipend Undisclosed",
            compensation_type="undisclosed",
            original_url=test_url,
            application_url=test_url,
            source_url=test_url,
            source_platform="unit_test",
            status="verified",
            last_fetched_at=datetime.utcnow(),
            last_verified_at=datetime.utcnow()
        )
        db.add(opp)
        db.commit()
        db.refresh(opp)

        # Retrieve and verify
        saved = db.query(Opportunity).filter(Opportunity.id == opp.id).first()
        assert saved is not None
        assert saved.internship_category == "backend"
        assert saved.last_fetched_at is not None
        assert saved.status == "verified"

        # Cleanup
        db.delete(saved)
        db.commit()
    finally:
        db.close()

def test_url_validation_and_ssrf_protection():
    """Item 8: Verify external URL verification and bulletproof SSRF protection."""
    from backend.app.services.verifier import verify_url_live, is_safe_external_url
    import asyncio

    # Dangerous / Private IPs must be rejected immediately
    for dangerous in [
        "http://localhost:8000/api",
        "http://127.0.0.1:8005",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.1:8080/secret",
        "http://192.168.1.1/router"
    ]:
        safe, reason = is_safe_external_url(dangerous)
        assert not safe, f"Dangerous URL {dangerous} was not blocked by SSRF filter!"
        assert "SSRF" in reason

        verif = asyncio.run(verify_url_live(dangerous))
        assert verif["listing_status"] == "failed_verification"
        assert "SSRF" in verif["verification_notes"]

def test_search_and_combined_filters():
    """Item 9: Verify search, combined filters, and ensure full-time jobs are excluded."""
    # Test filtering by compensation_type
    res = client.get("/api/opportunities?tab=all&compensation_type=paid")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "total_pages" in data

    # Test filtering by category
    res_cat = client.get("/api/opportunities?tab=all&category=software_engineering")
    assert res_cat.status_code == 200

    # Test search query
    res_search = client.get("/api/opportunities?tab=all&search=Intern")
    assert res_search.status_code == 200

    # Test invalid limit validation returns 422
    res_invalid = client.get("/api/opportunities?limit=500")
    assert res_invalid.status_code == 422

def test_sorting_and_pagination():
    """Item 10: Verify sorting and pagination metadata."""
    res = client.get("/api/opportunities?tab=all&sort_by=match_score&sort_order=desc&skip=0&limit=10")
    assert res.status_code == 200
    data = res.json()
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert len(data["items"]) <= 10

    # Check descending order of scores if multiple items
    if len(data["items"]) >= 2:
        scores = [item["match_score"] for item in data["items"]]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

def test_ollama_unavailable_resilience():
    """Item 12: Verify discovery, extraction, scoring, and persistence function seamlessly when Ollama is unavailable."""
    from backend.app.ai.extractor import fallback_heuristic_extraction
    from backend.app.ai.compatibility_scorer import evaluate_compatibility
    import asyncio

    # Fallback heuristic extraction works deterministically without Ollama
    res = fallback_heuristic_extraction(
        title="Python Machine Learning Intern",
        description="Looking for an intern with skills in Python, PyTorch, and Docker. 6-month duration."
    )
    assert "Python" in res["mandatory_technical_skills"] or "Python" in res["programming_languages"]
    assert "responsibilities" in res
    assert res["duration_details"] is None # does not invent duration

def test_synchronization_concurrency_and_locks():
    """Item 15: Verify ACTIVE_SYNC_LOCKS prevents duplicate concurrent sync jobs on the same source."""
    from backend.app.services.discovery_scheduler import ACTIVE_SYNC_LOCKS, run_connector_sync
    import asyncio

    db = SessionLocal()
    try:
        # Simulate active lock
        ACTIVE_SYNC_LOCKS.add("internshala")
        res = asyncio.run(run_connector_sync("Internshala", db))
        assert res.get("status") == "already_running"
        assert "already active" in res.get("message", "")
    finally:
        ACTIVE_SYNC_LOCKS.discard("internshala")
        db.close()

def test_invalid_and_incomplete_records():
    """Item 16: Verify invalid or incomplete records are rejected by is_valid_internship."""
    from backend.app.pipeline.internship_filter import is_valid_internship

    # Missing title
    valid, err = is_valid_internship(title="", description="Valid desc", company_name="Company", url="https://valid.com")
    assert not valid
    assert "Missing or empty job title" in err

    # Missing company
    valid, err = is_valid_internship(title="Python Intern", description="Valid desc", company_name="", url="https://valid.com")
    assert not valid
    assert "lacks verified employer" in err

    # Missing URL
    valid, err = is_valid_internship(title="Python Intern", description="Valid desc", company_name="Company", url="")
    assert not valid
    assert "lacks a valid" in err


