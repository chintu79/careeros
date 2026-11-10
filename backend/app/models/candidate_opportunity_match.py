from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey, UniqueConstraint, ForeignKeyConstraint
from backend.app.database import Base


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CandidateOpportunityMatch(Base):
    __tablename__ = "candidate_opportunity_matches"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    candidate_id = Column(Integer, ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True)

    match_score = Column(Float, default=0.0, index=True)
    eligibility_status = Column(String(50), default="eligible", index=True)
    match_analysis = Column(JSON, default=dict)

    candidate_content_hash = Column(String(64), nullable=False, index=True)
    opportunity_content_hash = Column(String(64), nullable=False, index=True)
    candidate_evidence_version = Column(Integer, default=1, nullable=False)
    opportunity_content_version = Column(Integer, default=1, nullable=False)
    engine_version = Column(String(20), default="2.0.0")
    engine_generation = Column(Integer, default=2, nullable=False, index=True)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        UniqueConstraint("user_id", "opportunity_id", name="uq_candidate_opportunity_match_user_opp"),
        ForeignKeyConstraint(
            ["candidate_id", "user_id"],
            ["candidate_profiles.id", "candidate_profiles.user_id"],
            ondelete="CASCADE",
            name="fk_cand_opp_match_cand_user"
        ),
    )
