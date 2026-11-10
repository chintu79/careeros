import re
import math
import urllib.parse
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

from backend.app.database import get_db
from backend.app.models.company import Company
from backend.app.models.opportunity import Opportunity
from backend.app.connectors.greenhouse import GreenhouseConnector
from backend.app.connectors.lever import LeverConnector
from backend.app.connectors.ashby import AshbyConnector
from backend.app.connectors.smartrecruiters import SmartRecruitersConnector

router = APIRouter(prefix="/companies", tags=["Companies"])

def detect_ats_provider_from_url(url: str) -> Dict[str, Any]:
    """
    Auto-detects ATS provider (Greenhouse, Lever, Ashby, SmartRecruiters) and extracts
    the board/company identifier from a career page URL.
    """
    if not url or not url.strip():
        return {"detected": False, "ats_provider": "greenhouse", "ats_board_id": ""}
    
    clean_url = url.strip()
    
    # Greenhouse patterns:
    # - https://boards.greenhouse.io/{board_id}
    # - https://boards.greenhouse.io/embed/job_board?for={board_id}
    # - https://job-boards.greenhouse.io/{board_id}
    if "greenhouse.io" in clean_url:
        parsed = urllib.parse.urlsplit(clean_url)
        params = urllib.parse.parse_qs(parsed.query)
        if "for" in params and params["for"]:
            return {"detected": True, "ats_provider": "greenhouse", "ats_board_id": params["for"][0]}
        
        path_parts = [p for p in parsed.path.split("/") if p and p not in ["embed", "jobs"]]
        if path_parts:
            return {"detected": True, "ats_provider": "greenhouse", "ats_board_id": path_parts[0]}
        return {"detected": True, "ats_provider": "greenhouse", "ats_board_id": ""}

    # Lever patterns:
    # - https://jobs.lever.co/{site}
    if "lever.co" in clean_url:
        parsed = urllib.parse.urlsplit(clean_url)
        path_parts = [p for p in parsed.path.split("/") if p]
        if path_parts:
            return {"detected": True, "ats_provider": "lever", "ats_board_id": path_parts[0]}
        return {"detected": True, "ats_provider": "lever", "ats_board_id": ""}

    # Ashby patterns:
    # - https://jobs.ashbyhq.com/{org}
    if "ashbyhq.com" in clean_url:
        parsed = urllib.parse.urlsplit(clean_url)
        path_parts = [p for p in parsed.path.split("/") if p]
        if path_parts:
            return {"detected": True, "ats_provider": "ashby", "ats_board_id": path_parts[0]}
        return {"detected": True, "ats_provider": "ashby", "ats_board_id": ""}

    # SmartRecruiters patterns:
    # - https://careers.smartrecruiters.com/{company}
    # - https://jobs.smartrecruiters.com/{company}
    if "smartrecruiters.com" in clean_url:
        parsed = urllib.parse.urlsplit(clean_url)
        path_parts = [p for p in parsed.path.split("/") if p]
        if path_parts:
            return {"detected": True, "ats_provider": "smartrecruiters", "ats_board_id": path_parts[0]}
        return {"detected": True, "ats_provider": "smartrecruiters", "ats_board_id": ""}

    return {"detected": False, "ats_provider": "greenhouse", "ats_board_id": ""}

class DetectATSRequest(BaseModel):
    career_url: str

class CompanyCreate(BaseModel):
    name: str
    website: Optional[str] = None
    career_url: Optional[str] = None
    industry: Optional[str] = "Technology"
    hq_location: Optional[str] = "Bengaluru, India"
    ats_provider: Optional[str] = None # auto-detected if not specified
    ats_board_id: Optional[str] = None
    company_size: Optional[str] = "100-500"
    monitoring_status: Optional[str] = "active"

class CompanyUpdate(BaseModel):
    website: Optional[str] = None
    career_url: Optional[str] = None
    industry: Optional[str] = None
    hq_location: Optional[str] = None
    ats_provider: Optional[str] = None
    ats_board_id: Optional[str] = None
    company_size: Optional[str] = None
    monitoring_status: Optional[str] = None

@router.post("/detect-ats")
def detect_ats_endpoint(data: DetectATSRequest):
    """Detect ATS provider and board ID from a career page URL."""
    return detect_ats_provider_from_url(data.career_url)

