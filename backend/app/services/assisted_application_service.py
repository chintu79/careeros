from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.app.models.opportunity import Opportunity
from backend.app.models.candidate import CandidateProfile
from backend.app.models.application import ApplicationRecord
from backend.app.models.application_transition import ApplicationStageTransition
from backend.app.models.resume import ResumeDocument

def prepare_assisted_application(db: Session, opportunity_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Gathers and packages candidate profile materials, tailored resume options,
    and verified answers for an opportunity without automated submission.
    """
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise ValueError(f"Opportunity {opportunity_id} not found")
    if user_id is not None and opp.user_id is not None and opp.user_id != user_id:
        raise PermissionError(f"Opportunity {opportunity_id} is private and not accessible for user #{user_id}")
        
    cand_query = db.query(CandidateProfile)
    if user_id is not None:
        cand = cand_query.filter(CandidateProfile.user_id == user_id).first()
    else:
        cand = cand_query.order_by(CandidateProfile.id.asc()).first()
    if not cand:
        raise ValueError("Candidate profile not found")
        
    # Check for existing tailored resume for this opportunity scoped to user
    tailored_query = db.query(ResumeDocument).filter(
        ResumeDocument.target_opportunity_id == opp.id
    )
    if user_id is not None:
        tailored_query = tailored_query.filter(ResumeDocument.user_id == user_id)
    tailored_resume = tailored_query.order_by(ResumeDocument.version.desc()).first()
    
    # Or fallback to master scoped to user
    master_query = db.query(ResumeDocument).filter(ResumeDocument.is_master == True)
    if user_id is not None:
        master_query = master_query.filter(ResumeDocument.user_id == user_id)
    master_resume = master_query.first()
    
    active_resume = tailored_resume or master_resume
    
    # Pre-filled applicant information
    applicant_info = {
        "full_name": cand.name,
        "email": cand.email,
        "phone": cand.phone,
        "location": cand.location,
        "college": cand.college,
        "degree": cand.degree,
        "graduation_year": cand.graduation_year,
        "cgpa": cand.cgpa,
        "work_authorization": cand.work_authorization,
        "github_url": cand.github_url,
        "linkedin_url": cand.linkedin_url,
        "portfolio_url": cand.portfolio_url
    }
    
    # Extract matching skills & projects for cover letter / questions
    extracted = opp.extracted_data or {}
    job_skills = set([s.lower() for s in extracted.get("mandatory_technical_skills", []) + extracted.get("preferred_skills", [])])
    
    matching_skills = [s.get("name") for s in (cand.skills or []) if s.get("name", "").lower() in job_skills]
    if not matching_skills and cand.skills:
        matching_skills = [s.get("name") for s in cand.skills[:3]]
        
    top_project = cand.projects[0] if cand.projects else None
    
    # Factual Cover Letter Draft based on real profile data
    cover_letter = f"""Dear Hiring Team at {opp.company_name},

I am writing to express my strong interest in the {opp.title} opportunity. As a {cand.degree} student at {cand.college} (graduating in {cand.graduation_year}), my technical background closely aligns with the requirements of this role.

Through my hands-on development work, I have built practical experience in {', '.join(matching_skills) if matching_skills else 'software engineering'}. In particular, through my project '{top_project.get('title') if top_project else 'software projects'}', I {top_project.get('description') if top_project else 'implemented end-to-end features'}.

I am excited about the opportunity to contribute to {opp.company_name} and welcome the chance to discuss my qualifications in greater detail.

Sincerely,
{cand.name}
{cand.email} | {cand.phone}
"""

    return {
        "opportunity_id": opp.id,
        "job_title": opp.title,
        "company_name": opp.company_name,
        "original_url": opp.original_url,
        "application_url": opp.application_url or opp.original_url,
        "applicant_info": applicant_info,
        "has_tailored_resume": tailored_resume is not None,
        "selected_resume": {
            "id": active_resume.id if active_resume else None,
            "title": active_resume.title if active_resume else "No Resume Selected",
            "pdf_url": f"/api/resumes/{active_resume.id}/pdf" if active_resume else None
        } if active_resume else None,
        "draft_cover_letter": cover_letter,
        "standard_questions": [
            {"question": "Are you legally authorized to work in India / target location?", "answer": cand.work_authorization},
            {"question": "What is your earliest available start date?", "answer": "Immediate / Within 2 weeks"},
            {"question": "Expected Graduation Year?", "answer": str(cand.graduation_year)}
        ],
        "submission_modes": [
            {
                "mode": "assisted",
                "label": "Mode A: Assisted Application (Recommended)",
                "description": "Copy tailored materials, open official portal, and review before submitting."
            },
            {
                "mode": "authorized_auto",
                "label": "Mode B: Authorized Auto-Apply (If Supported)",
                "description": "Requires direct verified API integration. Never bypasses anti-bot or CAPTCHA."
            }
        ]
    }

def record_application_submission(
    db: Session,
    opportunity_id: int,
    submission_mode: str = "assisted",
    resume_id: Optional[int] = None,
    notes: Optional[str] = "",
    submission_verified: bool = False
) -> ApplicationRecord:
    """Updates application record, creates stage transition, and schedules follow-up reminder."""
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise ValueError("Opportunity not found")
        
    app_record = db.query(ApplicationRecord).filter(ApplicationRecord.opportunity_id == opportunity_id).first()
    old_stage = app_record.status if app_record else "discovered"
    
    if not app_record:
        app_record = ApplicationRecord(
            opportunity_id=opp.id,
            company_name=opp.company_name,
            job_title=opp.title,
            original_url=opp.original_url,
            status="applied",
            match_score=opp.match_score,
            applied_date=datetime.utcnow(),
            resume_id=resume_id,
            submission_mode=submission_mode,
            submission_url=opp.application_url or opp.original_url,
            submission_verified=submission_verified,
            follow_up_date=datetime.utcnow() + timedelta(days=7),
            user_notes=notes or ""
        )
        db.add(app_record)
        db.flush()
    else:
        app_record.status = "applied"
        app_record.applied_date = datetime.utcnow()
        if resume_id:
            app_record.resume_id = resume_id
        app_record.submission_mode = submission_mode
        app_record.submission_verified = submission_verified
        app_record.follow_up_date = datetime.utcnow() + timedelta(days=7)
        if notes:
            app_record.user_notes = (app_record.user_notes or "") + "\n" + notes
            
    # Record stage transition for real Sankey diagram tracking
    trans = ApplicationStageTransition(
        application_id=app_record.id,
        from_stage=old_stage,
        to_stage="applied",
        transitioned_at=datetime.utcnow(),
        notes=f"Submitted via {submission_mode}. Verified: {submission_verified}"
    )
    db.add(trans)
    
    # Update opportunity
    opp.is_applied = True
    
    db.commit()
    db.refresh(app_record)
    return app_record
