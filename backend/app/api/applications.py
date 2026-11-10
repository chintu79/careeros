import math
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from sqlalchemy.orm.attributes import flag_modified

from backend.app.database import get_db
from backend.app.core.auth import get_current_user_id
from backend.app.models.application import ApplicationRecord
from backend.app.models.application_transition import ApplicationStageTransition
from backend.app.models.opportunity import Opportunity
from backend.app.models.candidate import CandidateProfile
from backend.app.models.resume import ResumeDocument
from backend.app.models.recruiter import RecruiterContact
from backend.app.services.application_service import handoff_to_application_tracker
from backend.app.services.assisted_application_service import (
    prepare_assisted_application,
    record_application_submission
)
from backend.app.services.application_analytics_service import compute_application_analytics
from backend.app.services.follow_up_intelligence_service import (
    get_follow_up_intelligence,
    generate_follow_up_email_draft
)
from backend.app.models.integration import CalendarEventRecord
from backend.app.services.unified_activity_service import fetch_unified_activities

router = APIRouter(prefix="/applications", tags=["Applications & Tracking"])

class HandoffRequest(BaseModel):
    opportunity_id: int
    initial_status: Optional[str] = "ready_to_apply"
    user_notes: Optional[str] = ""
    recruiter_name: Optional[str] = None
    recruiter_email: Optional[str] = None
    recruiter_linkedin: Optional[str] = None
    recruiter_id: Optional[int] = None
    salary_or_stipend: Optional[str] = None

class StatusUpdateRequest(BaseModel):
    new_status: str
    notes: Optional[str] = None

class AssistedSubmitRequest(BaseModel):
    opportunity_id: int
    submission_mode: Optional[str] = "assisted"
    resume_id: Optional[int] = None
    resume_version_number: Optional[int] = None
    notes: Optional[str] = None
    submission_verified: Optional[bool] = False
    salary_or_stipend: Optional[str] = None
    cover_letter_text: Optional[str] = None

class ApplicationUpdate(BaseModel):
    status: Optional[str] = None
    user_notes: Optional[str] = None
    recruiter_id: Optional[int] = None
    recruiter_name: Optional[str] = None
    recruiter_position: Optional[str] = None
    recruiter_email: Optional[str] = None
    recruiter_linkedin: Optional[str] = None
    follow_up_date: Optional[datetime] = None
    salary_or_stipend: Optional[str] = None
    cover_letter_text: Optional[str] = None
    resume_id: Optional[int] = None
    resume_version_number: Optional[int] = None
    interview_schedule: Optional[List[Dict[str, Any]]] = None

class FollowUpGenerateRequest(BaseModel):
    tone: Optional[str] = "inquisitive" # "inquisitive", "post_interview", "portfolio_update"
    custom_note: Optional[str] = None

class FollowUpApproveRequest(BaseModel):
    advance_days: Optional[int] = 7
    notes: Optional[str] = "Follow-up email dispatched to recruiter"

class ScheduleInterviewRequest(BaseModel):
    round_name: str
    date: datetime
    format: Optional[str] = "virtual_video" # "virtual_video", "in_person", "phone_screen", "take_home"
    interviewer: Optional[str] = None
    meeting_link: Optional[str] = None
    notes: Optional[str] = None

def serialize_app(a: ApplicationRecord) -> dict:
    if not a:
        return {}
    return {
        "id": a.id,
        "opportunity_id": a.opportunity_id,
        "company_name": a.company_name,
        "job_title": a.job_title,
        "original_url": a.original_url,
        "status": a.status,
        "applied_date": a.applied_date.isoformat() if a.applied_date else None,
        "match_score": a.match_score,
        "resume_id": a.resume_id,
        "resume_version_number": a.resume_version_number,
        "submission_mode": a.submission_mode,
        "submission_verified": a.submission_verified,
        "follow_up_date": a.follow_up_date.isoformat() if a.follow_up_date else None,
        "salary_or_stipend": a.salary_or_stipend,
        "cover_letter_text": a.cover_letter_text,
        "cover_letter_points": a.cover_letter_points or [],
        "user_notes": a.user_notes,
        "recruiter_id": a.recruiter_id,
        "recruiter_name": a.recruiter_name,
        "recruiter_position": a.recruiter_position,
        "recruiter_email": a.recruiter_email,
        "recruiter_linkedin": a.recruiter_linkedin,
        "interview_schedule": a.interview_schedule or [],
        "tailored_resume_summary": a.tailored_resume_summary,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }

