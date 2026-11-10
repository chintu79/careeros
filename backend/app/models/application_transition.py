from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from backend.app.database import Base

class ApplicationStageTransition(Base):
    __tablename__ = "application_stage_transitions"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("application_records.id", ondelete="CASCADE"), nullable=False, index=True)
    from_stage = Column(String(50), nullable=False)
    to_stage = Column(String(50), nullable=False)
    transitioned_at = Column(DateTime, default=datetime.utcnow, index=True)
    notes = Column(Text, nullable=True)
