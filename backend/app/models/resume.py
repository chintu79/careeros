from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, JSON
from backend.app.database import Base

class ResumeDocument(Base):
    __tablename__ = "resume_documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, default=1, index=True)
    title = Column(String(255), nullable=False, default="Master Resume")
    template_id = Column(String(50), default="ats_modern")  # ats_modern, ats_classic, ats_compact
    latex_content = Column(Text, nullable=False)
    
    # Target job traceability
    target_opportunity_id = Column(Integer, ForeignKey("opportunities.id", ondelete="SET NULL"), nullable=True, index=True)
    target_company = Column(String(255), nullable=True)
    target_role = Column(String(255), nullable=True)
    
    is_master = Column(Boolean, default=False, index=True)
    version = Column(Integer, default=1)
    
    # Metadata on tailored changes (which skills/projects were emphasized)
    tailored_insights = Column(JSON, default=dict)
    
    # Structured section content (personal_info, summary, education, skills, projects, experience, etc.)
    structured_content = Column(JSON, nullable=True, default=dict)

    pdf_path = Column(String(500), nullable=True)
    pdf_generated_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