# ----------------- STATIC ANALYTICS & INTELLIGENCE ENDPOINTS (Before /{id}) -----------------

@router.get("/analytics")
def get_application_analytics(db: Session = Depends(get_db)):
    """
    Returns mathematically defined application response rate, interview conversion rate,
    offer conversion rate, average response time, source performance, and resume-version yield.
    """
    return compute_application_analytics(db)

@router.get("/follow-ups")
def get_follow_up_alerts(
    stale_days: int = Query(7, ge=1, le=60),
    db: Session = Depends(get_db)
):
    """
    Identifies applications needing follow-up: unanswered beyond threshold,
    scheduled follow-up dates due, upcoming interviews, and approaching deadlines.
    """
    return get_follow_up_intelligence(db, stale_days_threshold=stale_days)

@router.get("/timeline")
def get_application_timeline(
    limit: int = Query(50, ge=1, le=200),
    filter_category: str = Query("all", description="all, emails, interviews, deadlines, follow_ups, updates"),
    application_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Returns unified centralized activity timeline combining stage transitions,
    incoming emails, scheduled interviews, assessment deadlines, and follow-ups.
    """
    events = fetch_unified_activities(db=db, limit=limit, filter_category=filter_category, application_id=application_id)
    return {"events": events}

@router.get("/calendar")
def get_application_calendar(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Returns calendar-mapped events across all applications:
    submission dates, follow-up deadlines, internal schedules, portal closing dates,
    and synced Google & Microsoft calendar events with meeting links and time zones.
    """
    calendar_events = []
    apps = db.query(ApplicationRecord).all()
    
    for a in apps:
        opp = db.query(Opportunity).filter(Opportunity.id == a.opportunity_id).first() if a.opportunity_id else None
        
        # Applied milestone
        if a.applied_date:
            calendar_events.append({
                "id": f"app_{a.id}_applied",
                "application_id": a.id,
                "title": f"Applied: {a.company_name} - {a.job_title}",
                "company": a.company_name,
                "date": a.applied_date.strftime("%Y-%m-%d"),
                "time": a.applied_date.strftime("%H:%M") if a.applied_date else None,
                "event_type": "applied",
                "status": a.status
            })
            
        # Follow-up milestone
        if a.follow_up_date:
            calendar_events.append({
                "id": f"app_{a.id}_follow_up",
                "application_id": a.id,
                "title": f"Follow-up: {a.company_name}",
                "company": a.company_name,
                "date": a.follow_up_date.strftime("%Y-%m-%d"),
                "time": a.follow_up_date.strftime("%H:%M"),
                "event_type": "follow_up_due",
                "status": a.status
            })
            
        # Scheduled Interviews
        for item in (a.interview_schedule or []):
            if item.get("date"):
                d_str = item["date"].split("T")[0]
                t_str = item["date"].split("T")[1][:5] if "T" in item["date"] else "10:00"
                calendar_events.append({
                    "id": f"int_{item.get('id', d_str)}",
                    "application_id": a.id,
                    "title": f"{item.get('round_name', 'Interview')} ({a.company_name})",
                    "company": a.company_name,
                    "date": d_str,
                    "time": t_str,
                    "event_type": "interview",
                    "status": a.status,
                    "meeting_link": item.get("meeting_link"),
                    "meeting_platform": item.get("format") or "Virtual Video",
                    "details": item
                })
                
        # Portal deadline
        opp_deadline = getattr(opp, "deadline_at", None) if opp else None
        if opp_deadline:
            calendar_events.append({
                "id": f"opp_{opp.id}_deadline",
                "application_id": a.id,
                "title": f"Deadline: {a.company_name}",
                "company": a.company_name,
                "date": opp_deadline.strftime("%Y-%m-%d"),
                "event_type": "deadline",
                "status": a.status
            })

    # Synced Google & Microsoft Calendar events
    synced_events = db.query(CalendarEventRecord).filter(CalendarEventRecord.status != "cancelled").all()
    for ce in synced_events:
        d_str = ce.start_time.strftime("%Y-%m-%d")
        t_str = ce.start_time.strftime("%H:%M")
        calendar_events.append({
            "id": f"synced_{ce.id}",
            "application_id": ce.application_id,
            "title": ce.title,
            "company": ce.company_name or "Employer",
            "date": d_str,
            "time": t_str,
            "event_type": ce.event_type,
            "status": ce.status,
            "meeting_platform": ce.meeting_platform,
            "meeting_link": ce.meeting_link,
            "time_zone": ce.time_zone,
            "details": {
                "meeting_link": ce.meeting_link,
                "meeting_platform": ce.meeting_platform,
                "location": ce.location,
                "prep_notes": ce.prep_notes,
                "time_zone": ce.time_zone
            }
        })

    return {"events": calendar_events}

# ----------------- STANDARD LIST & DETAIL ENDPOINTS -----------------

@router.get("")
def list_applications(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    status: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = "created_at",
    sort_order: Optional[str] = "desc",
    db: Session = Depends(get_db)
):
    """List applications handed off to tracker with server-side pagination and rich sorting."""
    query = db.query(ApplicationRecord)
    if status:
        if status == "interviewing":
            query = query.filter(or_(ApplicationRecord.status == "interviewing", ApplicationRecord.status.ilike("%interview%")))
        else:
            query = query.filter(ApplicationRecord.status == status)
    if search:
        query = query.filter(
            or_(
                ApplicationRecord.company_name.ilike(f"%{search}%"),
                ApplicationRecord.job_title.ilike(f"%{search}%"),
                ApplicationRecord.recruiter_name.ilike(f"%{search}%")
            )
        )
        
    total = query.count()
    total_pages = max(1, math.ceil(total / page_size))
    
    order_col = ApplicationRecord.created_at
    if sort_by == "applied_date":
        order_col = ApplicationRecord.applied_date
    elif sort_by == "follow_up_date":
        order_col = ApplicationRecord.follow_up_date
    elif sort_by == "match_score":
        order_col = ApplicationRecord.match_score
    elif sort_by == "company_name":
        order_col = ApplicationRecord.company_name

    if sort_order == "asc":
        query = query.order_by(order_col.asc())
    else:
        query = query.order_by(order_col.desc())
        
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        "items": [serialize_app(a) for a in items],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages
    }

