from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime
from backend.app.database import Base


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"

    id = Column(Integer, primary_key=True, index=True)
    bucket_key = Column(String(128), nullable=False, unique=True, index=True)
    tokens = Column(Float, nullable=False, default=0.0)
    capacity = Column(Float, nullable=False)
    refill_per_second = Column(Float, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=utc_now)
