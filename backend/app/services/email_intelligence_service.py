import re
import html
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.app.models.integration import EmailMessageRecord, IntegrationConnection
from backend.app.models.application import ApplicationRecord
from backend.app.models.opportunity import Opportunity
from backend.app.models.recruiter import RecruiterContact
from backend.app.services.notification_service import create_notification

logger = logging.getLogger(__name__)

# Core Career Categories
CATEGORY_APPLICATION_CONFIRMATION = "application_confirmation"
CATEGORY_RECRUITER_OUTREACH = "recruiter_outreach"
CATEGORY_INTERVIEW_INVITATION = "interview_invitation"
CATEGORY_INTERVIEW_RESCHEDULED = "interview_rescheduled"
CATEGORY_ASSESSMENT_TEST = "assessment_test"
CATEGORY_REJECTION = "rejection"
CATEGORY_SHORTLISTING_SCREENING = "shortlisting_screening"
CATEGORY_OFFER_LETTER = "offer_letter"
CATEGORY_FOLLOW_UP = "follow_up"
CATEGORY_OTHER_CAREER = "other_career"

ALL_CATEGORIES = [
    CATEGORY_APPLICATION_CONFIRMATION,
    CATEGORY_RECRUITER_OUTREACH,
    CATEGORY_INTERVIEW_INVITATION,
    CATEGORY_INTERVIEW_RESCHEDULED,
    CATEGORY_ASSESSMENT_TEST,
    CATEGORY_REJECTION,
    CATEGORY_SHORTLISTING_SCREENING,
    CATEGORY_OFFER_LETTER,
    CATEGORY_FOLLOW_UP,
    CATEGORY_OTHER_CAREER,
]

# Map categories to suggested application status transitions
SUGGESTED_STAGE_MAP = {
    CATEGORY_APPLICATION_CONFIRMATION: "applied",
    CATEGORY_INTERVIEW_INVITATION: "technical_interview",
    CATEGORY_INTERVIEW_RESCHEDULED: "technical_interview",
    CATEGORY_ASSESSMENT_TEST: "screening",
    CATEGORY_SHORTLISTING_SCREENING: "screening",
    CATEGORY_OFFER_LETTER: "offered",
    CATEGORY_REJECTION: "rejected",
    CATEGORY_RECRUITER_OUTREACH: None, # Recruiter outreach does not presuppose an applied status
    CATEGORY_FOLLOW_UP: None,
    CATEGORY_OTHER_CAREER: None
}