@router.get("/{id}")
def get_application_detail(id: int, db: Session = Depends(get_db)):
    """Retrieve application details including historical stage transitions and recruiter info."""
    app_record = db.query(ApplicationRecord).filter(ApplicationRecord.id == id).first()
    if not app_record:
        raise HTTPException(status_code=404, detail="Application record not found")
        
    transitions = db.query(ApplicationStageTransition).filter(
        ApplicationStageTransition.application_id == id
    ).order_by(ApplicationStageTransition.transitioned_at.asc()).all()
    
    recruiter = None
    if app_record.recruiter_id:
        rec = db.query(RecruiterContact).filter(RecruiterContact.id == app_record.recruiter_id).first()
        if rec:
            recruiter = {
                "id": rec.id,
                "name": rec.name,
                "email": rec.email,
                "linkedin_url": rec.linkedin_url,
                "position": rec.position,
                "company": rec.company
            }
            
    return {
        "application": serialize_app(app_record),
        "transitions": transitions,
        "recruiter": recruiter
    }

@router.post("/handoff")
def create_application_handoff(req: HandoffRequest, db: Session = Depends(get_db)):
    """Hand off discovered opportunity to application tracker."""
    app_record = handoff_to_application_tracker(
        db=db,
        opportunity_id=req.opportunity_id,
        initial_status=req.initial_status or "ready_to_apply",
        user_notes=req.user_notes or "",
        recruiter_name=req.recruiter_name,
        recruiter_email=req.recruiter_email,
        recruiter_linkedin=req.recruiter_linkedin
    )
    if req.salary_or_stipend:
        app_record.salary_or_stipend = req.salary_or_stipend
    if req.recruiter_id:
        app_record.recruiter_id = req.recruiter_id

    trans = ApplicationStageTransition(
        application_id=app_record.id,
        from_stage="discovered",
        to_stage=app_record.status,
        transitioned_at=datetime.utcnow(),
        notes="Opportunity handed off to tracker"
    )
    db.add(trans)
    db.commit()
    db.refresh(app_record)
    return serialize_app(app_record)

