from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text
from backend.app.database import Base

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    website = Column(String(500), nullable=True)
    career_url = Column(String(500), nullable=True)
    industry = Column(String(100), nullable=True)
    hq_location = Column(String(150), nullable=True)
    ats_provider = Column(String(50), nullable=False, default="custom") # greenhouse, lever, ashby, smartrecruiters, custom
    ats_board_id = Column(String(100), nullable=True, index=True)
    company_size = Column(String(50), nullable=True)
    monitoring_status = Column(String(30), nullable=False, default="active") # active, paused
    last_sync_at = Column(DateTime, nullable=True)
    opportunities_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
