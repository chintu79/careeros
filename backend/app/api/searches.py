from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.database import get_db
from backend.app.models.saved_search import SavedSearch
from backend.app.models.search_history import SearchHistory

router = APIRouter(prefix="/searches", tags=["Searches"])

class SavedSearchCreate(BaseModel):
    name: str
    search_mode: str = "hybrid"
    query: str = ""
    filters: Dict[str, Any] = {}

@router.get("/saved")
def list_saved_searches(db: Session = Depends(get_db)):
    """List all saved searches ordered by creation timestamp."""
    items = db.query(SavedSearch).order_by(desc(SavedSearch.created_at)).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "search_mode": s.search_mode,
            "query": s.query,
            "filters": s.filters or {},
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None
        }
        for s in items
    ]

@router.post("/saved")
def create_saved_search(data: SavedSearchCreate, db: Session = Depends(get_db)):
    """Save a search with custom name, mode, and filter parameters."""
    saved = SavedSearch(
        name=data.name.strip(),
        search_mode=data.search_mode,
        query=data.query.strip(),
        filters=data.filters,
        created_at=datetime.utcnow(),
        last_run_at=datetime.utcnow()
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)
    return {
        "id": saved.id,
        "name": saved.name,
        "search_mode": saved.search_mode,
        "query": saved.query,
        "filters": saved.filters,
        "created_at": saved.created_at.isoformat()
    }

@router.delete("/saved/{id}")
def delete_saved_search(id: int, db: Session = Depends(get_db)):
    """Delete a saved search."""
    item = db.query(SavedSearch).filter(SavedSearch.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Saved search not found")
    db.delete(item)
    db.commit()
    return {"success": True, "id": id}

@router.get("/history")
def list_search_history(
    limit: int = Query(15, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Retrieve recent unique search history items."""
    items = db.query(SearchHistory).order_by(desc(SearchHistory.created_at)).limit(limit).all()
    return [
        {
            "id": h.id,
            "query": h.query,
            "search_mode": h.search_mode,
            "filters": h.filters or {},
            "results_count": h.results_count,
            "created_at": h.created_at.isoformat() if h.created_at else None
        }
        for h in items
    ]

@router.delete("/history")
def clear_search_history(db: Session = Depends(get_db)):
    """Clear all logged search history."""
    db.query(SearchHistory).delete()
    db.commit()
    return {"success": True, "message": "Search history cleared"}