@router.post("/prepare/{opportunity_id}")
def prepare_application_materials(
    opportunity_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Prepare and preview application materials (resume, profile details, answers) before submission."""
    try:
        data = prepare_assisted_application(db, opportunity_id, user_id=user_id)
        return data
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail='Not authorized')
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Internal error")

@router.post("/submit-assisted")
def submit_assisted_application(
    req: AssistedSubmitRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Confirm assisted application submission, record stage transition, and set follow-up."""
    opp = db.query(Opportunity).filter(Opportunity.id == req.opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    if opp.user_id is not None and opp.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this opportunity")

    if req.resume_id:
        res_doc = db.query(ResumeDocument).filter(ResumeDocument.id == req.resume_id).first()
        if not res_doc:
            raise HTTPException(status_code=404, detail="Resume document not found")
        if res_doc.user_id != user_id:
            raise HTTPException(status_code=403, detail="Forbidden: Cannot associate another user's resume")

    try:
        app_record = record_application_submission(
            db=db,
            opportunity_id=req.opportunity_id,
            submission_mode=req.submission_mode or "assisted",
            resume_id=req.resume_id,
            notes=req.notes or "",
            submission_verified=req.submission_verified or False
        )
        if req.salary_or_stipend:
            app_record.salary_or_stipend = req.salary_or_stipend
        if req.cover_letter_text:
            app_record.cover_letter_text = req.cover_letter_text
        if req.resume_version_number:
            app_record.resume_version_number = req.resume_version_number
            
        db.commit()
        db.refresh(app_record)
        return serialize_app(app_record)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Internal error")

@router.put("/{id}")
def update_application(id: int, data: ApplicationUpdate, db: Session = Depends(get_db)):
    """Update application tracking stage, recruiter links, interview schedule, and financial info."""
    app_record = db.query(ApplicationRecord).filter(ApplicationRecord.id == id).first()
    if not app_record:
        raise HTTPException(status_code=404, detail="Application record not found")
        
    old_status = app_record.status
    for field, val in data.dict(exclude_unset=True).items():
        if val is not None:
            setattr(app_record, field, val)
            
    if data.interview_schedule is not None:
        flag_modified(app_record, "interview_schedule")

    if data.status and data.status != old_status:
        trans = ApplicationStageTransition(
            application_id=app_record.id,
            from_stage=old_status,
            to_stage=data.status,
            transitioned_at=datetime.utcnow(),
            notes=data.user_notes or f"Moved from {old_status} to {data.status}"
        )
        db.add(trans)
        if data.status == "applied" and not app_record.applied_date:
            app_record.applied_date = datetime.utcnow()
            if not app_record.follow_up_date:
                app_record.follow_up_date = datetime.utcnow() + timedelta(days=7)
                
    app_record.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(app_record)
    return serialize_app(app_record)

@router.delete("/{id}")
def delete_application(id: int, db: Session = Depends(get_db)):
    """Remove application from tracking."""
    app_record = db.query(ApplicationRecord).filter(ApplicationRecord.id == id).first()
    if not app_record:
        raise HTTPException(status_code=404, detail="Application record not found")
    db.delete(app_record)
    db.commit()
    return {"message": "Application removed from tracker"}

# ----------------- FOLLOW-UP DRAFT & APPROVAL WORKFLOWS -----------------

@router.post("/{id}/generate-follow-up")
def generate_follow_up(id: int, req: FollowUpGenerateRequest, db: Session = Depends(get_db)):
    """
    Generates a personalized email follow-up draft using candidate profile and target role context.
    Draft requires explicit user approval before dispatch.
    """
    app_record = db.query(ApplicationRecord).filter(ApplicationRecord.id == id).first()
    if not app_record:
        raise HTTPException(status_code=404, detail="Application record not found")
        
    profile = db.query(CandidateProfile).first()
    draft = generate_follow_up_email_draft(
        application=app_record,
        profile=profile,
        tone=req.tone or "inquisitive",
        custom_note=req.custom_note
    )
    return draft

@router.post("/{id}/approve-follow-up")
def approve_and_record_follow_up(id: int, req: FollowUpApproveRequest, db: Session = Depends(get_db)):
    """
    Explicit user approval of follow-up dispatch.
    Records stage touchpoint, updates last_contact_date on linked recruiter, and advances next follow_up_date.
    """
    app_record = db.query(ApplicationRecord).filter(ApplicationRecord.id == id).first()
    if not app_record:
        raise HTTPException(status_code=404, detail="Application record not found")
        
    now = datetime.utcnow()
    advance_days = req.advance_days or 7
    app_record.follow_up_date = now + timedelta(days=advance_days)
    app_record.updated_at = now
    
    # Update linked recruiter if present
    if app_record.recruiter_id:
        rec = db.query(RecruiterContact).filter(RecruiterContact.id == app_record.recruiter_id).first()
        if rec:
            rec.last_contact_date = now
            history = list(rec.interaction_history or [])
            history.append({
                "id": f"int_followup_{int(now.timestamp())}",
                "type": "email",
                "summary": f"Follow-up sent for {app_record.job_title}: {req.notes}",
                "date": now.isoformat(),
                "follow_up_needed": True,
                "next_step": f"Check response in {advance_days} days",
                "logged_at": now.isoformat()
            })
            rec.interaction_history = history
            flag_modified(rec, "interaction_history")
            rec.updated_at = now

    # Record transition touchpoint
    trans = ApplicationStageTransition(
        application_id=app_record.id,
        from_stage=app_record.status,
        to_stage=app_record.status,
        transitioned_at=now,
        notes=f"User approved follow-up email dispatch: {req.notes}"
    )
    db.add(trans)
    db.commit()
    db.refresh(app_record)
    
    return {
        "message": "Follow-up approved and recorded",
        "new_follow_up_date": app_record.follow_up_date.isoformat(),
        "application": serialize_app(app_record)
    }

@router.post("/{id}/schedule-interview")
def schedule_application_interview(id: int, req: ScheduleInterviewRequest, db: Session = Depends(get_db)):
    """
    Adds a scheduled interview round to application, transitions status to interviewing,
    and sets follow-up.
    """
    app_record = db.query(ApplicationRecord).filter(ApplicationRecord.id == id).first()
    if not app_record:
        raise HTTPException(status_code=404, detail="Application record not found")
        
    schedule = list(app_record.interview_schedule or [])
    item = {
        "id": f"int_{len(schedule) + 1}_{int(datetime.utcnow().timestamp())}",
        "round_name": req.round_name,
        "date": req.date.isoformat(),
        "format": req.format or "virtual_video",
        "interviewer": req.interviewer,
        "meeting_link": req.meeting_link,
        "notes": req.notes,
        "created_at": datetime.utcnow().isoformat()
    }
    schedule.append(item)
    app_record.interview_schedule = schedule
    flag_modified(app_record, "interview_schedule")
    
    old_status = app_record.status
    app_record.status = "interviewing"
    
    # Set follow-up for 1 day after the scheduled interview
    app_record.follow_up_date = req.date + timedelta(days=1)
    app_record.updated_at = datetime.utcnow()
    
    trans = ApplicationStageTransition(
        application_id=app_record.id,
        from_stage=old_status,
        to_stage="interviewing",
        transitioned_at=datetime.utcnow(),
        notes=f"Scheduled {req.round_name} for {req.date.strftime('%Y-%m-%d %H:%M')}"
    )
    db.add(trans)
    db.commit()
    db.refresh(app_record)
    
    return {
        "message": "Interview scheduled successfully",
        "interview": item,
        "application": serialize_app(app_record)
    }
