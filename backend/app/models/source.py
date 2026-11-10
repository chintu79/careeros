from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from backend.app.database import Base

class JobSource(Base):
    __tablename__ = "job_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    source_type = Column(String(50), nullable=False) # ats, api, rss, manual, portal
    integration_method = Column(String(50), nullable=False) # api, feed, direct_url, text_paste
    connection_status = Column(String(50), nullable=False, default="needs_configuration") 
    # connected, needs_configuration, temporarily_unavailable, manual_import_only, disabled
    sync_frequency_hours = Column(Integer, default=6)
    config_data = Column(JSON, default=dict) # api keys, board mappings, custom feed URLs
    last_sync_at = Column(DateTime, nullable=True)
    last_sync_status = Column(String(30), nullable=True) # success, error, warning
    last_error_message = Column(Text, nullable=True)
    total_jobs_discovered = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
