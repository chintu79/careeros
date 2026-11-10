from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.dialects.postgresql import JSONB
from backend.app.database import Base


def utc_now() -> datetime:
    """Return timezone-naive UTC timestamp for TIMESTAMP WITHOUT TIME ZONE columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DiscoveryRankingSnapshot(Base):
    """
    Persistent ranking snapshot table in PostgreSQL.
    Enables distributed, cross-worker pagination consistency across independent backend processes.
    """
    __tablename__ = "discovery_ranking_snapshots"

    snapshot_key = Column(String(128), primary_key=True, index=True)
    snapshot_id = Column(String(64), unique=True, index=True, nullable=True)
    user_id = Column(Integer, nullable=False, index=True)
    signature = Column(String(64), nullable=False, index=True)
    candidate_evidence_version = Column(String(64), nullable=False)
    total_count = Column(Integer, nullable=False)
    snapshot_ids = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=False)  # List[int]
    created_at = Column(DateTime, default=utc_now, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
