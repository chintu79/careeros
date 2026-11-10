from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.config import settings
from backend.app.observability.metrics import metrics as _metrics

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

@event.listens_for(engine, "checkout")
def _on_checkout(*_args):
    _metrics.inc("db_pool_checkouts_total")

@event.listens_for(engine, "checkin")
def _on_checkin(*_args):
    _metrics.inc("db_pool_checkins_total")

@event.listens_for(engine, "invalidate")
def _on_invalidate(*_args):
    _metrics.inc("db_pool_invalidations_total")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    try:
        db = SessionLocal()
    except Exception:
        _metrics.inc("db_pool_checkout_failures_total")
        raise
    try:
        yield db
    finally:
        db.close()
