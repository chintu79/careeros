import pytest
import asyncio
from datetime import datetime
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal, Base, engine
from backend.app.models.opportunity import Opportunity
from backend.app.models.company import Company
from backend.app.models.source import JobSource
from backend.app.pipeline.duplicate_detector import (
    normalize_canonical_url,
    find_duplicate_opportunity,
    merge_duplicate_opportunity
)
from backend.app.api.companies import detect_ats_provider_from_url
from backend.app.connectors.base import BaseConnector
from backend.app.connectors.ycombinator import YCombinatorConnector

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_canonical_url_normalization():
    # Strips standard UTM and tracking parameters
    url1 = "https://boards.greenhouse.io/databricks/jobs/54321?gh_src=linkedin&utm_source=feed&utm_campaign=campus#apply"
    norm1 = normalize_canonical_url(url1)
    assert norm1 == "https://boards.greenhouse.io/databricks/jobs/54321"

    # Strips www., port, and trailing slash
    url2 = "http://www.jobs.lever.co/palantir/abc-123/?lever-origin=applied"
    norm2 = normalize_canonical_url(url2)
    assert norm2 == "https://jobs.lever.co/palantir/abc-123"

    # Matches across different tracking configurations
    url3 = "https://jobs.ashbyhq.com/ramp/4567?ref=newsletter&utm_medium=email"
    url4 = "https://jobs.ashbyhq.com/ramp/4567"
    assert normalize_canonical_url(url3) == normalize_canonical_url(url4)

    # Custom URNs are preserved
    urn = "urn:careeros:email-alert:naukri:12345"
    assert normalize_canonical_url(urn) == urn

def test_ats_auto_detection():
    # Greenhouse
    gh1 = detect_ats_provider_from_url("https://boards.greenhouse.io/cloudflare")
    assert gh1["detected"] is True
    assert gh1["ats_provider"] == "greenhouse"
    assert gh1["ats_board_id"] == "cloudflare"

    gh2 = detect_ats_provider_from_url("https://boards.greenhouse.io/embed/job_board?for=stripe")
    assert gh2["detected"] is True
    assert gh2["ats_provider"] == "greenhouse"
    assert gh2["ats_board_id"] == "stripe"

    # Lever
    lev = detect_ats_provider_from_url("https://jobs.lever.co/palantir")
    assert lev["detected"] is True
    assert lev["ats_provider"] == "lever"
    assert lev["ats_board_id"] == "palantir"

    # Ashby
    ash = detect_ats_provider_from_url("https://jobs.ashbyhq.com/ramp")
    assert ash["detected"] is True
    assert ash["ats_provider"] == "ashby"
    assert ash["ats_board_id"] == "ramp"

    # SmartRecruiters
    sr = detect_ats_provider_from_url("https://careers.smartrecruiters.com/visa")
    assert sr["detected"] is True
    assert sr["ats_provider"] == "smartrecruiters"
    assert sr["ats_board_id"] == "visa"

    # Unrecognized
    unknown = detect_ats_provider_from_url("https://careers.company.com/openings")
    assert unknown["detected"] is False

