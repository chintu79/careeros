from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models.application import ApplicationRecord
from backend.app.models.recruiter import RecruiterContact
from backend.app.models.opportunity import Opportunity

client = TestClient(app)

@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def test_enhanced_application_crud_and_interview_schedule(db):
    # 1. Create or retrieve an opportunity
    opp = db.query(Opportunity).first()
    assert opp is not None, "Opportunity needed for testing"

    # Clean existing application for this opportunity if present
    db.query(ApplicationRecord).filter(ApplicationRecord.opportunity_id == opp.id).delete()
    db.commit()

    # 2. Handoff with salary and notes
    resp = client.post("/api/applications/handoff", json={
        "opportunity_id": opp.id,
        "initial_status": "ready_to_apply",
        "user_notes": "Target priority company with strong engineering culture",
        "salary_or_stipend": "$50/hr",
        "recruiter_name": "Sarah Connor",
        "recruiter_email": "sarah.connor@tech.co"
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    app_id = data["id"]
    assert data["salary_or_stipend"] == "$50/hr"
    assert data["status"] == "ready_to_apply"

    # 3. Update status to applied with cover letter and resume version
    update_resp = client.put(f"/api/applications/{app_id}", json={
        "status": "applied",
        "salary_or_stipend": "$55/hr",
        "cover_letter_text": "I am eager to contribute my backend systems expertise to your infrastructure team.",
        "resume_version_number": 2,
        "recruiter_position": "Senior Technical Recruiter"
    })
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["status"] == "applied"
    assert updated["salary_or_stipend"] == "$55/hr"
    assert updated["resume_version_number"] == 2
    assert updated["recruiter_position"] == "Senior Technical Recruiter"
    assert updated["cover_letter_text"] is not None

    # 4. Schedule an interview
    interview_time = (datetime.utcnow() + timedelta(days=2)).isoformat()
    sched_resp = client.post(f"/api/applications/{app_id}/schedule-interview", json={
        "round_name": "Technical Architecture Round",
        "date": interview_time,
        "format": "virtual_video",
        "interviewer": "David Heinemeier",
        "meeting_link": "https://meet.google.com/abc-defg-hij",
        "notes": "Review PostgreSQL index optimization and distributed transactions"
    })
    assert sched_resp.status_code == 200
    sched_data = sched_resp.json()
    assert sched_data["application"]["status"] == "interviewing"
    assert len(sched_data["application"]["interview_schedule"]) == 1
    assert sched_data["interview"]["round_name"] == "Technical Architecture Round"

def test_recruiter_crm_crud_and_interactions(db):
    # 1. Create a recruiter
    create_resp = client.post("/api/recruiters", json={
        "name": "Alex Mercer",
        "email": "alex.mercer@innovate.io",
        "linkedin_url": "https://linkedin.com/in/alex-mercer-recruiter",
        "company": "Innovate Labs",
        "position": "Director of University Talent",
        "contact_source": "LinkedIn Outreach",
        "notes": "Prefers communication on weekday mornings."
    })
    assert create_resp.status_code == 200
    rec = create_resp.json()
    rec_id = rec["id"]
    assert rec["name"] == "Alex Mercer"
    assert rec["company"] == "Innovate Labs"

    # 2. List recruiters
    list_resp = client.get("/api/recruiters?search=Mercer")
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert any(r["id"] == rec_id for r in items)

    # 3. Log interaction
    int_resp = client.post(f"/api/recruiters/{rec_id}/interactions", json={
        "interaction_type": "email",
        "summary": "Sent portfolio link and inquired about Summer 2026 SWE intern roles",
        "follow_up_needed": True,
        "next_step": "Check in 7 days if no reply"
    })
    assert int_resp.status_code == 200
    int_data = int_resp.json()
    assert len(int_data["recruiter"]["interaction_history"]) >= 1
    assert int_data["interaction"]["type"] == "email"

    # 4. Update recruiter
    up_resp = client.put(f"/api/recruiters/{rec_id}", json={
        "notes": "Confirmed opening for Backend Intern in Q2"
    })
    assert up_resp.status_code == 200
    assert up_resp.json()["notes"] == "Confirmed opening for Backend Intern in Q2"

    # 5. Delete recruiter
    del_resp = client.delete(f"/api/recruiters/{rec_id}")
    assert del_resp.status_code == 200

def test_follow_up_intelligence_and_email_generation(db):
    # 1. Fetch follow-up alerts
    alerts_resp = client.get("/api/applications/follow-ups?stale_days=7")
    assert alerts_resp.status_code == 200
    alerts = alerts_resp.json()
    assert "summary" in alerts
    assert "unanswered_applications" in alerts
    assert "upcoming_interviews" in alerts

    # 2. Pick an application to generate draft
    app_record = db.query(ApplicationRecord).first()
    assert app_record is not None

    draft_resp = client.post(f"/api/applications/{app_record.id}/generate-follow-up", json={
        "tone": "inquisitive"
    })
    assert draft_resp.status_code == 200
    draft = draft_resp.json()
    assert draft["subject"] is not None
    assert draft["body"] is not None
    assert draft["requires_user_approval"] is True

    # 3. Test approval endpoint
    approve_resp = client.post(f"/api/applications/{app_record.id}/approve-follow-up", json={
        "advance_days": 10,
        "notes": "Dispatched email via applicant mail client"
    })
    assert approve_resp.status_code == 200
    approved_data = approve_resp.json()
    assert "new_follow_up_date" in approved_data

def test_application_analytics_and_calendar_views(db):
    # 1. Analytics
    analytics_resp = client.get("/api/applications/analytics")
    assert analytics_resp.status_code == 200
    analytics = analytics_resp.json()
    assert "pipeline_counts" in analytics
    assert "rates" in analytics
    assert "formula_definitions" in analytics
    assert "source_performance" in analytics
    assert "resume_performance" in analytics

    # Mathematical checks
    rates = analytics["rates"]
    assert 0.0 <= rates["application_response_rate"] <= 100.0
    assert 0.0 <= rates["interview_conversion_rate"] <= 100.0
    assert 0.0 <= rates["offer_conversion_rate"] <= 100.0
    assert rates["average_response_time_days"] >= 0.0

    # 2. Timeline view
    timeline_resp = client.get("/api/applications/timeline")
    assert timeline_resp.status_code == 200
    timeline = timeline_resp.json()
    assert "events" in timeline
    assert isinstance(timeline["events"], list)

    # 3. Calendar view
    cal_resp = client.get("/api/applications/calendar")
    assert cal_resp.status_code == 200
    calendar = cal_resp.json()
    assert "events" in calendar
    assert isinstance(calendar["events"], list)
