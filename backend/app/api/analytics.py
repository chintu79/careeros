from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.services.analytics_service import (
    get_discovery_analytics, 
    get_application_sankey_data,
    get_source_efficacy_metrics
)

router = APIRouter(prefix="/analytics", tags=["Analytics & Sankey Pipeline"])

@router.get("")
def get_analytics(db: Session = Depends(get_db)):
    """Fetch aggregated job discovery analytics and KPIs."""
    return get_discovery_analytics(db)

@router.get("/source-efficacy")
def get_source_efficacy(db: Session = Depends(get_db)):
    """Fetch per-source discovery and conversion efficacy metrics."""
    return get_source_efficacy_metrics(db)

@router.get("/sankey")
def get_sankey_diagram(
    source_platform: Optional[str] = Query("all"),
    category: Optional[str] = Query("all"),
    db: Session = Depends(get_db)
):
    """
    Fetch genuine interactive application pipeline Sankey data computed from
    real database records and historical stage transitions.
    """
    return get_application_sankey_data(
        db=db,
        source_platform=source_platform,
        category=category
    )
