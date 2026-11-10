from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON
from backend.app.database import Base

class SavedSearch(Base):
    __tablename__ = "saved_searches"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    search_mode = Column(String(50), default="hybrid", index=True) # hybrid, semantic, keyword, skill, company, location
    query = Column(String(500), default="")
    filters = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    last_run_at = Column(DateTime, default=datetime.utcnow)
