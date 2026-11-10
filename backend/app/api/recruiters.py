import math
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc
from sqlalchemy.orm.attributes import flag_modified

from backend.app.database import get_db
from backend.app.models.recruiter import RecruiterContact

router = APIRouter(prefix="/recruiters", tags=["Recruiter CRM"])

class RecruiterCreate(BaseModel):
    name: str
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    company: Optional[str] = None
    position: Optional[str] = None
    contact_source: Optional[str] = "Direct Outreach"
    notes: Optional[str] = None
    last_contact_date: Optional[datetime] = None

class RecruiterUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    company: Optional[str] = None
    position: Optional[str] = None
    contact_source: Optional[str] = None
    notes: Optional[str] = None
    last_contact_date: Optional[datetime] = None

class InteractionLogRequest(BaseModel):
    interaction_type: str # "email", "linkedin_message", "phone_screen", "interview", "note"
    summary: str
    date: Optional[datetime] = None
    follow_up_needed: Optional[bool] = False
    next_step: Optional[str] = None

def serialize_recruiter(r: RecruiterContact) -> Dict[str, Any]:
    if not r:
        return {}
    return {
        "id": r.id,
        "name": r.name,
        "email": r.email,
        "linkedin_url": r.linkedin_url,
        "company": r.company,
        "position": r.position,
        "contact_source": r.contact_source,
        "notes": r.notes,
        "last_contact_date": r.last_contact_date.isoformat() if r.last_contact_date else None,
        "interaction_history": r.interaction_history or [],
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None
    }

@router.get("")
def list_recruiters(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    company: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List recruiters with search by name, company, email and pagination."""
    query = db.query(RecruiterContact)
    if company:
        query = query.filter(RecruiterContact.company.ilike(f"%{company}%"))
    if search:
        query = query.filter(
            (RecruiterContact.name.ilike(f"%{search}%")) |
            (RecruiterContact.company.ilike(f"%{search}%")) |
            (RecruiterContact.email.ilike(f"%{search}%")) |
            (RecruiterContact.position.ilike(f"%{search}%"))
        )
        
    total = query.count()
    total_pages = max(1, math.ceil(total / page_size))
    items = query.order_by(desc(RecruiterContact.updated_at)).offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        "items": [serialize_recruiter(r) for r in items],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages
    }

@router.post("")
def create_recruiter(data: RecruiterCreate, db: Session = Depends(get_db)):
    """Add a new recruiter contact."""
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="Recruiter name is required")
        
    r = RecruiterContact(
        name=data.name.strip(),
        email=data.email.strip() if data.email else None,
        linkedin_url=data.linkedin_url.strip() if data.linkedin_url else None,
        company=data.company.strip() if data.company else None,
        position=data.position.strip() if data.position else None,
        contact_source=data.contact_source or "Direct Outreach",
        notes=data.notes,
        last_contact_date=data.last_contact_date or datetime.utcnow(),
        interaction_history=[]
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return serialize_recruiter(r)

@router.get("/{id}")
def get_recruiter_detail(id: int, db: Session = Depends(get_db)):
    """Retrieve recruiter details and interaction timeline."""
    r = db.query(RecruiterContact).filter(RecruiterContact.id == id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Recruiter contact not found")
    return serialize_recruiter(r)

@router.put("/{id}")
def update_recruiter(id: int, data: RecruiterUpdate, db: Session = Depends(get_db)):
    """Update recruiter contact fields."""
    r = db.query(RecruiterContact).filter(RecruiterContact.id == id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Recruiter contact not found")
        
    for field, val in data.dict(exclude_unset=True).items():
        if val is not None:
            setattr(r, field, val)
            
    r.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(r)
    return serialize_recruiter(r)

@router.delete("/{id}")
def delete_recruiter(id: int, db: Session = Depends(get_db)):
    """Delete recruiter contact."""
    r = db.query(RecruiterContact).filter(RecruiterContact.id == id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Recruiter contact not found")
    db.delete(r)
    db.commit()
    return {"message": "Recruiter contact deleted successfully"}

@router.post("/{id}/interactions")
def log_recruiter_interaction(id: int, req: InteractionLogRequest, db: Session = Depends(get_db)):
    """Log an interaction touchpoint with the recruiter and update last contact date."""
    r = db.query(RecruiterContact).filter(RecruiterContact.id == id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Recruiter contact not found")
        
    history = list(r.interaction_history or [])
    interaction_entry = {
        "id": f"int_{len(history) + 1}_{int(datetime.utcnow().timestamp())}",
        "type": req.interaction_type,
        "summary": req.summary.strip(),
        "date": req.date.isoformat() if req.date else datetime.utcnow().isoformat(),
        "follow_up_needed": req.follow_up_needed or False,
        "next_step": req.next_step,
        "logged_at": datetime.utcnow().isoformat()
    }
    history.append(interaction_entry)
    r.interaction_history = history
    flag_modified(r, "interaction_history")
    
    r.last_contact_date = req.date or datetime.utcnow()
    r.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(r)
    return {
        "message": "Interaction logged",
        "interaction": interaction_entry,
        "recruiter": serialize_recruiter(r)
    }
