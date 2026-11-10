from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, ForeignKey
from backend.app.database import Base

class AIActionAuditLog(Base):
    __tablename__ = "ai_action_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action_type = Column(String(100), nullable=False, index=True) # e.g. "update_application_status", "prepare_tailored_resume", "schedule_interview"
    tool_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False) # Human-readable explanation of intended action
    data_payload = Column(JSON, default=dict) # Exact data being used
    status = Column(String(50), default="pending_approval", index=True) # "pending_approval", "approved", "rejected", "executed", "failed"
    requires_approval = Column(Boolean, default=True)
    user_confirmed = Column(Boolean, nullable=True) # True if approved, False if rejected
    rejection_reason = Column(Text, nullable=True)
    result_summary = Column(Text, nullable=True) # Verified result reported after execution
    result_payload = Column(JSON, nullable=True) # Result data payload
    conversation_id = Column(Integer, ForeignKey("chat_conversations.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    executed_at = Column(DateTime, nullable=True)
