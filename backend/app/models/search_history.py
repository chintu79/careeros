from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON
from backend.app.database import Base

class SearchHistory(Base):
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(String(500), default="")
    search_mode = Column(String(50), default="hybrid", index=True)
    filters = Column(JSON, default=dict)
    results_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
