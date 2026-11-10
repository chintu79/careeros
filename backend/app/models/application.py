from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from backend.app.database import Base

class ApplicationRecord(Base):
    __tablename__ = "application_records"

    id = Column(Integer, primary_key=True, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, unique=True)
    company_name = Column(String(255), nullable=False, index=True)
    job_title = Column(String(300), nullable=False)
    original_url = Column(String(1000), nullable=False)
    
    # Status pipeline: saved, ready_to_apply, applied, recruiter_response, screening, technical_interview, hr_interview, final_round, offered, rejected, withdrawn, no_response
    status = Column(String(50), default="ready_to_apply", index=True)
    applied_date = Column(DateTime, nullable=True)
    match_score = Column(Float, default=0.0)
    
    # Associated tailored resume
    resume_id = Column(Integer, ForeignKey("resume_documents.id", ondelete="SET NULL"), nullable=True)
    resume_version_number = Column(Integer, nullable=True)
    
    # Assisted application fields
    submission_mode = Column(String(50), default="assisted") # "assisted" or "authorized_auto"
    submitted_materials = Column(JSON, default=dict)
    submission_url = Column(String(1000), nullable=True)
    submission_verified = Column(Boolean, default=False)
    follow_up_date = Column(DateTime, nullable=True)
    
    # Financial and letter details
    tailored_resume_summary = Column(Text, nullable=True)
    salary_or_stipend = Column(String(100), nullable=True)
    cover_letter_text = Column(Text, nullable=True)
    cover_letter_points = Column(JSON, default=list)

    # Recruiter details (inline or linked)
    recruiter_id = Column(Integer, ForeignKey("recruiter_contacts.id", ondelete="SET NULL"), nullable=True)
    recruiter_name = Column(String(150), nullable=True)
    recruiter_position = Column(String(150), nullable=True)
    recruiter_email = Column(String(150), nullable=True)
    recruiter_linkedin = Column(String(500), nullable=True)
    
    # Scheduled interviews: [{ id, round_name, date, format, interviewer, meeting_link, notes }]
    interview_schedule = Column(JSON, default=list)

    user_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    stage_transitions = relationship("ApplicationStageTransition", backref="application", cascade="all, delete-orphan", order_by="ApplicationStageTransition.transitioned_at")

