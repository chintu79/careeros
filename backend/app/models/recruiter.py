from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from backend.app.database import Base

class RecruiterContact(Base):
    __tablename__ = "recruiter_contacts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, index=True)
    email = Column(String(255), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    company = Column(String(255), nullable=True, index=True)
    position = Column(String(255), nullable=True)
    contact_source = Column(String(100), default="Direct Outreach")  # LinkedIn, Referral, Career Fair, Direct Application
    notes = Column(Text, nullable=True)
    last_contact_date = Column(DateTime, nullable=True)
    
    # List of interaction touchpoints: [{ id, date, type, summary, follow_up_needed, logged_at }]
    interaction_history = Column(JSON, default=list)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