@router.get("")
def list_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    search: Optional[str] = None,
    ats_provider: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List monitored company career pages with server-side pagination and discovery stats."""
    query = db.query(Company)
    if search:
        query = query.filter(or_(Company.name.ilike(f"%{search}%"), Company.industry.ilike(f"%{search}%")))
    if ats_provider:
        query = query.filter(Company.ats_provider == ats_provider)
    if status:
        query = query.filter(Company.monitoring_status == status)
        
    total = query.count()
    total_pages = max(1, math.ceil(total / page_size))
    companies = query.order_by(Company.name.asc()).offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        "items": companies,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages
    }

@router.post("")
def add_company(data: CompanyCreate, db: Session = Depends(get_db)):
    """Add a new company to the career page monitoring directory."""
    existing = db.query(Company).filter(Company.name.ilike(data.name.strip())).first()
    if existing:
        raise HTTPException(status_code=400, detail="Company already exists in monitoring directory")
        
    ats_prov = (data.ats_provider or "").lower().strip()
    ats_bid = (data.ats_board_id or "").strip()

    # Attempt auto-detection if career_url provided
    if data.career_url:
        detected = detect_ats_provider_from_url(data.career_url)
        if detected["detected"]:
            if not ats_prov:
                ats_prov = detected["ats_provider"]
            if not ats_bid:
                ats_bid = detected["ats_board_id"]

    if not ats_prov:
        ats_prov = "greenhouse"
    if not ats_bid:
        ats_bid = data.name.strip().lower().replace(" ", "")

    comp = Company(
        name=data.name.strip(),
        website=data.website,
        career_url=data.career_url,
        industry=data.industry,
        hq_location=data.hq_location,
        ats_provider=ats_prov,
        ats_board_id=ats_bid,
        company_size=data.company_size,
        monitoring_status=data.monitoring_status or "active"
    )
    db.add(comp)
    db.commit()
    db.refresh(comp)
    return comp

@router.put("/{id}")
def update_company(id: int, data: CompanyUpdate, db: Session = Depends(get_db)):
    comp = db.query(Company).filter(Company.id == id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Company not found")
        
    for field, val in data.dict(exclude_unset=True).items():
        if val is not None:
            setattr(comp, field, val)
            
    comp.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(comp)
    return comp

@router.delete("/{id}")
def delete_company(id: int, db: Session = Depends(get_db)):
    comp = db.query(Company).filter(Company.id == id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Company not found")
    db.delete(comp)
    db.commit()
    return {"success": True, "message": f"Company {comp.name} removed from monitoring."}

@router.post("/{id}/sync")
async def sync_single_company(id: int, db: Session = Depends(get_db)):
    """Fetch opportunities directly from this company's configured ATS career page with active board reconciliation."""
    comp = db.query(Company).filter(Company.id == id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Company not found")
        
    ats = comp.ats_provider.lower()
    board = comp.ats_board_id or comp.name.lower().replace(" ", "")
    
    if ats == "greenhouse":
        connector = GreenhouseConnector(board_id=board, company_name=comp.name)
    elif ats == "lever":
        connector = LeverConnector(site=board, company_name=comp.name)
    elif ats == "ashby":
        connector = AshbyConnector(organization=board, company_name=comp.name)
    elif ats == "smartrecruiters":
        connector = SmartRecruitersConnector(company_identifier=board, company_name=comp.name)
    else:
        raise HTTPException(status_code=400, detail=f"Direct sync not supported for ATS provider '{ats}'")
        
    raw_jobs = await connector.fetch_jobs()
    stats = await connector.process_and_save_jobs(
        db, 
        raw_jobs, 
        verify_links=True, 
        reconcile_board=True, 
        reconcile_company=comp.name
    )
    
    comp.last_sync_at = datetime.utcnow()
    
    # Recalculate total active opportunities for this company
    total_active = db.query(Opportunity).filter(
        Opportunity.company_name.ilike(comp.name),
        Opportunity.status.in_(["verified", "active_verified", "newly_discovered"])
    ).count()
    comp.opportunities_count = total_active
    db.commit()
    
    return {
        "success": True,
        "company": comp.name,
        "ats_provider": ats,
        "active_opportunities_count": total_active,
        "stats": stats
    }