def sanitize_email_text(text: str) -> str:
    """
    Sanitizes untrusted email plain text:
    - Strips scripts and dangerous tags
    - Preserves href link targets by expanding <a href="url">text</a>
    - Limits size to prevent memory attacks
    """
    if not text:
        return ""
    clean = re.sub(r"<script.*?>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<style.*?>.*?</style>", "", clean, flags=re.DOTALL | re.IGNORECASE)
    # Convert <a href="url">text</a> to text (url)
    clean = re.sub(r'<a\s+(?:[^>]*?\s+)?href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', r'\2 (\1)', clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = html.unescape(clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:10000]

def extract_meeting_links(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Extracts video meeting link and platform from text."""
    if not text:
        return None, None
        
    meet_match = re.search(r"https?://meet\.google\.com/[a-zA-Z0-9?&=_-]+", text)
    if meet_match:
        return meet_match.group(0), "Google Meet"
        
    zoom_match = re.search(r"https?://[a-zA-Z0-9-]+\.zoom\.us/[a-zA-Z0-9?&=_/-]+", text)
    if zoom_match:
        return zoom_match.group(0), "Zoom"
        
    teams_match = re.search(r"https?://teams\.microsoft\.com/[a-zA-Z0-9%?&=_/-]+", text)
    if teams_match:
        return teams_match.group(0), "Microsoft Teams"
        
    return None, None

def classify_career_email(subject: str, body: str, sender: str = "") -> Tuple[str, float]:
    """
    Classifies career communication into one of 10 structured categories with confidence score.
    Returns (category, confidence_score).
    """
    text = f"{subject} {body}".lower()
    
    # 1. Offer Letter (Highest precedence)
    if any(k in text for k in ["offer letter", "pleased to offer you", "congratulations on your offer", "formal offer", "job offer", "internship offer"]):
        return CATEGORY_OFFER_LETTER, 0.96

    # 2. Rejection
    if any(k in text for k in [
        "not moving forward", "decided to move forward with other", "unfortunately, we will not",
        "pursuing other candidates", "regret to inform you", "not selected", "won't be moving forward",
        "position has been filled", "unable to offer you", "wishing you the best in your search"
    ]):
        return CATEGORY_REJECTION, 0.94

    # 3. Interview Rescheduled
    if any(k in text for k in ["interview rescheduled", "rescheduling your interview", "new interview time", "updated meeting invitation", "time change for your"]):
        return CATEGORY_INTERVIEW_RESCHEDULED, 0.92

    # 4. Interview Invitation
    if any(k in text for k in [
        "interview invitation", "invite you to interview", "schedule an interview", "schedule your next round",
        "technical interview", "coding interview", "behavioral interview", "virtual interview",
        "phone screen interview", "availability for a call", "speak with our team", "select a time for your"
    ]):
        return CATEGORY_INTERVIEW_INVITATION, 0.95

    # 5. Assessment or Coding Test
    if any(k in text for k in [
        "hackerrank", "codesignal", "codility", "online assessment", "coding challenge", "take-home test",
        "complete your assessment", "assessment deadline", "technical assessment", "screening test"
    ]):
        return CATEGORY_ASSESSMENT_TEST, 0.94

    # 6. Shortlisting / Screening
    if any(k in text for k in ["shortlisted for", "selected for the next step", "passed the initial screening", "initial phone screen", "quick screening call"]):
        return CATEGORY_SHORTLISTING_SCREENING, 0.88

    # 7. Application Confirmation
    if any(k in text for k in [
        "thank you for applying", "application received", "we received your application",
        "confirming your application", "application submitted successfully", "thanks for your interest in"
    ]):
        return CATEGORY_APPLICATION_CONFIRMATION, 0.96

    # 8. Recruiter Outreach
    if any(k in text for k in [
        "came across your profile", "impressed by your background", "opportunity at",
        "reaching out regarding", "found your github", "found your linkedin", "would love to connect about a role"
    ]):
        return CATEGORY_RECRUITER_OUTREACH, 0.86

    # 9. Follow-up
    if any(k in text for k in ["following up on", "checking in on", "update on your status", "status update for your"]):
        return CATEGORY_FOLLOW_UP, 0.82

    # 10. Other career
    if any(k in text for k in ["career", "internship", "hiring", "recruitment", "position", "applicant"]):
        return CATEGORY_OTHER_CAREER, 0.65

    return CATEGORY_OTHER_CAREER, 0.40

def extract_structured_email_data(subject: str, body: str, sender: str, category: str) -> Dict[str, Any]:
    """
    Extracts structured entities: company, role, interview dates, deadline, meeting links.
    Zero fabrication: fields default to null if not grounded in text.
    """
    clean_body = sanitize_email_text(body)
    full_text = f"{subject} {clean_body}"
    
    # 1. Company Name Extraction
    company = None
    # Check domain in sender (e.g., recruiter@stripe.com -> Stripe)
    domain_match = re.search(r"@([a-zA-Z0-9-]+)\.(com|io|co|in|org|net|ai)", sender)
    if domain_match:
        candidate_domain = domain_match.group(1).capitalize()
        if candidate_domain.lower() not in ["gmail", "outlook", "yahoo", "hotmail", "icloud", "mail", "recruiting", "greenhouse", "lever", "ashbyhq", "smartrecruiters"]:
            company = candidate_domain

    if not company:
        # Look for "at <Company>" or "<Company> Careers"
        at_match = re.search(r"\bat\s+([A-Z][a-zA-Z0-9&.-]+(?:\s+[A-Z][a-zA-Z0-9&.-]+)?)", subject)
        if at_match:
            company = at_match.group(1).strip()
        else:
            with_match = re.search(r"\bwith\s+([A-Z][a-zA-Z0-9&.-]+(?:\s+[A-Z][a-zA-Z0-9&.-]+)?)", subject)
            if with_match:
                company = with_match.group(1).strip()

    # 2. Role Title Extraction
    role = None
    role_match = re.search(r"((?:Software|Backend|Frontend|Full[- ]Stack|Machine Learning|AI|Data Science|Systems|Security|DevOps)\s+(?:Engineering\s+)?(?:Intern(?:ship)?|Fellow|Co-op|Developer|Engineer))", full_text, re.IGNORECASE)
    if role_match:
        role = role_match.group(1).title()

    # 3. Meeting Link & Platform
    meeting_link, platform = extract_meeting_links(full_text)

    # 4. Dates & Deadlines
    extracted_deadline = None
    deadline_match = re.search(r"\b(?:by|before|deadline:?)\s+([A-Z][a-z]{2,8}\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?)", full_text)
    if deadline_match:
        extracted_deadline = deadline_match.group(1)

    # 5. Action Required
    action_required = None
    if category == CATEGORY_ASSESSMENT_TEST:
        action_required = f"Complete online assessment {f'by {extracted_deadline}' if extracted_deadline else 'before expiration'}"
    elif category == CATEGORY_INTERVIEW_INVITATION:
        action_required = "Schedule interview time slot or confirm attendance"
    elif category == CATEGORY_OFFER_LETTER:
        action_required = "Review offer details and response deadline"
    elif category == CATEGORY_SHORTLISTING_SCREENING:
        action_required = "Prepare for initial screening call"

    return {
        "company_name": company,
        "role_title": role,
        "meeting_platform": platform,
        "meeting_link": meeting_link,
        "deadline_text": extracted_deadline,
        "action_required": action_required,
        "is_low_confidence": False
    }

def find_matching_application(db: Session, company_name: Optional[str], role_title: Optional[str]) -> Tuple[Optional[ApplicationRecord], float]:
    """
    Connects detected email to existing ApplicationRecord.
    Returns (matched_application, match_confidence).
    """
    if not company_name:
        return None, 0.0

    c_clean = company_name.strip().lower()
    apps = db.query(ApplicationRecord).all()
    
    best_match = None
    best_score = 0.0
    
    for app in apps:
        app_company = (app.company_name or "").strip().lower()
        if not app_company:
            continue
            
        score = 0.0
        # Exact company match
        if c_clean == app_company or c_clean in app_company or app_company in c_clean:
            score += 0.70
            
            # Role matching bonus
            if role_title and app.job_title:
                r_clean = role_title.strip().lower()
                aj_clean = app.job_title.strip().lower()
                if r_clean == aj_clean:
                    score += 0.30
                elif any(word in aj_clean for word in r_clean.split() if len(word) > 3):
                    score += 0.20
            else:
                score += 0.15 # Single active application at company
                
        if score > best_score:
            best_score = score
            best_match = app

    if best_score >= 0.70:
        return best_match, min(best_score, 1.0)
    return None, 0.0

def process_incoming_email(
    db: Session,
    raw_message: Dict[str, Any],
    connection_id: Optional[int] = None
) -> EmailMessageRecord:
    """
    Processes an incoming raw email:
    - Checks for duplicate message ID (idempotency)
    - Classifies career category
    - Extracts structured entities
    - Associates with existing ApplicationRecord
    - Creates EmailMessageRecord
    - Generates in-app notification if actionable
    """
    provider_msg_id = raw_message.get("provider_message_id", "")
    existing = db.query(EmailMessageRecord).filter(EmailMessageRecord.provider_message_id == provider_msg_id).first()
    if existing:
        return existing

    subject = raw_message.get("subject", "")
    body = raw_message.get("body_plain", "") or raw_message.get("snippet", "")
    sender = raw_message.get("sender", "")
    
    # 1. Classify
    category, conf = classify_career_email(subject, body, sender)
    
    # 2. Extract
    extracted = extract_structured_email_data(subject, body, sender, category)
    if conf < 0.85:
        extracted["is_low_confidence"] = True

    # 3. Match with Application
    app, match_conf = find_matching_application(db, extracted.get("company_name"), extracted.get("role_title"))
    suggested_stage = SUGGESTED_STAGE_MAP.get(category)

    # Clean sender email & name
    sender_email = sender
    sender_name = sender
    email_match = re.search(r"<([^>]+)>", sender)
    if email_match:
        sender_email = email_match.group(1).strip()
        sender_name = sender.split("<")[0].strip().strip('"')

    record = EmailMessageRecord(
        connection_id=connection_id,
        application_id=app.id if app else None,
        provider_message_id=provider_msg_id,
        thread_id=raw_message.get("thread_id"),
        sender=sender,
        sender_email=sender_email,
        sender_name=sender_name or sender_email,
        recipient=raw_message.get("recipient", ""),
        subject=subject,
        snippet=raw_message.get("snippet", "")[:500],
        body_plain=sanitize_email_text(body)[:4000],
        received_at=raw_message.get("received_at", datetime.utcnow()),
        detected_category=category,
        confidence_score=conf,
        extracted_data=extracted,
        suggested_stage=suggested_stage,
        review_status="pending_review"
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # 4. Generate notification for actionable high-priority career messages
    if category in [CATEGORY_INTERVIEW_INVITATION, CATEGORY_OFFER_LETTER, CATEGORY_ASSESSMENT_TEST]:
        notif_title = f"{category.replace('_', ' ').title()}: {extracted.get('company_name') or 'Employer'}"
        notif_msg = f"{subject} — {extracted.get('action_required') or 'Review message in Email Intelligence'}"
        create_notification(
            db=db,
            title=notif_title,
            message=notif_msg,
            notification_type="deadline_warning" if category == CATEGORY_ASSESSMENT_TEST else "high_match",
            opportunity_id=app.opportunity_id if app else None
        )

    return record
