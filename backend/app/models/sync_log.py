from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from backend.app.database import Base

class SyncLog(Base):
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    source_name = Column(String(100), nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    retrieved_count = Column(Integer, default=0)
    new_count = Column(Integer, default=0)
    duplicate_count = Column(Integer, default=0)
    expired_count = Column(Integer, default=0)
    relevant_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    error_details = Column(Text, nullable=True)
    status = Column(String(50), default="running") # running, success, partial, failure
    created_at = Column(DateTime, default=datetime.utcnow)
