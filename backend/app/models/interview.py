from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, JSON, ForeignKey
from backend.app.database import Base

class InterviewJournalRecord(Base):
    __tablename__ = "interview_journal_records"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("application_records.id", ondelete="SET NULL"), nullable=True, index=True)
    company_name = Column(String(255), nullable=False, index=True)
    role = Column(String(255), default="Software Engineering Intern", index=True)
    round_name = Column(String(150), default="Technical Round 1")
    round_type = Column(String(50), default="technical") # technical, behavioral, screening, hr, system_design
    interview_format = Column(String(50), default="virtual_video") # virtual_video, in_person, phone_screen, take_home, online_assessment
    
    interview_date = Column(DateTime, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Structured Q&A: [{"question": "...", "topic": "...", "user_answer": "...", "feedback": "...", "confidence": 4}]
    questions_asked = Column(JSON, default=list)
    topics_covered = Column(JSON, default=list) # ["FastAPI", "PostgreSQL", "System Design"]
    
    confidence_level = Column(Integer, default=3) # 1 to 5
    difficulty_rating = Column(Integer, default=3) # 1 to 5
    performance_rating = Column(Integer, default=3) # 1 to 5
    interview_result = Column(String(50), default="pending", index=True) # pending, passed, rejected, offer, withdrawn
    
    # Real interviewer feedback from hiring team (strictly separate from AI feedback)
    interviewer_feedback = Column(Text, nullable=True)
    
    # AI Performance diagnosis: {"strengths": [...], "weaknesses": [...], "suggested_topics": [...]}
    ai_feedback = Column(JSON, default=dict)
    
    notes = Column(Text, nullable=True)
    personal_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
