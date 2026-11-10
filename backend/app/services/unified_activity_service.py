import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.models.application import ApplicationRecord
from backend.app.models.application_transition import ApplicationStageTransition
from backend.app.models.integration import EmailMessageRecord, CalendarEventRecord, UnifiedActivityRecord
from backend.app.models.opportunity import Opportunity

logger = logging.getLogger(__name__)

def fetch_unified_activities(
    db: Session,
    limit: int = 100,
    filter_category: str = "all", # all, emails, interviews, deadlines, follow_ups, updates
    application_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Assembles a unified chronological timeline combining:
    1. Application stage transitions
    2. Synced career emails
    3. Calendar events & scheduled interviews
    4. Follow-up milestones
    5. Application deadlines
    """
    events = []

    # Cache for application details
    app_cache: Dict[int, ApplicationRecord] = {}
    def get_app(aid: int) -> Optional[ApplicationRecord]:
        if aid not in app_cache:
            app_cache[aid] = db.query(ApplicationRecord).filter(ApplicationRecord.id == aid).first()
        return app_cache[aid]

    # 1. Stage Transitions (Updates)
    if filter_category in ["all", "updates"]:
        q = db.query(ApplicationStageTransition)
        if application_id:
            q = q.filter(ApplicationStageTransition.application_id == application_id)
        transitions = q.order_by(desc(ApplicationStageTransition.transitioned_at)).limit(limit).all()

        for t in transitions:
            app = get_app(t.application_id)
            events.append({
                "id": f"trans_{t.id}",
                "source_type": "stage_transition",
                "event_category": "stage_change",
                "timestamp": t.transitioned_at.isoformat(),
                "title": f"Moved to {t.to_stage.replace('_', ' ').title()}",
                "description": f"Application stage updated from {t.from_stage.replace('_', ' ').title()} to {t.to_stage.replace('_', ' ').title()}",
                "company_name": app.company_name if app else "Company",
                "job_title": app.job_title if app else "Opportunity",
                "application_id": t.application_id,
                "notes": t.notes,
                "badge_color": "emerald"
            })

    # 2. Career Emails (Emails)
    if filter_category in ["all", "emails"]:
        q = db.query(EmailMessageRecord)
        if application_id:
            q = q.filter(EmailMessageRecord.application_id == application_id)
        emails = q.order_by(desc(EmailMessageRecord.received_at)).limit(limit).all()

        for em in emails:
            app = get_app(em.application_id) if em.application_id else None
            company = (em.extracted_data or {}).get("company_name") or (app.company_name if app else em.sender_name)
            role = (em.extracted_data or {}).get("role_title") or (app.job_title if app else "Career Role")
            
            badge_color = "blue"
            if em.detected_category == "interview_invitation":
                badge_color = "purple"
            elif em.detected_category == "offer_letter":
                badge_color = "emerald"
            elif em.detected_category == "rejection":
                badge_color = "rose"
            elif em.detected_category == "assessment_test":
                badge_color = "amber"

            events.append({
                "id": f"email_{em.id}",
                "source_type": "email",
                "event_category": em.detected_category,
                "timestamp": em.received_at.isoformat(),
                "title": f"Email: {em.subject}",
                "description": em.snippet or em.body_plain[:200] if em.body_plain else "",
                "company_name": company,
                "job_title": role,
                "application_id": em.application_id,
                "sender": em.sender,
                "confidence_score": em.confidence_score,
                "review_status": em.review_status,
                "suggested_stage": em.suggested_stage,
                "meeting_link": (em.extracted_data or {}).get("meeting_link"),
                "badge_color": badge_color
            })

    # 3. Calendar Events & Interviews (Interviews)
    if filter_category in ["all", "interviews"]:
        q = db.query(CalendarEventRecord)
        if application_id:
            q = q.filter(CalendarEventRecord.application_id == application_id)
        cal_events = q.order_by(desc(CalendarEventRecord.start_time)).limit(limit).all()

        for ce in cal_events:
            app = get_app(ce.application_id) if ce.application_id else None
            company = ce.company_name or (app.company_name if app else "Company")
            role = ce.role_title or (app.job_title if app else "Role")

            events.append({
                "id": f"cal_{ce.id}",
                "source_type": "calendar",
                "event_category": ce.event_type,
                "timestamp": ce.start_time.isoformat(),
                "title": ce.title,
                "description": ce.description or f"Scheduled on {ce.meeting_platform or 'Virtual Platform'}",
                "company_name": company,
                "job_title": role,
                "application_id": ce.application_id,
                "meeting_platform": ce.meeting_platform,
                "meeting_link": ce.meeting_link,
                "location": ce.location,
                "time_zone": ce.time_zone,
                "badge_color": "purple"
            })

        # Scheduled interviews from ApplicationRecord.interview_schedule
        app_q = db.query(ApplicationRecord).filter(ApplicationRecord.interview_schedule.isnot(None))
        if application_id:
            app_q = app_q.filter(ApplicationRecord.id == application_id)
        for a in app_q.all():
            for item in (a.interview_schedule or []):
                if item.get("date"):
                    events.append({
                        "id": f"int_sched_{item.get('id', item.get('date'))}",
                        "source_type": "interview_schedule",
                        "event_category": "interview_scheduled",
                        "timestamp": item.get("date"),
                        "title": f"Interview: {item.get('round_name', 'Interview Round')}",
                        "description": f"Format: {item.get('format', 'Virtual Video')}. Interviewer: {item.get('interviewer', 'Hiring Team')}",
                        "company_name": a.company_name,
                        "job_title": a.job_title,
                        "application_id": a.id,
                        "meeting_link": item.get("meeting_link"),
                        "notes": item.get("notes"),
                        "badge_color": "purple"
                    })

    # 4. Deadlines (Deadlines)
    if filter_category in ["all", "deadlines"]:
        opp_q = db.query(Opportunity).filter(Opportunity.deadline_at.isnot(None))
        for opp in opp_q.limit(30).all():
            app = db.query(ApplicationRecord).filter(ApplicationRecord.opportunity_id == opp.id).first()
            if application_id and (not app or app.id != application_id):
                continue
            events.append({
                "id": f"opp_dl_{opp.id}",
                "source_type": "deadline",
                "event_category": "assessment_deadline",
                "timestamp": opp.deadline_at.isoformat(),
                "title": f"Deadline: {opp.company_name}",
                "description": f"Application deadline for {opp.title}",
                "company_name": opp.company_name,
                "job_title": opp.title,
                "application_id": app.id if app else None,
                "badge_color": "amber"
            })

    # 5. Follow-ups (Follow-ups)
    if filter_category in ["all", "follow_ups"]:
        app_fu = db.query(ApplicationRecord).filter(ApplicationRecord.follow_up_date.isnot(None))
        if application_id:
            app_fu = app_fu.filter(ApplicationRecord.id == application_id)
        for a in app_fu.all():
            events.append({
                "id": f"app_fu_{a.id}",
                "source_type": "follow_up",
                "event_category": "follow_up_due",
                "timestamp": a.follow_up_date.isoformat(),
                "title": f"Follow-up Due: {a.company_name}",
                "description": f"Recommended follow-up regarding {a.job_title}",
                "company_name": a.company_name,
                "job_title": a.job_title,
                "application_id": a.id,
                "badge_color": "amber"
            })

    # Sort strictly descending by timestamp
    events.sort(key=lambda x: x["timestamp"], reverse=True)
    return events[:limit]
