from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Optional
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.connectors.manual_import import ManualImportConnector
from backend.app.connectors.india_platforms import parse_job_alert_email
from backend.app.models.opportunity import Opportunity

router = APIRouter(prefix="/import", tags=["Job Import"])
connector = ManualImportConnector()

class UrlImportRequest(BaseModel):
    url: str

class PasteImportRequest(BaseModel):
    title: str
    company_name: str
    location: Optional[str] = "Remote, India"
    description: str
    stipend_text: Optional[str] = "Competitive Stipend"
    original_url: Optional[str] = ""

class EmailAlertImportRequest(BaseModel):
    email_text: str
    platform_hint: Optional[str] = "internshala"

@router.post("/url")
async def import_job_from_url(req: UrlImportRequest, db: Session = Depends(get_db)):
    """Fetch, extract, and ingest a job opportunity from a public URL."""
    try:
        raw_data = await connector.extract_from_url(req.url)
        stats = await connector.process_and_save_jobs(db, [raw_data])
        
        # Retrieve the newly created or merged opportunity
        opp = db.query(Opportunity).filter(Opportunity.original_url == raw_data["original_url"]).first()
        if not opp:
            opp = db.query(Opportunity).order_by(Opportunity.id.desc()).first()
            
        return {
            "success": True,
            "message": "Opportunity successfully imported and analyzed.",
            "stats": stats,
            "opportunity_id": opp.id if opp else None
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail="Operation failed")

@router.post("/paste")
async def import_job_from_paste(req: PasteImportRequest, db: Session = Depends(get_db)):
    """Ingest a job opportunity from pasted title and description text."""
    try:
        raw_data = connector.parse_pasted_text(
            title=req.title,
            company_name=req.company_name,
            location=req.location or "Remote, India",
            description=req.description,
            stipend_text=req.stipend_text or "",
            original_url=req.original_url or ""
        )
        stats = await connector.process_and_save_jobs(db, [raw_data])
        
        opp = db.query(Opportunity).filter(Opportunity.original_url == raw_data["original_url"]).first()
        if not opp:
            opp = db.query(Opportunity).order_by(Opportunity.id.desc()).first()

        return {
            "success": True,
            "message": "Pasted job listing analyzed and added to discovery database.",
            "stats": stats,
            "opportunity_id": opp.id if opp else None
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail="Operation failed")

@router.post("/email-alert")
async def import_from_email_alert(req: EmailAlertImportRequest, db: Session = Depends(get_db)):
    """Parse and ingest job alert email notification text."""
    try:
        raw_data = parse_job_alert_email(req.email_text, platform_hint=req.platform_hint or "internshala")
        stats = await connector.process_and_save_jobs(db, [raw_data])
        
        opp = db.query(Opportunity).filter(Opportunity.original_url == raw_data["original_url"]).first()
        return {
            "success": True,
            "message": "Email alert parsed and imported into discovery feed.",
            "stats": stats,
            "opportunity_id": opp.id if opp else None
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail="Operation failed")
