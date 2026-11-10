import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.database import get_db
from backend.app.models.integration import EmailMessageRecord
from backend.app.models.application import ApplicationRecord
from backend.app.models.application_transition import ApplicationStageTransition
from backend.app.services.email_intelligence_service import process_incoming_email, ALL_CATEGORIES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/email-intelligence", tags=["Email Intelligence Platform"])

class RawEmailParseRequest(BaseModel):
    subject: str
    body_text: str
    sender: str
    recipient: Optional[str] = None
    application_id: Optional[int] = None

class AssociateApplicationRequest(BaseModel):
    application_id: int

def serialize_email_message(msg: EmailMessageRecord, db: Session) -> Dict[str, Any]:
    app = None
    if msg.application_id:
        app = db.query(ApplicationRecord).filter(ApplicationRecord.id == msg.application_id).first()

    return {
        "id": msg.id,
        "connection_id": msg.connection_id,
        "application_id": msg.application_id,
        "application_company": app.company_name if app else (msg.extracted_data or {}).get("company_name"),
        "application_title": app.job_title if app else (msg.extracted_data or {}).get("role_title"),
        "application_status": app.status if app else None,
        "provider_message_id": msg.provider_message_id,
        "thread_id": msg.thread_id,
        "sender": msg.sender,
        "sender_email": msg.sender_email,
        "sender_name": msg.sender_name,
        "recipient": msg.recipient,
        "subject": msg.subject,
        "snippet": msg.snippet,
        "body_plain": msg.body_plain,
        "received_at": msg.received_at.isoformat() if msg.received_at else None,
        "detected_category": msg.detected_category,
        "confidence_score": msg.confidence_score,
        "is_low_confidence": msg.confidence_score < 0.85,
        "extracted_data": msg.extracted_data or {},
        "suggested_stage": msg.suggested_stage,
        "review_status": msg.review_status,
        "user_action_at": msg.user_action_at.isoformat() if msg.user_action_at else None,
        "created_at": msg.created_at.isoformat() if msg.created_at else None
    }

@router.get("/messages")
def list_email_messages(
    review_status: Optional[str] = Query(None, description="pending_review, approved, dismissed"),
    category: Optional[str] = Query(None),
    application_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Lists detected career communications with category, confidence, and approval status."""
    query = db.query(EmailMessageRecord)

    if review_status:
        query = query.filter(EmailMessageRecord.review_status == review_status)
    if category:
        query = query.filter(EmailMessageRecord.detected_category == category)
    if application_id:
        query = query.filter(EmailMessageRecord.application_id == application_id)

    total = query.count()
    items = query.order_by(desc(EmailMessageRecord.received_at)).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": [serialize_email_message(m, db) for m in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pending_review_count": db.query(EmailMessageRecord).filter(EmailMessageRecord.review_status == "pending_review").count()
    }

@router.post("/messages/{id}/approve")
def approve_email_update(id: int, db: Session = Depends(get_db)):
    """
    User approval workflow for consequential application status changes:
    - Verifies message exists and has a suggested stage
    - Updates ApplicationRecord stage
    - Records an ApplicationStageTransition audit entry
    - Marks review_status as approved
    - Idempotent: does not create duplicate transitions if already approved
    """
    msg = db.query(EmailMessageRecord).filter(EmailMessageRecord.id == id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Email message not found")

    if msg.review_status == "approved":
        return {
            "success": True,
            "message": "Update was already approved previously.",
            "email": serialize_email_message(msg, db)
        }

    app = None
    if msg.application_id:
        app = db.query(ApplicationRecord).filter(ApplicationRecord.id == msg.application_id).first()

    transition_applied = False
    old_stage = None
    new_stage = None

    if app and msg.suggested_stage and app.status != msg.suggested_stage:
        old_stage = app.status
        new_stage = msg.suggested_stage

        # Create audit stage transition record
        transition = ApplicationStageTransition(
            application_id=app.id,
            from_stage=old_stage,
            to_stage=new_stage,
            transitioned_at=datetime.utcnow(),
            notes=f"Approved from Email Intelligence: '{msg.subject}' ({msg.detected_category})"
        )
        db.add(transition)

        # Update application status
        app.status = new_stage
        
        # If interview invite with meeting link, update interview schedule
        extracted = msg.extracted_data or {}
        if msg.detected_category == "interview_invitation" and extracted.get("meeting_link"):
            schedules = list(app.interview_schedule or [])
            schedules.append({
                "id": f"email_{msg.id}",
                "round_name": "Technical Interview (from Email)",
                "date": datetime.utcnow().isoformat(),
                "meeting_link": extracted.get("meeting_link"),
                "format": extracted.get("meeting_platform") or "virtual_video",
                "notes": f"Scheduled via email: {msg.subject}"
            })
            app.interview_schedule = schedules

        transition_applied = True

    msg.review_status = "approved"
    msg.user_action_at = datetime.utcnow()
    db.commit()
    db.refresh(msg)

    return {
        "success": True,
        "transition_applied": transition_applied,
        "old_stage": old_stage,
        "new_stage": new_stage,
        "email": serialize_email_message(msg, db)
    }

@router.post("/messages/{id}/dismiss")
def dismiss_email_update(id: int, db: Session = Depends(get_db)):
    """
    Dismisses the suggested update without modifying the application tracker.
    Preserves audit history.
    """
    msg = db.query(EmailMessageRecord).filter(EmailMessageRecord.id == id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Email message not found")

    msg.review_status = "dismissed"
    msg.user_action_at = datetime.utcnow()
    db.commit()
    db.refresh(msg)

    return {
        "success": True,
        "message": "Suggested tracker update dismissed. Application status remains unchanged.",
        "email": serialize_email_message(msg, db)
    }

@router.post("/messages/{id}/associate")
def associate_email_to_application(id: int, payload: AssociateApplicationRequest, db: Session = Depends(get_db)):
    """Manually links an email to an application when automatic association was uncertain."""
    msg = db.query(EmailMessageRecord).filter(EmailMessageRecord.id == id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Email message not found")

    app = db.query(ApplicationRecord).filter(ApplicationRecord.id == payload.application_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Target application not found")

    msg.application_id = app.id
    db.commit()
    db.refresh(msg)

    return {
        "success": True,
        "message": f"Associated email '{msg.subject}' with {app.company_name} ({app.job_title}).",
        "email": serialize_email_message(msg, db)
    }

@router.post("/parse-raw")
def parse_raw_email(payload: RawEmailParseRequest, db: Session = Depends(get_db)):
    """
    Ingests and classifies raw pasted email text / headers.
    Enables instant user verification of any email without third-party OAuth setup.
    """
    import uuid
    raw_message = {
        "provider_message_id": f"raw_{uuid.uuid4().hex[:12]}",
        "subject": payload.subject,
        "body_plain": payload.body_text,
        "sender": payload.sender,
        "recipient": payload.recipient or "user@careeros.local",
        "received_at": datetime.utcnow()
    }
    record = process_incoming_email(db, raw_message)
    if payload.application_id:
        record.application_id = payload.application_id
        db.commit()
        db.refresh(record)

    return serialize_email_message(record, db)
