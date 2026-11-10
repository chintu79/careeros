import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models.opportunity import Opportunity
from backend.app.models.application import ApplicationRecord
from backend.app.models.interview import InterviewJournalRecord
from backend.app.models.resume import ResumeDocument
from backend.app.services.command_center import get_command_center_overview

client = TestClient(app)

@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    yield db
    db.close()


def test_command_center_service_pipeline_and_funnel(db_session):
    """Verify Question 1: Application pipeline metrics and conversion calculations."""
    data = get_command_center_overview(db_session, date_range="all")
    pipeline = data["pipeline_summary"]

    assert "total_applications" in pipeline
    assert "stages_count" in pipeline
    assert "response_rate" in pipeline
    assert "interview_rate" in pipeline
    assert "offer_rate" in pipeline

    # Must be grounded in actual database application records
    actual_db_count = db_session.query(ApplicationRecord).count()
    assert pipeline["total_applications"] == actual_db_count
    assert sum(pipeline["stages_count"].values()) == actual_db_count


def test_command_center_service_prioritized_actions(db_session):
    """Verify Question 3: Intelligent prioritized actions with clear reasons and actionable triggers."""
    data = get_command_center_overview(db_session, date_range="30d")
    actions = data["prioritized_actions"]

    assert isinstance(actions, list)
    assert len(actions) >= 1

    # Every action item must strictly have id, priority, category, title, reason, action_label, action_type
    for item in actions:
        assert item["priority"] in ("urgent", "high", "medium")
        assert item["category"] in ("interview", "follow_up", "deadline", "resume", "apply")
        assert len(item["title"]) > 3
        assert len(item["reason"]) > 10
        assert len(item["action_label"]) > 1
        assert item["action_type"] in ("navigate_tab", "tailor_resume", "prepare_apply")


def test_command_center_service_deadlines_and_prioritization(db_session):
    """Verify Question 2: Upcoming deadlines and top priority opportunities."""
    data = get_command_center_overview(db_session, date_range="all")
    deadlines = data["upcoming_deadlines"]

    assert isinstance(deadlines, list)
    # Check deadline structure
    for dl in deadlines:
        assert "days_left" in dl
        assert "hours_left" in dl
        assert dl["urgency"] in ("urgent", "high", "medium")
        assert "match_score" in dl

    # Top priority relevant opportunities
    top_matches = data["recently_discovered_relevant"]
    assert len(top_matches) >= 1
    for m in top_matches:
        assert m["match_score"] >= 50.0
        assert "company_name" in m
        assert "title" in m


def test_command_center_service_readiness_and_gaps(db_session):
    """Verify Question 4: Readiness diagnostics, resume ATS status, and skill gaps."""
    data = get_command_center_overview(db_session, date_range="30d")
    diag = data["readiness_diagnostics"]

    assert "interview" in diag
    assert "resume" in diag
    assert "skills" in diag

    # Resume health
    assert diag["resume"]["total_resumes"] >= 1
    assert 0.0 <= diag["resume"]["compiled_pdf_rate"] <= 100.0

    # Skills gaps
    assert diag["skills"]["verified_skills_count"] >= 10
    assert len(diag["skills"]["market_demanded_mastered"]) >= 1


def test_command_center_service_strategic_focus(db_session):
    """Verify Question 5: Strategic roadmap and next milestone project."""
    data = get_command_center_overview(db_session, date_range="30d")
    focus = data["strategic_focus"]

    assert "focus_area" in focus
    assert "reason" in focus
    assert "milestone_project" in focus
    assert "weekly_pace" in focus


def test_command_center_service_activity_timeline(db_session):
    """Verify unified chronological activity stream."""
    data = get_command_center_overview(db_session, date_range="all")
    timeline = data["activity_timeline"]

    assert isinstance(timeline, list)
    assert len(timeline) >= 1

    # Check timestamps are sorted descending
    if len(timeline) > 1:
        assert timeline[0]["timestamp"] >= timeline[1]["timestamp"]


def test_command_center_date_ranges(db_session):
    """Verify date range filtering (7d, 30d, 90d, all)."""
    d_7d = get_command_center_overview(db_session, date_range="7d")
    d_all = get_command_center_overview(db_session, date_range="all")

    assert d_7d["date_range"] == "7d"
    assert d_all["date_range"] == "all"
    assert d_7d["pipeline_summary"]["total_applications"] <= d_all["pipeline_summary"]["total_applications"]


def test_command_center_api_endpoint():
    """Verify GET /api/command-center returns 200 OK with full schema."""
    res = client.get("/api/command-center?date_range=30d")
    assert res.status_code == 200
    payload = res.json()

    assert payload["date_range"] == "30d"
    assert "pipeline_summary" in payload
    assert "prioritized_actions" in payload
    assert "upcoming_deadlines" in payload
    assert "readiness_diagnostics" in payload
    assert "strategic_focus" in payload
    assert "activity_timeline" in payload
