from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.preferences import UserPreferences

router = APIRouter(prefix="/preferences", tags=["Preferences"])

class PreferencesUpdate(BaseModel):
    preferred_categories: Optional[List[str]] = None
    search_priorities: Optional[List[Dict[str, Any]]] = None
    preferred_locations: Optional[List[str]] = None
    paid_only: Optional[bool] = None
    allow_unpaid: Optional[bool] = None
    min_stipend: Optional[float] = None
    preferred_duration_months: Optional[int] = None
    workplace_types: Optional[List[str]] = None
    max_experience_years: Optional[int] = None
    student_only: Optional[bool] = None
    graduation_year: Optional[int] = None
    excluded_keywords: Optional[List[str]] = None
    excluded_companies: Optional[List[str]] = None

@router.get("")
def get_user_preferences(db: Session = Depends(get_db)):
    """Fetch stored user job search preferences."""
    pref = db.query(UserPreferences).first()
    if not pref:
        raise HTTPException(status_code=404, detail="Preferences not found")
    return pref

@router.put("")
def update_user_preferences(data: PreferencesUpdate, db: Session = Depends(get_db)):
    """Save user search preferences persistently."""
    pref = db.query(UserPreferences).first()
    if not pref:
        pref = UserPreferences()
        db.add(pref)
        
    for field, val in data.dict(exclude_unset=True).items():
        if val is not None:
            setattr(pref, field, val)
            
    pref.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(pref)
    return pref
