from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.models.application import ApplicationRecord
from backend.app.models.opportunity import Opportunity
from backend.app.models.candidate import CandidateProfile
from backend.app.models.recruiter import RecruiterContact

def get_follow_up_intelligence(
    db: Session,
    stale_days_threshold: int = 7
) -> Dict[str, Any]:
    """
    Identifies high-priority application attention items:
      - Applications with no response after a configurable period
      - Applications where follow_up_date has arrived or passed
      - Applications with scheduled upcoming interviews
      - Applications with approaching portal deadlines
    """
    now = datetime.utcnow()
    stale_cutoff = now - timedelta(days=stale_days_threshold)
    
    apps: List[ApplicationRecord] = db.query(ApplicationRecord).all()
    
    no_response_items = []
    follow_up_due_items = []
    upcoming_interviews = []
    approaching_deadlines = []
    
    for a in apps:
        opp = db.query(Opportunity).filter(Opportunity.id == a.opportunity_id).first() if a.opportunity_id else None
        company = a.company_name or (opp.company_name if opp else "Target Company")
        title = a.job_title or (opp.title if opp else "Role")
        
        # 1. No response after configurable threshold
        if (a.status or "").lower() == "applied" and a.applied_date:
            days_elapsed = (now - a.applied_date).days
            if days_elapsed >= stale_days_threshold:
                no_response_items.append({
                    "application_id": a.id,
                    "company_name": company,
                    "job_title": title,
                    "applied_date": a.applied_date.isoformat(),
                    "days_elapsed": days_elapsed,
                    "recruiter_name": a.recruiter_name,
                    "recruiter_email": a.recruiter_email,
                    "recommendation": f"Application submitted {days_elapsed} days ago with no response. A professional follow-up is recommended."
                })

        # 2. Follow-up reminder date arrived
        if a.follow_up_date and a.follow_up_date <= now and (a.status or "").lower() not in ["offered", "rejected", "withdrawn"]:
            follow_up_due_items.append({
                "application_id": a.id,
                "company_name": company,
                "job_title": title,
                "status": a.status,
                "follow_up_date": a.follow_up_date.isoformat(),
                "recruiter_name": a.recruiter_name,
                "recruiter_email": a.recruiter_email,
                "recommendation": "Scheduled follow-up reminder is due today."
            })

        # 3. Upcoming interviews in interview_schedule
        schedule = a.interview_schedule or []
        for round_item in schedule:
            r_date_str = round_item.get("date")
            if r_date_str:
                try:
                    r_date = datetime.fromisoformat(r_date_str.replace("Z", ""))
                    diff_days = (r_date - now).total_seconds() / 86400.0
                    if 0 <= diff_days <= 7:
                        upcoming_interviews.append({
                            "application_id": a.id,
                            "company_name": company,
                            "job_title": title,
                            "round_name": round_item.get("round_name", "Interview Round"),
                            "date": r_date.isoformat(),
                            "format": round_item.get("format", "virtual_video"),
                            "interviewer": round_item.get("interviewer"),
                            "meeting_link": round_item.get("meeting_link"),
                            "days_until": round(diff_days, 1)
                        })
                except Exception:
                    pass

        # 4. Approaching portal deadlines
        opp_deadline = getattr(opp, "deadline_at", None) if opp else None
        if opp_deadline:
            days_to_deadline = (opp_deadline - now).total_seconds() / 86400.0
            if 0 < days_to_deadline <= 7 and (a.status or "").lower() == "ready_to_apply":
                approaching_deadlines.append({
                    "application_id": a.id,
                    "opportunity_id": opp.id,
                    "company_name": company,
                    "job_title": title,
                    "deadline": opp_deadline.isoformat(),
                    "days_remaining": round(days_to_deadline, 1),
                    "original_url": opp.source_url or a.original_url
                })

    no_response_items.sort(key=lambda x: x["days_elapsed"], reverse=True)
    follow_up_due_items.sort(key=lambda x: x["follow_up_date"])
    upcoming_interviews.sort(key=lambda x: x["days_until"])
    approaching_deadlines.sort(key=lambda x: x["days_remaining"])

    return {
        "stale_days_threshold": stale_days_threshold,
        "summary": {
            "unanswered_count": len(no_response_items),
            "follow_up_due_count": len(follow_up_due_items),
            "upcoming_interviews_count": len(upcoming_interviews),
            "approaching_deadlines_count": len(approaching_deadlines)
        },
        "unanswered_applications": no_response_items,
        "follow_ups_due": follow_up_due_items,
        "upcoming_interviews": upcoming_interviews,
        "approaching_deadlines": approaching_deadlines,
        "generated_at": now.isoformat()
    }


