from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException
from backend.app.models.opportunity import Opportunity
from backend.app.models.application import ApplicationRecord
from backend.app.models.candidate import CandidateProfile
from backend.app.services.notification_service import create_notification

def handoff_to_application_tracker(
    db: Session,
    opportunity_id: int,
    initial_status: str = "ready_to_apply",
    user_notes: str = "",
    recruiter_name: Optional[str] = None,
    recruiter_email: Optional[str] = None,
    recruiter_linkedin: Optional[str] = None
) -> ApplicationRecord:
    """
    Section 9: Automatic Application Handoff
    Moves an opportunity to the application tracker:
    - Verifies opportunity
    - Checks for existing application to avoid duplicates
    - Synthesizes tailored resume bullet points and cover letter strategies
    - Flags opportunity as is_applied = True
    """
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
        
    existing_app = db.query(ApplicationRecord).filter(
        ApplicationRecord.opportunity_id == opportunity_id
    ).first()
    if existing_app:
        return existing_app

    candidate = db.query(CandidateProfile).first()
    
    # Generate tailored resume summary and bullet points based on match analysis
    match_data = opp.match_analysis or {}
    strong_skills = [m.get("skill") for m in match_data.get("skill_compatibility", {}).get("strong", [])]
    matched_projects = match_data.get("relevant_projects", [])
    
    proj_names = [p.get("title") for p in matched_projects] or ["CareerOS", "Argus AI"]
    tailored_resume = (
        f"Tailored Resume Angle for {opp.company_name} ({opp.normalized_title}):\n"
        f"• Highlight hands-on experience in: {', '.join(strong_skills[:4]) or 'Python, REST APIs, Git'}\n"
        f"• Lead portfolio section with: '{proj_names[0]}'\n"
        f"• Showcase production-ready code quality and active problem solving."
    )
    
    cover_letter_points = [
        f"Express genuine interest in {opp.company_name}'s technical mission.",
        f"Mention direct relevance of verified project '{proj_names[0]}' to the {opp.title} requirements.",
        f"Emphasize strong technical match in {', '.join(strong_skills[:3])}."
    ]

    app_record = ApplicationRecord(
        opportunity_id=opp.id,
        company_name=opp.company_name,
        job_title=opp.title,
        original_url=opp.original_url,
        status=initial_status,
        applied_date=datetime.utcnow() if initial_status == "applied" else None,
        match_score=opp.match_score,
        tailored_resume_summary=tailored_resume,
        cover_letter_points=cover_letter_points,
        recruiter_name=recruiter_name,
        recruiter_email=recruiter_email,
        recruiter_linkedin=recruiter_linkedin,
        user_notes=user_notes
    )
    
    opp.is_applied = True
    db.add(app_record)
    db.commit()
    db.refresh(app_record)
    
    create_notification(
        db,
        title=f"Application Created: {opp.company_name}",
        message=f"{opp.title} handed off to Application Tracker with status '{initial_status}'.",
        notification_type="high_match",
        opportunity_id=opp.id
    )
    
    return app_record
