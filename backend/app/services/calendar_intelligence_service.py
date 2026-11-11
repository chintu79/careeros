import re
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.app.models.integration import CalendarEventRecord
from backend.app.models.application import ApplicationRecord
from backend.app.services.email_intelligence_service import find_matching_application, extract_meeting_links

logger = logging.getLogger(__name__)

EVENT_TYPE_TECHNICAL_INTERVIEW = "technical_interview"
EVENT_TYPE_HR_INTERVIEW = "hr_interview"
EVENT_TYPE_RECRUITER_CALL = "recruiter_call"
EVENT_TYPE_ONLINE_ASSESSMENT = "online_assessment"
EVENT_TYPE_DEADLINE = "deadline"
EVENT_TYPE_FOLLOW_UP_REMINDER = "follow_up_reminder"
EVENT_TYPE_CAREER_MEETING = "career_meeting"

def classify_calendar_event(title: str, description: str = "") -> Tuple[str, Optional[str], Optional[str]]:
    """
    Classifies a calendar event into a career event type, and attempts to extract company and role.
    Returns (event_type, company_name, role_title).
    """
    text = f"{title} {description}".lower()

    event_type = EVENT_TYPE_CAREER_MEETING
    if any(k in text for k in ["technical interview", "coding interview", "system design", "pair programming", "live coding"]):
        event_type = EVENT_TYPE_TECHNICAL_INTERVIEW
    elif any(k in text for k in ["hr interview", "behavioral interview", "culture fit", "hiring manager"]):
        event_type = EVENT_TYPE_HR_INTERVIEW
    elif any(k in text for k in ["recruiter screen", "recruiter call", "phone screen", "introductory chat", "recruiter chat"]):
        event_type = EVENT_TYPE_RECRUITER_CALL
    elif any(k in text for k in ["assessment", "hackerrank", "codesignal", "take-home"]):
        event_type = EVENT_TYPE_ONLINE_ASSESSMENT
    elif any(k in text for k in ["deadline", "portal close", "submission due"]):
        event_type = EVENT_TYPE_DEADLINE
    elif any(k in text for k in ["follow up", "follow-up", "check-in"]):
        event_type = EVENT_TYPE_FOLLOW_UP_REMINDER

    # Extract company (e.g. "Interview with Stripe", "Palantir Technical Screen", "Google / Alex")
    company = None
    with_match = re.search(r"\b(?:with|at|@|/)\s+([A-Z][a-zA-Z0-9&.-]+)", title)
    if with_match:
        company = with_match.group(1).strip()
    else:
        # Check first word if capitalized company name like "Stripe: Technical Interview"
        prefix_match = re.search(r"^([A-Z][a-zA-Z0-9&.-]+)\s*[:|-]", title)
        if prefix_match:
            company = prefix_match.group(1).strip()

    # Extract role if present
    role = None
    role_match = re.search(r"((?:Software|Backend|Frontend|Full[- ]Stack|AI|ML|Data)\s+(?:Engineer(?:ing)?|Intern(?:ship)?))", text, re.IGNORECASE)
    if role_match:
        role = role_match.group(1).title()

    return event_type, company, role

def process_calendar_event(
    db: Session,
    raw_event: Dict[str, Any],
    connection_id: Optional[int] = None
) -> CalendarEventRecord:
    """
    Ingests or updates a calendar event:
    - Avoids duplicate records by provider_event_id
    - Classifies career event type
    - Connects to existing ApplicationRecord
    - Preserves time zone and video conference meeting links
    """
    provider_event_id = raw_event.get("provider_event_id", "")
    existing = db.query(CalendarEventRecord).filter(CalendarEventRecord.provider_event_id == provider_event_id).first()

    title = raw_event.get("title", "Career Event")
    desc = raw_event.get("description", "")
    event_type, extracted_company, extracted_role = classify_calendar_event(title, desc)

    company_name = raw_event.get("company_name") or extracted_company
    role_title = raw_event.get("role_title") or extracted_role

    # Meeting link check
    meeting_link = raw_event.get("meeting_link")
    meeting_platform = raw_event.get("meeting_platform")
    if not meeting_link and desc:
        detected_link, detected_plat = extract_meeting_links(desc)
        if detected_link:
            meeting_link = detected_link
            meeting_platform = detected_plat

    # Connect to application
    app, _ = find_matching_application(db, company_name, role_title)

    if existing:
        existing.title = title
        existing.description = desc
        existing.start_time = raw_event.get("start_time", existing.start_time)
        existing.end_time = raw_event.get("end_time", existing.end_time)
        existing.time_zone = raw_event.get("time_zone", existing.time_zone)
        existing.event_type = event_type
        existing.meeting_platform = meeting_platform or existing.meeting_platform
        existing.meeting_link = meeting_link or existing.meeting_link
        existing.location = raw_event.get("location") or existing.location
        if app and not existing.application_id:
            existing.application_id = app.id
        db.commit()
        db.refresh(existing)
        return existing

    record = CalendarEventRecord(
        connection_id=connection_id,
        application_id=app.id if app else None,
        provider_event_id=provider_event_id,
        title=title,
        description=desc,
        start_time=raw_event.get("start_time", datetime.utcnow()),
        end_time=raw_event.get("end_time"),
        time_zone=raw_event.get("time_zone", "UTC"),
        event_type=event_type,
        meeting_platform=meeting_platform,
        meeting_link=meeting_link,
        location=raw_event.get("location"),
        company_name=company_name,
        role_title=role_title,
        organizer=raw_event.get("organizer"),
        attendees=raw_event.get("attendees", []),
        prep_notes=raw_event.get("prep_notes"),
        status=raw_event.get("status", "confirmed")
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
