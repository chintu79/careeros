from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.services.command_center import get_command_center_overview

router = APIRouter(prefix="/command-center", tags=["Intelligent Career Command Center"])

@router.get("")
def get_command_center(
    date_range: Optional[str] = Query("30d"),
    db: Session = Depends(get_db)
):
    """
    Fetch comprehensive Command Center metrics answering the 5 key career questions:
    1. What is happening with my applications?
    2. Which opportunities should I prioritize?
    3. What action should I take today?
    4. Where am I improving or struggling?
    5. What should I focus on next?
    """
    return get_command_center_overview(db=db, date_range=date_range)
