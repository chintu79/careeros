import pytest
from datetime import datetime, timedelta
from backend.app.database import SessionLocal
from backend.app.services.token_vault import encrypt_token, decrypt_token
from backend.app.services.email_intelligence_service import (
    classify_career_email,
    extract_structured_email_data,
    sanitize_email_text,
    find_matching_application,
    process_incoming_email,
    CATEGORY_APPLICATION_CONFIRMATION,
    CATEGORY_RECRUITER_OUTREACH,
    CATEGORY_INTERVIEW_INVITATION,
    CATEGORY_INTERVIEW_RESCHEDULED,
    CATEGORY_ASSESSMENT_TEST,
    CATEGORY_REJECTION,
    CATEGORY_SHORTLISTING_SCREENING,
    CATEGORY_OFFER_LETTER,
    CATEGORY_FOLLOW_UP,
    CATEGORY_OTHER_CAREER
)
from backend.app.services.calendar_intelligence_service import (
    classify_calendar_event,
    process_calendar_event,
    EVENT_TYPE_TECHNICAL_INTERVIEW,
    EVENT_TYPE_ONLINE_ASSESSMENT
)
from backend.app.services.unified_activity_service import fetch_unified_activities
from backend.app.models.application import ApplicationRecord
from backend.app.models.application_transition import ApplicationStageTransition
from backend.app.models.integration import IntegrationConnection, EmailMessageRecord, CalendarEventRecord

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_token_vault_encryption_and_decryption():
    """Verify Fernet symmetric encryption and decryption at rest."""
    sample_token = "ya29.a0AfH6SMD_very_secret_oauth_access_token_12345"
    cipher = encrypt_token(sample_token)
    
    assert cipher != sample_token
    assert len(cipher) > len(sample_token)
    
    decrypted = decrypt_token(cipher)
    assert decrypted == sample_token

    # Verify empty string handling
    assert encrypt_token("") == ""
    assert decrypt_token("") == ""

    # Verify corrupted ciphertext raises error
    with pytest.raises(ValueError):
        decrypt_token("corrupted_invalid_base64_ciphertext")

def test_email_10_category_classification():
    """Verify high-accuracy classification across all 10 career communication categories."""
    cases = [
        ("Thank you for applying to Stripe!", "We received your application for Backend Intern.", CATEGORY_APPLICATION_CONFIRMATION),
        ("Exciting opportunity at Figma", "I came across your profile on GitHub and was impressed by your distributed systems work.", CATEGORY_RECRUITER_OUTREACH),
        ("Interview Invitation: Round 1 Technical", "We would like to invite you to interview for Software Engineer Intern.", CATEGORY_INTERVIEW_INVITATION),
        ("Updated: Interview Rescheduled for Friday", "Due to an internal conflict, we are rescheduling your interview to 3 PM.", CATEGORY_INTERVIEW_RESCHEDULED),
        ("Palantir Technologies: HackerRank Coding Challenge", "Please complete your online assessment before the deadline.", CATEGORY_ASSESSMENT_TEST),
        ("Update on your application with Datadog", "Unfortunately, we have decided to move forward with other candidates at this time.", CATEGORY_REJECTION),
        ("You have been shortlisted for initial screening", "We are pleased to inform you that you passed the initial screening call.", CATEGORY_SHORTLISTING_SCREENING),
        ("Congratulations! Offer Letter from Ramp", "We are pleased to offer you the position of Software Engineering Intern.", CATEGORY_OFFER_LETTER),
        ("Following up on our conversation", "Just checking in on your current interview availability.", CATEGORY_FOLLOW_UP),
        ("Campus Recruiting Update", "Information about our upcoming virtual tech talk and intern showcase.", CATEGORY_OTHER_CAREER)
    ]

    for subject, body, expected_category in cases:
        cat, conf = classify_career_email(subject, body)
        assert cat == expected_category, f"Failed for '{subject}': expected {expected_category}, got {cat}"
        assert 0.0 <= conf <= 1.0

def test_structured_email_data_extraction_and_sanitization():
    """Verify meeting links, deadline extraction, and strict HTML sanitization without fabrication."""
    malicious_body = """
    <script>alert('pwned');</script>
    <p>Hi Krishna,</p>
    <p>Please join our technical interview on Google Meet: 
       <a href="https://meet.google.com/abc-defg-hij">Google Meet Link</a>
    </p>
    <p>Please confirm your attendance by November 18, 2026.</p>
    """
    sanitized = sanitize_email_text(malicious_body)
    assert "<script>" not in sanitized
    assert "alert('pwned')" not in sanitized
    assert "Please join our technical interview on Google Meet" in sanitized

    extracted = extract_structured_email_data(
        subject="Technical Interview with Stripe",
        body=sanitized,
        sender="recruiting@stripe.com",
        category=CATEGORY_INTERVIEW_INVITATION
    )
    assert extracted["company_name"] == "Stripe"
    assert extracted["meeting_platform"] == "Google Meet"
    assert extracted["meeting_link"] == "https://meet.google.com/abc-defg-hij"
    assert extracted["deadline_text"] is not None
    assert "November 18" in extracted["deadline_text"]