def test_multi_tier_duplicate_detection(db_session: Session):
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    ext_id = f"test_dup_{timestamp}"
    orig_url = f"https://boards.greenhouse.io/testco/jobs/{timestamp}"

    # Insert baseline opportunity
    opp = Opportunity(
        title="Software Engineer Intern",
        normalized_title="Software Engineer Intern",
        company_name="DuplicateTest Corp",
        location="Bengaluru, India",
        normalized_location="Bengaluru, India",
        workplace_type="onsite",
        internship_type="in-office",
        employment_type="internship",
        description="Initial posting from primary source.",
        stipend_text="Stipend Undisclosed",
        min_stipend=None,
        max_stipend=None,
        is_paid=True,
        compensation_type="undisclosed",
        original_url=orig_url,
        application_url=orig_url,
        external_id=ext_id,
        source_platform="greenhouse",
        source_links=[{"source": "greenhouse", "url": orig_url, "discovered_at": datetime.utcnow().isoformat()}],
        status="verified"
    )
    db_session.add(opp)
    db_session.commit()
    db_session.refresh(opp)

    try:
        # Tier 1 match: same external_id and source_platform
        is_dup, found = find_duplicate_opportunity(db_session, {
            "external_id": ext_id,
            "source_platform": "greenhouse",
            "original_url": "https://different-url.com"
        })
        assert is_dup is True
        assert found.id == opp.id

        # Tier 2 match: canonical normalized URL (with tracking parameters)
        is_dup, found = find_duplicate_opportunity(db_session, {
            "external_id": "different_id",
            "source_platform": "aggregator",
            "original_url": f"{orig_url}?utm_source=google&gh_src=test"
        })
        assert is_dup is True
        assert found.id == opp.id

        # Tier 3 match: Title + Company + Location
        is_dup, found = find_duplicate_opportunity(db_session, {
            "external_id": "unrelated_id",
            "source_platform": "naukri",
            "company_name": "DuplicateTest Corp",
            "normalized_title": "Software Engineer Intern",
            "normalized_location": "Bengaluru, India"
        })
        assert is_dup is True
        assert found.id == opp.id

        # Merge duplicate opportunity
        new_data = {
            "source_platform": "lever",
            "original_url": "https://jobs.lever.co/testco/alt-posting",
            "application_url": "https://jobs.lever.co/testco/alt-posting",
            "stipend_text": "₹35,000 / month",
            "min_stipend": 35000.0,
            "max_stipend": 35000.0,
            "compensation_type": "paid",
            "deadline_at": datetime(2026, 12, 31)
        }
        merged = merge_duplicate_opportunity(opp, new_data)
        db_session.commit()

        # Verify source_links preserved both references
        assert len(merged.source_links) == 2
        assert merged.source_links[0]["source"] == "greenhouse"
        assert merged.source_links[1]["source"] == "lever"

        # Verify compensation was enriched without overwriting title/company
        assert merged.min_stipend == 35000.0
        assert merged.stipend_text == "₹35,000 / month"
        assert merged.compensation_type == "paid"
        assert merged.deadline_at == datetime(2026, 12, 31)

    finally:
        # Clean up test record
        db_session.delete(opp)
        db_session.commit()

def test_board_reconciliation(db_session: Session):
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    active_url = f"https://boards.greenhouse.io/reconcileco/jobs/active_{timestamp}"
    closed_url = f"https://boards.greenhouse.io/reconcileco/jobs/closed_{timestamp}"

    opp_active = Opportunity(
        title="AI Engineer Intern",
        normalized_title="AI Engineer Intern",
        company_name="Reconcile Corp",
        original_url=active_url,
        source_platform="greenhouse",
        status="verified"
    )
    opp_closed = Opportunity(
        title="Backend Engineer Intern",
        normalized_title="Backend Developer Intern",
        company_name="Reconcile Corp",
        original_url=closed_url,
        source_platform="greenhouse",
        status="verified"
    )
    db_session.add(opp_active)
    db_session.add(opp_closed)
    db_session.commit()

    class TestConnector(BaseConnector):
        def __init__(self):
            super().__init__(name="Greenhouse", source_type="ats")
        async def fetch_jobs(self, **kwargs):
            return []

    connector = TestConnector()

    try:
        # Reconcile board with payload containing ONLY active_url
        closed_count = connector.reconcile_active_board_listings(
            db=db_session,
            active_original_urls=[active_url],
            source_platform="greenhouse",
            company_name="Reconcile Corp"
        )

        assert closed_count == 1
        db_session.refresh(opp_active)
        db_session.refresh(opp_closed)

        assert opp_active.status == "verified"
        assert opp_closed.status == "closed"

    finally:
        db_session.delete(opp_active)
        db_session.delete(opp_closed)
        db_session.commit()

def test_yc_connector_title_parsing():
    conn = YCombinatorConnector()

    comp, batch, role, loc = conn._parse_yc_title("Mbodi AI (YC P25) Is Hiring Research and Robotic Engineers")
    assert comp == "Mbodi AI"
    assert batch == "YC P25"
    assert "Research and Robotic Engineers" in role

    comp2, batch2, role2, loc2 = conn._parse_yc_title("PostHog (YC W20) is hiring an engineering intern in London or Remote")
    assert comp2 == "PostHog"
    assert batch2 == "YC W20"
    assert "engineering intern" in role2.lower()
    assert "London or Remote" in loc2

    # Categorization test
    assert conn._categorize_role("Machine Learning Engineer Intern") == "ai_ml"
    assert conn._categorize_role("Full Stack Developer") == "fullstack"
    assert conn._categorize_role("Infrastructure Engineer") == "devops_cloud"