def generate_follow_up_email_draft(
    application: ApplicationRecord,
    profile: Optional[CandidateProfile],
    tone: str = "inquisitive",
    custom_note: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generates a personalized, professional email draft tailored to candidate profile and target company.
    Requires explicit user approval before sending.
    """
    cand_name = getattr(profile, "name", None) or "Candidate"
    cand_email = getattr(profile, "email", None) or "candidate@university.edu"
    cand_phone = getattr(profile, "phone", None) or ""
    cand_uni = getattr(profile, "college", None) or "University"
    
    # Pick candidate top project
    cand_projects = getattr(profile, "projects", []) or []
    cand_proj = cand_projects[0] if cand_projects else None
    proj_mention = f"Recently, I completed {cand_proj.get('title', 'a full-stack project')} utilizing {', '.join(cand_proj.get('tech_stack', ['modern web technologies'])[:3])}." if cand_proj else ""

    company = application.company_name or "the hiring team"
    role = application.job_title or "Software Engineering Intern"
    applied_str = application.applied_date.strftime("%B %d, %Y") if application.applied_date else "recently"
    recruiter_name = application.recruiter_name or "Hiring Team"

    if tone == "post_interview":
        subject = f"Thank You - {role} Interview Follow-up - {cand_name}"
        body = f"""Dear {recruiter_name},

Thank you very much for taking the time to speak with me regarding the {role} position at {company}. I really enjoyed our conversation and learning more about the engineering challenges your team is currently solving.

Our discussion reinforced my enthusiasm for joining {company}. {proj_mention} I am confident my technical foundations will allow me to contribute meaningfully from day one.

Please let me know if there are any additional materials, code samples, or references I can provide. I look forward to hearing about the next steps.

Best regards,

{cand_name}
{cand_uni}
{cand_email} | {cand_phone}
"""
    elif tone == "portfolio_update":
        subject = f"Project Update & Application Check-in: {role} - {cand_name}"
        body = f"""Dear {recruiter_name},

I hope this email finds you well.

I submitted my application for the {role} position at {company} on {applied_str}. I am writing to reiterate my strong interest in joining your team and to share a brief update.

{proj_mention} I believe the architectural patterns and technologies I exercised here directly align with {company}'s tech stack.

I would welcome the opportunity to discuss how my skill set aligns with your team's goals this upcoming term. Thank you for your time and consideration.

Warm regards,

{cand_name}
{cand_uni}
{cand_email} | {cand_phone}
"""
    else: # default: "inquisitive" (polite follow-up after no response)
        subject = f"Inquiry Regarding Application: {role} - {cand_name}"
        body = f"""Dear {recruiter_name},

I hope you are having a productive week.

I applied for the {role} opening at {company} on {applied_str}. Given my background at {cand_uni} and my experience building backend systems, I remain very excited about the opportunity to contribute to {company}.

{proj_mention}

I understand your team is busy reviewing applications, but I wanted to respectfully check in on the status of my application and see if there are any further details I can provide.

Thank you very much for your time and guidance.

Sincerely,

{cand_name}
{cand_uni}
{cand_email} | {cand_phone}
"""

    return {
        "application_id": application.id,
        "company_name": company,
        "job_title": role,
        "recipient_name": recruiter_name,
        "recipient_email": application.recruiter_email or "recruiter@" + company.lower().replace(" ", "") + ".com",
        "subject": subject,
        "body": body.strip(),
        "tone": tone,
        "requires_user_approval": True,
        "generated_at": datetime.utcnow().isoformat()
    }
