from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, UniqueConstraint
from backend.app.database import Base


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_candidate_profiles_id_user"),
        UniqueConstraint("user_id", name="uq_candidate_profiles_user_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(150), default="")
    email = Column(String(150), default="")
    phone = Column(String(50), default="")
    location = Column(String(150), default="")
    bio = Column(Text, default="")
    
    degree = Column(String(100), default="")
    graduation_year = Column(Integer, nullable=True)
    college = Column(String(200), default="")
    cgpa = Column(Float, nullable=True)
    
    # External Profile URLs
    github_url = Column(String(255), default="")
    github_username = Column(String(100), default="")
    github_data = Column(JSON, default=dict)
    
    linkedin_url = Column(String(255), default="")
    linkedin_data = Column(JSON, default=dict)
    
    portfolio_url = Column(String(255), default="")
    portfolio_data = Column(JSON, default=dict)
    website_url = Column(String(255), nullable=True)
    
    # Skills structure: [{"name": "Python", "level": "advanced", "category": "language", "evidence": "Argus AI, FastAPI microservices"}]
    skills = Column(JSON, default=list)
    
    # Projects: [{"title": "CareerOS Job Discovery Engine", "description": "Automated opportunity aggregator with pgvector and Ollama", "tech_stack": ["FastAPI", "PostgreSQL", "React", "Ollama"], "url": "https://github.com/synthetic-candidate/careeros"}]
    projects = Column(JSON, default=list)
    
    # Experience: [{"title": "Software Engineering Intern", "company": "Tech Labs", "duration": "3 months", "description": "Built backend APIs and vector search microservices."}]
    experience = Column(JSON, default=list)
    
    # Additional sections
    certifications = Column(JSON, default=list)
    achievements = Column(JSON, default=list)
    extracurriculars = Column(JSON, default=list)
    raw_resume_text = Column(Text, nullable=True)
    
    preferred_locations = Column(JSON, default=list)
    work_authorization = Column(String(100), default="")
    
    # Onboarding & Activation (Iteration 2.8)
    onboarding_status = Column(String(50), default="not_started") # "not_started", "in_progress", "completed"
    onboarding_step = Column(Integer, default=1) # 1 to 6
    career_goals = Column(JSON, default=dict) # target_roles, target_locations, workplace_preference, min_stipend
    
    evidence_version = Column(Integer, default=1, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
