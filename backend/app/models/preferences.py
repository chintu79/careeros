from datetime import datetime
from sqlalchemy import Column, Integer, Boolean, Float, DateTime, JSON
from backend.app.database import Base

class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    preferred_categories = Column(JSON, default=list)
    search_priorities = Column(JSON, default=list) # e.g. [{"priority": 1, "category": "AI/ML and Generative AI"}]
    preferred_locations = Column(JSON, default=list)
    
    paid_only = Column(Boolean, default=True)
    allow_unpaid = Column(Boolean, default=False)
    min_stipend = Column(Float, default=10000.0) # In INR
    preferred_duration_months = Column(Integer, default=6)
    workplace_types = Column(JSON, default=lambda: ["remote", "hybrid", "onsite"])
    
    max_experience_years = Column(Integer, default=1)
    student_only = Column(Boolean, default=True)
    graduation_year = Column(Integer, default=2026)
    
    excluded_keywords = Column(JSON, default=list)
    excluded_companies = Column(JSON, default=list)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