def test_consequential_approval_workflow(db_session):
    """
    Verify consequential application tracker updates:
    - Status is NEVER changed before approval
    - Approval applies transition and logs ApplicationStageTransition
    - Idempotent execution
    """
    # 1. Create a dedicated unique opportunity for foreign key
    import uuid
    from backend.app.models.opportunity import Opportunity
    uid = uuid.uuid4().hex[:8]
    opp = Opportunity(
        title=f"Software Intern {uid}",
        normalized_title=f"software intern {uid}",
        company_name="TestCorp",
        original_url=f"https://testcorp.com/jobs/{uid}",
        source_platform="direct",
        location="Remote"
    )
    db_session.add(opp)
    db_session.commit()
    db_session.refresh(opp)

    app = ApplicationRecord(
        opportunity_id=opp.id,
        company_name="TestCorp",
        job_title="Software Intern",
        original_url=f"https://testcorp.com/jobs/{uid}",
        status="applied",
        applied_date=datetime.utcnow()
    )
    db_session.add(app)
    db_session.commit()
    db_session.refresh(app)

    # 2. Process an interview invite email for TestCorp
    raw_msg = {
        "provider_message_id": f"msg_test_{datetime.utcnow().timestamp()}",
        "subject": "Interview Invitation: TestCorp Software Intern",
        "sender": "recruiter@testcorp.com",
        "snippet": "We want to invite you to an interview.",
        "body_plain": "Join us on https://meet.google.com/tst-test-xyz by Friday.",
        "received_at": datetime.utcnow()
    }
    email_rec = process_incoming_email(db_session, raw_msg)
    assert email_rec.application_id == app.id
    assert email_rec.detected_category == CATEGORY_INTERVIEW_INVITATION
    assert email_rec.suggested_stage == "technical_interview"
    assert email_rec.review_status == "pending_review"

    # CRITICAL: Application status must remain 'applied' before explicit user approval!
    db_session.refresh(app)
    assert app.status == "applied"

    # 3. Simulate User Approval
    from backend.app.api.email_intelligence import approve_email_update
    result = approve_email_update(email_rec.id, db=db_session)
    assert result["success"] is True
    assert result["transition_applied"] is True
    assert result["old_stage"] == "applied"
    assert result["new_stage"] == "technical_interview"

    # Verify application status was updated
    db_session.refresh(app)
    assert app.status == "technical_interview"
    assert email_rec.review_status == "approved"

    # Verify ApplicationStageTransition audit entry was recorded
    transitions = db_session.query(ApplicationStageTransition).filter(ApplicationStageTransition.application_id == app.id).all()
    assert len(transitions) >= 1
    assert any(t.to_stage == "technical_interview" for t in transitions)

    # 4. Verify Idempotency: Approving again does not create redundant transitions
    res_again = approve_email_update(email_rec.id, db=db_session)
    assert res_again["success"] is True
    assert "already approved" in res_again["message"]

    # Cleanup
    db_session.delete(app)
    db_session.delete(email_rec)
    db_session.delete(opp)
    db_session.commit()

def test_calendar_intelligence_event_processing(db_session):
    """Verify calendar event classification, meeting link parsing, and application linking."""
    raw_ev = {
        "provider_event_id": f"cal_test_{datetime.utcnow().timestamp()}",
        "title": "Technical Interview with Stripe",
        "description": "Round 1 Coding. Link: https://meet.google.com/tst-meet-123",
        "start_time": datetime.utcnow() + timedelta(days=2),
        "end_time": datetime.utcnow() + timedelta(days=2, hours=1),
        "time_zone": "Asia/Kolkata",
        "status": "confirmed"
    }
    record = process_calendar_event(db_session, raw_ev)
    assert record.event_type == EVENT_TYPE_TECHNICAL_INTERVIEW
    assert record.company_name == "Stripe"
    assert record.meeting_platform == "Google Meet"
    assert record.meeting_link == "https://meet.google.com/tst-meet-123"
    assert record.time_zone == "Asia/Kolkata"

    # Cleanup
    db_session.delete(record)
    db_session.commit()

def test_unified_activity_feed_filtering(db_session):
    """Verify Unified Activity timeline combines events and filters accurately."""
    activities_all = fetch_unified_activities(db_session, limit=20, filter_category="all")
    assert isinstance(activities_all, list)

    activities_emails = fetch_unified_activities(db_session, limit=20, filter_category="emails")
    assert all(a["source_type"] == "email" for a in activities_emails)

    activities_interviews = fetch_unified_activities(db_session, limit=20, filter_category="interviews")
    assert all(a["source_type"] in ["calendar", "interview_schedule"] for a in activities_interviews)

@pytest.mark.asyncio
async def test_sandbox_seed_and_disconnect(db_session):
    """Verify sandbox seed populates realistic fixtures and disconnect revokes credentials."""
    from backend.app.api.integrations import seed_sandbox_data, disconnect_integration

    seed_res = seed_sandbox_data(db=db_session)
    assert seed_res["success"] is True
    assert seed_res["emails_count"] >= 4
    assert seed_res["calendar_events_count"] >= 2

    conn_id = seed_res["connection_id"]
    conn = db_session.query(IntegrationConnection).filter(IntegrationConnection.id == conn_id).first()
    assert conn is not None
    assert conn.connection_status == "connected"

    # Test disconnect
    disc_res = await disconnect_integration(conn_id, db=db_session)
    assert disc_res.success is True
    db_session.refresh(conn)
    assert conn.connection_status == "disconnected"
    assert conn.encrypted_access_token is None

