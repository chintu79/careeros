from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, JSON, ForeignKey, Text
from backend.app.database import Base

class MockPracticeSession(Base):
    __tablename__ = "mock_practice_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, default=1, index=True)
    session_title = Column(String(255), nullable=False, default="Mock Interview Practice")
    
    target_opportunity_id = Column(Integer, ForeignKey("opportunities.id", ondelete="SET NULL"), nullable=True, index=True)
    company_name = Column(String(255), nullable=True)
    role_title = Column(String(255), nullable=True)
    session_type = Column(String(50), default="technical", index=True) # technical, dsa, project_deep_dive, behavioral, full_mock
    status = Column(String(50), default="in_progress", index=True) # in_progress, completed, abandoned
    
    # List of practice questions:
    # [{
    #   "id": "q1",
    #   "category": "technical",
    #   "question": "How does FastAPI handle asynchronous request execution?",
    #   "context_or_hint": "Think about event loop and threadpool workers for def vs async def.",
    #   "user_answer": "...",
    #   "evaluated_at": "...",
    #   "ai_evaluation": {
    #       "score": 85,
    #       "clarity_rating": 4,
    #       "technical_depth": 4,
    #       "strengths": [...],
    #       "improvement_areas": [...],
    #       "ideal_answer_points": [...],
    #       "verdict": "Strong technical grasp"
    #   }
    # }]
    questions = Column(JSON, default=list)
    
    overall_score = Column(Float, nullable=True) # 0 to 100
    ai_session_summary = Column(JSON, default=dict) # strengths, gaps, overall readiness
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
