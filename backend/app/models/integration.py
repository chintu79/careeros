from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from backend.app.database import Base

class IntegrationConnection(Base):
    """
    Connected user accounts for Gmail, Google Calendar, and Microsoft 365 Outlook.
    Sensitive tokens are encrypted at rest with Fernet.
    """
    __tablename__ = "integration_connections"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), nullable=False, index=True) # "google", "microsoft"
    account_email = Column(String(255), nullable=False, index=True)
    account_name = Column(String(255), nullable=True)
    scopes = Column(JSON, default=list) # e.g. ["https://www.googleapis.com/auth/gmail.readonly", ...]
    
    # Fernet encrypted credentials
    encrypted_access_token = Column(Text, nullable=True)
    encrypted_refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    
    # Status: "connected", "expired", "revoked", "disconnected", "error", "not_configured"
    connection_status = Column(String(50), default="not_configured", index=True)
    last_sync_at = Column(DateTime, nullable=True)
    last_sync_error = Column(Text, nullable=True)
    sync_cursor = Column(JSON, default=dict) # e.g. historyId, deltaLink, syncToken
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    emails = relationship("EmailMessageRecord", backref="connection", cascade="all, delete-orphan")
    calendar_events = relationship("CalendarEventRecord", backref="connection", cascade="all, delete-orphan")


class EmailMessageRecord(Base):
    """
    Ingested career communication with classification, structured extraction,
    and suggested application tracker updates.
    """
    __tablename__ = "email_message_records"

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(Integer, ForeignKey("integration_connections.id", ondelete="CASCADE"), nullable=True, index=True)
    application_id = Column(Integer, ForeignKey("application_records.id", ondelete="SET NULL"), nullable=True, index=True)
    
    provider_message_id = Column(String(255), unique=True, index=True, nullable=False)
    thread_id = Column(String(255), nullable=True, index=True)
    sender = Column(String(255), nullable=False)
    sender_email = Column(String(255), nullable=False, index=True)
    sender_name = Column(String(255), nullable=True)
    recipient = Column(String(255), nullable=True)
    subject = Column(String(500), nullable=False)
    snippet = Column(Text, nullable=True)
    body_plain = Column(Text, nullable=True)
    received_at = Column(DateTime, nullable=False, index=True)
    
    # Classification: application_confirmation, recruiter_outreach, interview_invitation, 
    # interview_rescheduled, assessment_test, rejection, shortlisting_screening, offer_letter, follow_up, other_career
    detected_category = Column(String(50), nullable=False, index=True)
    confidence_score = Column(Float, default=1.0) # 0.0 to 1.0 (scores < 0.85 require review)
    
    # Structured extracted details: {company, role, interview_date, meeting_link, deadline, action_required, platform}
    extracted_data = Column(JSON, default=dict)
    
    # Suggested application tracker stage transition (e.g. "applied", "technical_interview", "rejected", "offered")
    suggested_stage = Column(String(50), nullable=True)
    
    # Review status: "pending_review", "approved", "dismissed"
    review_status = Column(String(50), default="pending_review", index=True)
    user_action_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CalendarEventRecord(Base):
    """
    Calendar events synced from Google Calendar or Microsoft 365 Outlook,
    linked to applications for interview prep and deadline tracking.
    """
    __tablename__ = "calendar_event_records"

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(Integer, ForeignKey("integration_connections.id", ondelete="CASCADE"), nullable=True, index=True)
    application_id = Column(Integer, ForeignKey("application_records.id", ondelete="SET NULL"), nullable=True, index=True)
    
    provider_event_id = Column(String(255), unique=True, index=True, nullable=False)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=True)
    time_zone = Column(String(100), default="UTC")
    
    # Event type: technical_interview, hr_interview, recruiter_call, online_assessment, deadline, follow_up_reminder, career_meeting
    event_type = Column(String(50), default="technical_interview", index=True)
    meeting_platform = Column(String(100), nullable=True) # Google Meet, Zoom, Microsoft Teams, In-Person
    meeting_link = Column(String(1000), nullable=True)
    location = Column(String(500), nullable=True)
    
    company_name = Column(String(255), nullable=True, index=True)
    role_title = Column(String(255), nullable=True)
    organizer = Column(String(255), nullable=True)
    attendees = Column(JSON, default=list) # [{"name": "...", "email": "..."}]
    prep_notes = Column(Text, nullable=True)
    status = Column(String(50), default="confirmed") # confirmed, tentative, cancelled
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UnifiedActivityRecord(Base):
    """
    Centralized activity stream combining application stage changes,
    incoming emails, scheduled interviews, assessment deadlines, and follow-ups.
    """
    __tablename__ = "unified_activity_records"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("application_records.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Source type: email, calendar, stage_transition, interview_session, follow_up, user_note
    source_type = Column(String(50), nullable=False, index=True)
    # Event category: stage_change, email_received, interview_scheduled, assessment_deadline, follow_up_due, interview_completed
    event_category = Column(String(50), nullable=False, index=True)
    
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    company_name = Column(String(255), nullable=True)
    job_title = Column(String(255), nullable=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    
    reference_id = Column(String(255), nullable=True) # ID of underlying email, calendar event, or transition
    deep_link = Column(String(500), nullable=True)
    metadata_json = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow)
