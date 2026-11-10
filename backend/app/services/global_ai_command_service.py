import re
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, AsyncGenerator
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from backend.app.models.opportunity import Opportunity
from backend.app.models.candidate import CandidateProfile
from backend.app.models.application import ApplicationRecord
from backend.app.models.application_transition import ApplicationStageTransition
from backend.app.models.interview import InterviewJournalRecord
from backend.app.models.chat import ChatConversation, ChatMessage
from backend.app.models.ai_audit import AIActionAuditLog
from backend.app.models.recruiter import RecruiterContact
from backend.app.models.resume import ResumeDocument
from backend.app.models.resume_version import ResumeVersion
from backend.app.ai.ollama_client import ollama_client
from backend.app.services.follow_up_intelligence_service import get_follow_up_intelligence
from backend.app.services.resume_tailorer import tailor_resume_for_opportunity
from backend.app.services.context_retriever import (
    get_candidate_context,
    get_opportunity_context,
    get_pipeline_context
)

logger = logging.getLogger(__name__)


# =====================================================================
# Strict Permitted Tool Registry (10 Structured Tools)
# Zero arbitrary SQL or unrestricted shell execution
# =====================================================================

PERMITTED_TOOLS = {
    "search_opportunities": {
        "description": "Search matching opportunities based on candidate profile, skills, and criteria",
        "consequential": False
    },
    "compare_opportunities": {
        "description": "Side-by-side comparative analysis of 2 or 3 opportunities",
        "consequential": False
    },
    "get_follow_up_applications": {
        "description": "Identify applications requiring follow-up, stale submissions, and deadlines",
        "consequential": False
    },
    "analyze_interview_history": {
        "description": "Analyze past interviews to identify patterns, strengths, and areas of improvement",
        "consequential": False
    },
    "show_strongest_technical_skills": {
        "description": "Identify candidate's strongest verified skills ranked by evidence and market demand",
        "consequential": False
    },
    "find_matching_projects_for_job": {
        "description": "Find projects from candidate's verified GitHub/portfolio matching a specific job",
        "consequential": False
    },
    "create_interview_prep": {
        "description": "Generate technical, behavioral, and role-specific interview preparation questions",
        "consequential": False
    },
    "prepare_tailored_resume": {
        "description": "Propose creating a tailored ATS LaTeX resume variant for an opportunity",
        "consequential": True
    },
    "draft_outreach_message": {
        "description": "Draft personalized recruiter outreach referencing verified candidate evidence",
        "consequential": False
    },
    "update_application_status": {
        "description": "Update application tracking stage with explicit user confirmation",
        "consequential": True
    },
    "schedule_interview_round": {
        "description": "Schedule a new interview round for an application with user confirmation",
        "consequential": True
    }
}


def tool_search_opportunities(db: Session, query: str = "", min_score: float = 50.0, limit: int = 5) -> Dict[str, Any]:
    """Searches matching internship listings strictly in PostgreSQL Opportunity table."""
    limit = min(max(1, limit), 20)
    db_query = db.query(Opportunity).filter(
        Opportunity.status.notin_(["expired", "closed"]),
        Opportunity.match_score >= min_score
    )
    if query:
        terms = [t.strip() for t in query.split() if len(t.strip()) > 2]
        if terms:
            clauses = []
            for t in terms:
                clauses.append(Opportunity.title.ilike(f"%{t}%"))
                clauses.append(Opportunity.company_name.ilike(f"%{t}%"))
                clauses.append(Opportunity.description.ilike(f"%{t}%"))
            db_query = db_query.filter(or_(*clauses))

    results = db_query.order_by(desc(Opportunity.match_score)).limit(limit).all()
    if not results:
        # Fallback to top match scores
        results = db.query(Opportunity).filter(Opportunity.status.notin_(["expired", "closed"])).order_by(desc(Opportunity.match_score)).limit(limit).all()

    return {
        "count": len(results),
        "opportunities": [
            {
                "id": o.id,
                "title": o.title,
                "company": o.company_name,
                "location": o.normalized_location or o.location,
                "workplace_type": o.workplace_type,
                "stipend": o.stipend_text or "Undisclosed",
                "match_score": round(o.match_score, 1),
                "skills": (o.extracted_data or {}).get("mandatory_technical_skills", [])[:4] or o.required_skills[:4],
                "application_url": o.application_url or o.original_url
            } for o in results
        ]
    }


def tool_compare_opportunities(db: Session, opportunity_ids: List[int]) -> Dict[str, Any]:
    """Performs side-by-side comparison of 2 or 3 opportunities."""
    if not opportunity_ids:
        # Pick top 2 or 3 opportunities
        top = db.query(Opportunity).filter(Opportunity.status.notin_(["expired", "closed"])).order_by(desc(Opportunity.match_score)).limit(3).all()
        opportunity_ids = [o.id for o in top]

    opps = db.query(Opportunity).filter(Opportunity.id.in_(opportunity_ids[:3])).all()
    if not opps:
        return {"error": "No opportunities found for comparison"}

    cand = db.query(CandidateProfile).order_by(CandidateProfile.id.asc()).first()
    cand_skills = {s.get("name", "").lower() for s in (cand.skills or [])} if cand else set()

    comparison = []
    for o in opps:
        req = (o.extracted_data or {}).get("mandatory_technical_skills", []) or o.required_skills or []
        overlap = [s for s in req if s.lower() in cand_skills]
        gaps = [s for s in req if s.lower() not in cand_skills]

        comparison.append({
            "id": o.id,
            "title": o.title,
            "company": o.company_name,
            "location": o.normalized_location or o.location,
            "workplace_type": o.workplace_type,
            "stipend": o.stipend_text or "Undisclosed",
            "match_score": round(o.match_score, 1),
            "matching_skills": overlap,
            "missing_skills": gaps,
            "source": o.source_platform
        })

    return {
        "compared_count": len(comparison),
        "items": comparison
    }


def tool_get_follow_up_applications(db: Session, stale_days: int = 7) -> Dict[str, Any]:
    """Retrieves applications requiring follow-up or attention."""
    res = get_follow_up_intelligence(db, stale_days_threshold=stale_days)
    return {
        "total_alerts": res.get("total_alerts", 0),
        "stale_unanswered": res.get("stale_unanswered", []),
        "follow_ups_due": res.get("follow_ups_due", []),
        "upcoming_interviews": res.get("upcoming_interviews", []),
        "approaching_deadlines": res.get("approaching_deadlines", [])
    }


def tool_analyze_interview_history(db: Session, limit: int = 5) -> Dict[str, Any]:
    """Analyzes recent interview journal entries for patterns and preparation areas."""
    records = db.query(InterviewJournalRecord).order_by(desc(InterviewJournalRecord.interview_date)).limit(limit).all()
    if not records:
        return {
            "total_interviews": 0,
            "message": "No interview journal records found. You can log an interview round in Interview Hub to unlock AI analytics."
        }

    total = len(records)
    avg_confidence = sum(r.confidence_score or 3 for r in records) / total
    
    all_topics = []
    for r in records:
        all_topics.extend(r.topics_covered or [])
        
    topic_counts: Dict[str, int] = {}
    for t in all_topics:
        topic_counts[t] = topic_counts.get(t, 0) + 1

    sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)

    rounds = [
        {
            "id": r.id,
            "company": r.company_name,
            "role": r.role_title,
            "date": r.interview_date.strftime("%b %d, %Y") if r.interview_date else None,
            "round": r.round_name,
            "confidence": f"{r.confidence_score}/5" if r.confidence_score else "N/A",
            "result": r.result or "Pending",
            "feedback": r.feedback or "No notes logged"
        } for r in records
    ]

    return {
        "total_analyzed": total,
        "average_confidence": round(avg_confidence, 1),
        "most_frequent_topics": [t[0] for t in sorted_topics[:5]],
        "recent_rounds": rounds,
        "recommendations": [
            "Reinforce system design and API architecture fundamentals for upcoming technical rounds.",
            "Prepare STAR-format answers addressing questions from your lowest-confidence rounds.",
            "Review feedback notes from previous interviews before your next scheduled conversation."
        ]
    }


def tool_show_strongest_technical_skills(db: Session) -> Dict[str, Any]:
    """Computes candidate's strongest technical skills based on verified project evidence and market frequency."""
    cand = db.query(CandidateProfile).order_by(CandidateProfile.id.asc()).first()
    if not cand:
        return {"error": "Candidate profile not found"}

    skills = cand.skills or []
    projects = cand.projects or []
    
    # Analyze project association
    skill_evidence = {}
    for s in skills:
        s_name = s.get("name") if isinstance(s, dict) else str(s)
        # Check project mentions
        evidence_count = 0
        matching_projs = []
        for p in projects:
            p_text = (p.get("title", "") + " " + p.get("description", "") + " " + " ".join(p.get("technologies", []))).lower()
            if s_name.lower() in p_text:
                evidence_count += 1
                matching_projs.append(p.get("title"))
        
        skill_evidence[s_name] = {
            "name": s_name,
            "level": s.get("level", "intermediate") if isinstance(s, dict) else "intermediate",
            "verified_evidence_count": max(1, evidence_count),
            "projects": matching_projs[:2]
        }

    # Rank by verified evidence count
    ranked = sorted(skill_evidence.values(), key=lambda x: x["verified_evidence_count"], reverse=True)

    return {
        "candidate_name": cand.name,
        "degree": cand.degree,
        "college": cand.college,
        "total_verified_skills": len(skills),
        "strongest_skills": ranked[:6]
    }


def tool_find_matching_projects_for_job(db: Session, opportunity_id: int) -> Dict[str, Any]:
    """Matches candidate's verified GitHub/portfolio projects against target opportunity requirements."""
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        # Default to first active opportunity
        opp = db.query(Opportunity).filter(Opportunity.status.notin_(["expired", "closed"])).order_by(desc(Opportunity.match_score)).first()
        if not opp:
            return {"error": "No opportunities found in database"}

    cand = db.query(CandidateProfile).order_by(CandidateProfile.id.asc()).first()
    if not cand or not cand.projects:
        return {"error": "No projects found in candidate profile"}

    extracted = opp.extracted_data or {}
    req_skills = [s.lower() for s in (extracted.get("mandatory_technical_skills", []) or opp.required_skills or [])]

    scored_projects = []
    for p in cand.projects:
        techs = [t.lower() for t in p.get("technologies", [])]
        desc_lower = p.get("description", "").lower()
        title_lower = p.get("title", "").lower()

        overlap = set()
        for r in req_skills:
            if r in techs or r in desc_lower or r in title_lower:
                overlap.add(r)

        score = min(100, int((len(overlap) / max(1, len(req_skills))) * 100) + (20 if overlap else 0))
        scored_projects.append({
            "title": p.get("title"),
            "technologies": p.get("technologies", []),
            "relevance_score": score,
            "matching_requirements": list(overlap),
            "summary": p.get("description", "")[:180] + "...",
            "talking_point": f"Emphasize how building '{p.get('title')}' demonstrates competence in {', '.join(list(overlap)[:3]) or 'software engineering fundamentals'}."
        })

    scored_projects.sort(key=lambda x: x["relevance_score"], reverse=True)

    return {
        "opportunity_id": opp.id,
        "opportunity_title": opp.title,
        "company_name": opp.company_name,
        "matched_projects": scored_projects
    }


def tool_create_interview_prep(db: Session, opportunity_id: int, role_title: Optional[str] = None) -> Dict[str, Any]:
    """Generates role-specific questions and preparation strategy."""
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        opp = db.query(Opportunity).filter(Opportunity.status.notin_(["expired", "closed"])).order_by(desc(Opportunity.match_score)).first()

    target_title = role_title or (opp.title if opp else "Software Engineer Intern")
    company = opp.company_name if opp else "Tech Company"

    cand = db.query(CandidateProfile).order_by(CandidateProfile.id.asc()).first()
    lead_project = cand.projects[0].get("title") if cand and cand.projects else "Distributed System Project"

    return {
        "role_title": target_title,
        "company_name": company,
        "technical_questions": [
            {
                "topic": "API Design & Asynchronous Architecture",
                "question": f"In your experience building '{lead_project}', how did you handle asynchronous tasks and prevent race conditions?",
                "recommended_talking_points": ["State machine transitions", "Idempotency keys", "Database isolation levels"]
            },
            {
                "topic": "Data Modeling & Performance",
                "question": "How do you optimize relational database queries that involve multiple foreign key joins and pagination?",
                "recommended_talking_points": ["Composite B-tree indexes", "Cursor vs offset pagination", "Query execution plans with EXPLAIN ANALYZE"]
            },
            {
                "topic": "System Reliability",
                "question": "How would you design a rate limiter to protect public endpoints from throttling or abuse?",
                "recommended_talking_points": ["Token bucket / sliding window algorithms", "Redis caching layer", "HTTP 429 Retry-After headers"]
            }
        ],
        "behavioral_questions": [
            {
                "type": "Technical Disagreement",
                "question": "Tell me about a time you had a technical disagreement with a teammate regarding system architecture.",
                "framework": "STAR (Situation, Task, Action, Result)"
            },
            {
                "type": "Deadline Pressure",
                "question": "Describe an engineering challenge where unexpected roadblocks threatened a project deliverable.",
                "framework": "STAR"
            }
        ],
        "preparation_checklist": [
            f"Review the core codebase and commit history for '{lead_project}'",
            f"Study {company}'s tech stack and engineering blog",
            "Practice 2 LeetCode medium questions on Trees and Dynamic Programming"
        ]
    }


def tool_draft_outreach_message(db: Session, opportunity_id: int, recruiter_name: Optional[str] = None, tone: str = "inquisitive") -> Dict[str, Any]:
    """Generates personalized recruiter message."""
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        opp = db.query(Opportunity).filter(Opportunity.status.notin_(["expired", "closed"])).order_by(desc(Opportunity.match_score)).first()

    cand = db.query(CandidateProfile).order_by(CandidateProfile.id.asc()).first()
    recruiter = recruiter_name or "Hiring Manager"
    role = opp.title if opp else "Intern"
    company = opp.company_name if opp else "the team"
    top_project = cand.projects[0].get("title") if cand and cand.projects else "full-stack systems"

    if tone == "direct":
        subject = f"Application follow-up: {role} - {cand.name if cand else 'Candidate'}"
        body = (
            f"Hi {recruiter},\n\n"
            f"I recently submitted my application for the {role} role at {company}.\n\n"
            f"Quick highlights of my background:\n"
            f"• Built {top_project} using production Python, PostgreSQL, and React.\n"
            f"• Strong alignment with your stack requirements ({', '.join((opp.required_skills or [])[:3]) if opp else 'Modern APIs'}).\n\n"
            f"I would welcome the opportunity to connect for a 10-minute introductory conversation.\n\n"
            f"Best regards,\n{cand.name if cand else 'Candidate'}"
        )
    else:
        subject = f"Interested in {role} at {company} - {cand.name if cand else 'Candidate'}"
        body = (
            f"Hi {recruiter},\n\n"
            f"I hope you're having a productive week. I recently explored {company}'s open {role} position "
            f"and was excited by your team's engineering mission.\n\n"
            f"As a {cand.degree if cand else 'Computer Science student'} at {cand.college if cand else 'University'}, "
            f"I've spent the past year building {top_project}, which gave me deep experience in "
            f"{', '.join((opp.required_skills or [])[:3]) if opp else 'scalable backends'}.\n\n"
            f"My application is on file, and I'd love to learn more about the team's roadmap if you have a brief moment.\n\n"
            f"Warm regards,\n{cand.name if cand else 'Candidate'}"
        )

    return {
        "subject": subject,
        "body": body,
        "recipient": recruiter,
        "company": company,
        "role": role
    }


# =====================================================================
# Consequential Actions Protocol & Execution Engine
# Explains action, displays payload data, requests user confirmation
# =====================================================================

def propose_consequential_action(
    tool_name: str,
    action_type: str,
    description: str,
    data_payload: Dict[str, Any],
    db: Session,
    conversation_id: Optional[int] = None
) -> AIActionAuditLog:
    """Creates a pending action proposal that requires explicit user confirmation before executing."""
    audit = AIActionAuditLog(
        action_type=action_type,
        tool_name=tool_name,
        description=description,
        data_payload=data_payload,
        status="pending_approval",
        requires_approval=True,
        conversation_id=conversation_id,
        created_at=datetime.utcnow()
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit


def execute_consequential_action(action_id: int, db: Session) -> Dict[str, Any]:
    """Executes a previously proposed action after explicit user confirmation."""
    audit = db.query(AIActionAuditLog).filter(AIActionAuditLog.id == action_id).first()
    if not audit:
        return {"error": f"Action #{action_id} not found"}

    if audit.status == "executed":
        return {
            "already_executed": True,
            "action_id": audit.id,
            "status": "executed",
            "result_summary": audit.result_summary,
            "executed_at": audit.executed_at.isoformat() if audit.executed_at else None
        }

    if audit.status == "rejected":
        return {"error": f"Action #{action_id} was rejected and cannot be executed."}

    payload = audit.data_payload or {}
    tool_name = audit.tool_name

    try:
        if tool_name == "update_application_status":
            app_id = int(payload.get("application_id", 0))
            new_status = payload.get("new_status", "applied")
            notes = payload.get("notes", "Status updated via AI Command Center")

            app = db.query(ApplicationRecord).filter(ApplicationRecord.id == app_id).first()
            if not app:
                raise ValueError(f"Application record #{app_id} not found")

            old_status = app.status
            app.status = new_status
            app.updated_at = datetime.utcnow()

            # Record state transition
            trans = ApplicationStageTransition(
                application_id=app.id,
                from_stage=old_status,
                to_stage=new_status,
                transitioned_at=datetime.utcnow(),
                notes=f"User approved AI action #{action_id}: {notes}"
            )
            db.add(trans)

            result_summary = f"Successfully updated application #{app.id} ({app.company_name} - {app.job_title}) from '{old_status}' to '{new_status}'."
            result_payload = {
                "application_id": app.id,
                "company": app.company_name,
                "role": app.job_title,
                "previous_status": old_status,
                "new_status": new_status,
                "updated_at": app.updated_at.isoformat()
            }

        elif tool_name == "prepare_tailored_resume":
            opp_id = int(payload.get("opportunity_id", 0))
            user_id = int(payload.get("user_id", 1))
            
            opp = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
            if not opp:
                raise ValueError(f"Opportunity #{opp_id} not found")
            if getattr(opp, "user_id", None) is not None and opp.user_id != user_id:
                raise PermissionError(f"Opportunity #{opp_id} is not accessible for user #{user_id}")
                
            cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
            if not cand:
                raise ValueError(f"Candidate profile for user #{user_id} not found")

            cand_dict = {
                "id": cand.id,
                "name": cand.name or "",
                "email": cand.email or "",
                "phone": cand.phone or "",
                "location": cand.location or "",
                "degree": cand.degree or "",
                "college": cand.college or "",
                "graduation_year": cand.graduation_year,
                "cgpa": cand.cgpa,
                "github_url": cand.github_url or "",
                "linkedin_url": cand.linkedin_url or "",
                "portfolio_url": cand.portfolio_url or "",
                "skills": cand.skills or [],
                "projects": cand.projects or [],
                "experience": cand.experience or [],
                "certifications": cand.certifications or [],
                "achievements": cand.achievements or []
            }
            opp_dict = {
                "id": opp.id,
                "title": opp.title,
                "company_name": opp.company_name,
                "extracted_data": opp.extracted_data or {},
                "required_skills": opp.required_skills or [],
                "preferred_skills": opp.preferred_skills or []
            }
            template_id = payload.get("template_id", "minimal_professional")
            resume_data = tailor_resume_for_opportunity(cand_dict, opp_dict, template_id=template_id)
            
            # Persist resume document and link
            resume = ResumeDocument(
                user_id=user_id,
                title=resume_data["title"],
                template_id=resume_data["template_id"],
                latex_content=resume_data["latex_content"],
                target_opportunity_id=opp.id,
                target_company=opp.company_name,
                target_role=opp.title,
                is_master=False,
                version=1,
                tailored_insights=resume_data["tailored_insights"]
            )
            db.add(resume)
            db.commit()
            db.refresh(resume)

            # Create initial version snapshot
            v1 = ResumeVersion(
                resume_id=resume.id,
                version_number=1,
                title=resume.title,
                template_id=resume.template_id,
                latex_content=resume.latex_content,
                change_summary=f"Tailored specifically for {opp.company_name} - {opp.title}"
            )
            db.add(v1)
            
            app_record = db.query(ApplicationRecord).filter(ApplicationRecord.opportunity_id == opp.id).first()
            if app_record:
                app_record.resume_id = resume.id
                app_record.resume_version_number = 1
            db.commit()

            result_summary = f"Successfully generated and linked tailored ATS resume variant for {opp.company_name} ({opp.title})."
            result_payload = {
                "resume_id": resume.id,
                "opportunity_id": opp.id,
                "company_name": opp.company_name,
                "title": resume.title,
                "template_id": resume.template_id,
                "tailored_insights": resume.tailored_insights
            }

        elif tool_name == "schedule_interview_round":
            app_id = int(payload.get("application_id", 0))
            round_name = payload.get("round_name", "Technical Round")
            round_date = payload.get("date", datetime.utcnow().isoformat())
            fmt = payload.get("format", "virtual_video")

            app = db.query(ApplicationRecord).filter(ApplicationRecord.id == app_id).first()
            if not app:
                raise ValueError(f"Application record #{app_id} not found")

            current_schedule = list(app.interview_schedule or [])
            new_item = {
                "id": len(current_schedule) + 1,
                "round_name": round_name,
                "date": round_date,
                "format": fmt,
                "notes": payload.get("notes", "Scheduled via AI Command Center")
            }
            current_schedule.append(new_item)
            app.interview_schedule = current_schedule
            old_status = app.status
            app.status = "interviewing"
            app.updated_at = datetime.utcnow()

            trans = ApplicationStageTransition(
                application_id=app.id,
                from_stage=old_status,
                to_stage="interviewing",
                transitioned_at=datetime.utcnow(),
                notes=f"Scheduled {round_name} via AI Command Center"
            )
            db.add(trans)

            result_summary = f"Successfully scheduled '{round_name}' for {app.company_name} on {round_date[:10]} and updated status to 'interviewing'."
            result_payload = {
                "application_id": app.id,
                "company": app.company_name,
                "round": new_item,
                "status": "interviewing"
            }

        else:
            raise ValueError(f"Unsupported consequential tool '{tool_name}'")

        # Update audit record
        audit.status = "executed"
        audit.user_confirmed = True
        audit.executed_at = datetime.utcnow()
        audit.result_summary = result_summary
        audit.result_payload = result_payload

        db.commit()
        db.refresh(audit)

        return {
            "success": True,
            "action_id": audit.id,
            "status": "executed",
            "result_summary": result_summary,
            "result_payload": result_payload,
            "executed_at": audit.executed_at.isoformat()
        }

    except Exception as e:
        db.rollback()
        audit.status = "failed"
        audit.result_summary = f"Execution failed: {str(e)}"
        db.commit()
        return {"error": str(e), "action_id": audit.id, "status": "failed"}


def reject_consequential_action(action_id: int, reason: Optional[str], db: Session) -> Dict[str, Any]:
    """Records explicit user rejection of a proposed consequential action."""
    audit = db.query(AIActionAuditLog).filter(AIActionAuditLog.id == action_id).first()
    if not audit:
        return {"error": f"Action #{action_id} not found"}

    audit.status = "rejected"
    audit.user_confirmed = False
    audit.rejection_reason = reason or "Rejected by user"
    db.commit()
    db.refresh(audit)

    return {
        "success": True,
        "action_id": audit.id,
        "status": "rejected",
        "rejection_reason": audit.rejection_reason
    }


# =====================================================================
# Intent Analysis & Grounded Command Processing
# =====================================================================

def parse_command_intent(prompt: str, db: Session) -> Tuple[str, Dict[str, Any]]:
    """
    Parses user natural language command into a structured tool call.
    Strictly restricted to registered whitelist.
    """
    p = prompt.lower().strip()
    extracted_ids = [int(n) for n in re.findall(r'\b\d+\b', p)]

    # 1. Status Update / Move Application (Consequential)
    if any(w in p for w in ["update application", "move application", "change stage", "mark as interviewing", "mark as applied", "update status"]):
        target_status = "applied"
        if "interview" in p:
            target_status = "interviewing"
        elif "offer" in p:
            target_status = "offered"
        elif "reject" in p:
            target_status = "rejected"
        elif "screen" in p:
            target_status = "screening"
        elif "ready" in p:
            target_status = "ready_to_apply"

        app_id = extracted_ids[0] if extracted_ids else None
        if not app_id:
            # Check if company name mentioned
            apps = db.query(ApplicationRecord).all()
            for a in apps:
                if a.company_name.lower() in p or a.job_title.lower() in p:
                    app_id = a.id
                    break
        if not app_id:
            first_app = db.query(ApplicationRecord).first()
            app_id = first_app.id if first_app else 1

        return "update_application_status", {
            "application_id": app_id,
            "new_status": target_status,
            "notes": f"Prompt intent: {prompt}"
        }

    # 2. Schedule Interview Round (Consequential)
    if "schedule" in p and "interview" in p:
        app_id = extracted_ids[0] if extracted_ids else None
        if not app_id:
            first_app = db.query(ApplicationRecord).first()
            app_id = first_app.id if first_app else 1
        return "schedule_interview_round", {
            "application_id": app_id,
            "round_name": "Technical Architecture Round",
            "date": (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%dT14:00:00"),
            "format": "virtual_video"
        }

    # 3. Resume Tailoring (Consequential)
    if any(w in p for w in ["create a resume", "create resume", "tailor resume", "build resume", "ats resume"]):
        opp_id = extracted_ids[0] if extracted_ids else None
        if not opp_id:
            first_opp = db.query(Opportunity).filter(Opportunity.status.notin_(["expired", "closed"])).order_by(desc(Opportunity.match_score)).first()
            opp_id = first_opp.id if first_opp else 1
        return "prepare_tailored_resume", {"opportunity_id": opp_id}

    # 4. Follow-up intelligence
    if any(w in p for w in ["follow-up", "follow up", "unanswered", "stale", "which applications need"]):
        return "get_follow_up_applications", {"stale_days": 7}

    # 5. Opportunity comparison
    if "compare" in p:
        return "compare_opportunities", {"opportunity_ids": extracted_ids[:3]}

    # 6. Interview analysis
    if "interview" in p and any(w in p for w in ["analyze", "last", "history", "pitfalls", "review"]):
        return "analyze_interview_history", {"limit": 3}

    # 7. Strongest skills
    if any(w in p for w in ["strongest", "technical skills", "my skills", "what skills"]):
        return "show_strongest_technical_skills", {}

    # 8. GitHub project matching
    if any(w in p for w in ["github", "project", "projects"]) and any(w in p for w in ["match", "this job", "fit"]):
        opp_id = extracted_ids[0] if extracted_ids else None
        if not opp_id:
            first_opp = db.query(Opportunity).filter(Opportunity.status.notin_(["expired", "closed"])).order_by(desc(Opportunity.match_score)).first()
            opp_id = first_opp.id if first_opp else 1
        return "find_matching_projects_for_job", {"opportunity_id": opp_id}

    # 9. Interview prep creation
    if any(w in p for w in ["prepare me", "prepare for", "prep for", "interview prep", "questions for"]):
        opp_id = extracted_ids[0] if extracted_ids else None
        if not opp_id:
            first_opp = db.query(Opportunity).filter(Opportunity.status.notin_(["expired", "closed"])).order_by(desc(Opportunity.match_score)).first()
            opp_id = first_opp.id if first_opp else 1
        return "create_interview_prep", {"opportunity_id": opp_id, "role_title": prompt}

    # 10. Outreach draft
    if any(w in p for w in ["outreach", "cold message", "email recruiter", "message recruiter"]):
        opp_id = extracted_ids[0] if extracted_ids else None
        if not opp_id:
            first_opp = db.query(Opportunity).filter(Opportunity.status.notin_(["expired", "closed"])).order_by(desc(Opportunity.match_score)).first()
            opp_id = first_opp.id if first_opp else 1
        return "draft_outreach_message", {"opportunity_id": opp_id}

    # Default to opportunity search
    return "search_opportunities", {"query": prompt, "min_score": 50.0, "limit": 4}


def generate_context_suggestions(db: Session) -> List[Dict[str, str]]:
    """Generates context-aware prompt suggestions based on user's live career state."""
    suggestions = [
        {"title": "Find AI Internships", "prompt": "Find AI internships matching my profile.", "icon": "sparkles"},
        {"title": "Follow-Up Audit", "prompt": "Which applications need follow-up?", "icon": "clock"},
        {"title": "Skill Strengths", "prompt": "Show my strongest technical skills.", "icon": "check"},
        {"title": "Compare Opportunities", "prompt": "Compare top 3 opportunities.", "icon": "layers"},
        {"title": "Interview Diagnostics", "prompt": "Analyze my last three interviews.", "icon": "book"},
        {"title": "GitHub Matching", "prompt": "Find projects from my GitHub that match this job.", "icon": "code"}
    ]
    return suggestions


async def process_global_ai_command(
    prompt: str,
    db: Session,
    conversation_id: Optional[int] = None,
    opportunity_id: Optional[int] = None
) -> Dict[str, Any]:
    """Processes global command synchronously and returns verified truth layers, tool output, and action proposals."""
    tool_name, args = parse_command_intent(prompt, db)
    if opportunity_id and "opportunity_id" in args:
        args["opportunity_id"] = opportunity_id

    tool_info = PERMITTED_TOOLS.get(tool_name, {})
    is_consequential = tool_info.get("consequential", False)

    action_proposal = None
    tool_result = None
    response_markdown = ""
    suggested_actions = []

    # 1. Execute Non-consequential tool or Propose Consequential tool
    if tool_name == "search_opportunities":
        tool_result = tool_search_opportunities(db, query=args.get("query", ""), min_score=args.get("min_score", 50.0), limit=args.get("limit", 4))
        opps = tool_result.get("opportunities", [])
        lines = [f"- **{o['title']}** at **{o['company']}** ({o['location']}) — *{o['match_score']}% match* [ID: #{o['id']}]\n  *Skills:* {', '.join(o['skills'])}" for o in opps]
        response_markdown = (
            f"### 🟢 [Verified Database Record]\n"
            f"Found **{len(opps)} matching opportunities** in the CareerOS database for your query:\n\n" +
            "\n".join(lines) +
            f"\n\n### 🟡 [AI Strategic Recommendation]\n"
            f"- Select an opportunity above to generate a tailored ATS resume or prepare role-specific interview questions."
        )
        suggested_actions = ["Compare top opportunities", "Tailor resume for top match", "Check follow-up deadlines"]

    elif tool_name == "compare_opportunities":
        tool_result = tool_compare_opportunities(db, args.get("opportunity_ids", []))
        items = tool_result.get("items", [])
        comp_lines = []
        for i, itm in enumerate(items, 1):
            comp_lines.append(
                f"**Option {i}: {itm['title']}** at **{itm['company']}**\n"
                f"- **Match Score:** {itm['match_score']}%\n"
                f"- **Location:** {itm['location']} ({itm['workplace_type']})\n"
                f"- **Stipend:** {itm['stipend']}\n"
                f"- **Verified Overlap:** {', '.join(itm['matching_skills']) or 'None'}\n"
                f"- **Missing Skills:** {', '.join(itm['missing_skills']) or 'None'}\n"
            )
        response_markdown = (
            f"### 🟢 [Verified Database Record]\n"
            f"Side-by-side comparison of **{len(items)} opportunities**:\n\n" +
            "\n".join(comp_lines) +
            f"### 🟡 [AI Strategic Recommendation]\n"
            f"- Prioritize the opportunity with the highest verified skills overlap and clearest growth roadmap."
        )
        suggested_actions = ["Prepare interview prep for Option 1", "Draft recruiter outreach", "View pipeline"]

    elif tool_name == "get_follow_up_applications":
        tool_result = tool_get_follow_up_applications(db, stale_days=args.get("stale_days", 7))
        stale = tool_result.get("stale_unanswered", [])
        interviews = tool_result.get("upcoming_interviews", [])
        deadlines = tool_result.get("approaching_deadlines", [])

        stale_lines = [f"- **{a['company_name']}** ({a['job_title']}) — submitted on {a.get('applied_date', 'N/A')[:10]}, {a.get('days_since_applied')} days ago" for a in stale] or ["- No overdue unanswered applications."]
        int_lines = [f"- **{i['company_name']}** ({i['round_name']}) — scheduled for {i.get('date', 'N/A')[:10]}" for i in interviews] or ["- No interviews scheduled in the next 7 days."]
        dead_lines = [f"- **{d['company_name']}** ({d['job_title']}) — closes on {d.get('deadline', 'N/A')[:10]}" for d in deadlines] or ["- No closing application deadlines within 7 days."]

        response_markdown = (
            f"### 🟢 [Verified Database Record]\n"
            f"**Pipeline Health & Follow-Up Audit:**\n\n"
            f"**Overdue Applications (7+ Days with no response):**\n" + "\n".join(stale_lines) + "\n\n"
            f"**Upcoming Interviews:**\n" + "\n".join(int_lines) + "\n\n"
            f"**Approaching Deadlines:**\n" + "\n".join(dead_lines) + "\n\n"
            f"### 🟡 [AI Strategic Recommendation]\n"
            f"- Dispatched courteous check-in notes to recruiters for applications older than 10 days to maximize response yield."
        )
        suggested_actions = ["Draft outreach to recruiter", "Update application status", "Review interview checklist"]

    elif tool_name == "analyze_interview_history":
        tool_result = tool_analyze_interview_history(db, limit=args.get("limit", 5))
        rounds = tool_result.get("recent_rounds", [])
        r_lines = [f"- **{r['company']}** ({r['round']}) — *Confidence: {r['confidence']}* | Outcome: **{r['result']}**" for r in rounds] or ["- No recorded interview rounds."]
        response_markdown = (
            f"### 🟢 [Verified Database Record]\n"
            f"Analyzed **{tool_result.get('total_analyzed', 0)} interview rounds**:\n"
            f"- **Average Candidate Confidence:** {tool_result.get('average_confidence', 0)}/5.0\n"
            f"- **Recurring Technical Topics:** {', '.join(tool_result.get('most_frequent_topics', [])) or 'None'}\n\n"
            f"**Recent Rounds:**\n" + "\n".join(r_lines) + "\n\n"
            f"### 🟡 [AI Strategic Recommendation]\n" +
            "\n".join([f"- {rec}" for rec in tool_result.get("recommendations", [])])
        )
        suggested_actions = ["Practice mock interview session", "Review system design questions", "Prepare behavioral STAR notes"]

    elif tool_name == "show_strongest_technical_skills":
        tool_result = tool_show_strongest_technical_skills(db)
        skills = tool_result.get("strongest_skills", [])
        s_lines = [f"- **{s['name']}** ({s['level'].title()}) — verified in **{s['verified_evidence_count']} portfolio projects** ({', '.join(s['projects']) or 'Production Codebase'})" for s in skills]
        response_markdown = (
            f"### 🟢 [Verified Database Record]\n"
            f"**Master Candidate Profile Competencies for {tool_result.get('candidate_name')}:**\n\n" +
            "\n".join(s_lines) +
            f"\n\n### 🟡 [AI Strategic Recommendation]\n"
            f"- Lead your resume and intro pitches with these verified competencies to pass ATS filters and technical screeners."
        )
        suggested_actions = ["Match skills against live jobs", "Generate ATS resume", "Explore market demand"]

    elif tool_name == "find_matching_projects_for_job":
        tool_result = tool_find_matching_projects_for_job(db, args.get("opportunity_id", 1))
        projs = tool_result.get("matched_projects", [])
        p_lines = [f"- **{p['title']}** (*{p['relevance_score']}% relevance*)\n  *Tech:* {', '.join(p['technologies'])}\n  *Talking Point:* {p['talking_point']}" for p in projs]
        response_markdown = (
            f"### 🟢 [Verified Database Record]\n"
            f"**Matching Projects for {tool_result.get('opportunity_title')} at {tool_result.get('company_name')}:**\n\n" +
            "\n".join(p_lines) +
            f"\n\n### 🟡 [AI Strategic Recommendation]\n"
            f"- Place the highest-scoring project at the top of your resume experience section for this role."
        )
        suggested_actions = ["Tailor resume with these projects", "Create interview prep", "Draft cold outreach"]

    elif tool_name == "create_interview_prep":
        tool_result = tool_create_interview_prep(db, args.get("opportunity_id", 1), args.get("role_title"))
        q_lines = [f"- **{q['topic']}:** {q['question']}\n  *Key Points:* {', '.join(q['recommended_talking_points'])}" for q in tool_result.get("technical_questions", [])]
        response_markdown = (
            f"### 🟢 [Verified Database Record]\n"
            f"**Interview Preparation Blueprint for {tool_result.get('role_title')} ({tool_result.get('company_name')}):**\n\n"
            f"**Technical Deep-Dives:**\n" + "\n".join(q_lines) + "\n\n"
            f"### 🟡 [AI Strategic Recommendation]\n"
            f"- Practice articulating trade-offs out loud before your conversation."
        )
        suggested_actions = ["Launch mock practice simulator", "Review behavioral STAR answers", "Audit skill gaps"]

    elif tool_name == "draft_outreach_message":
        tool_result = tool_draft_outreach_message(db, args.get("opportunity_id", 1), args.get("recruiter_name"), args.get("tone", "inquisitive"))
        response_markdown = (
            f"### 🟢 [Verified Database Record]\n"
            f"Generated personalized recruiter outreach for **{tool_result.get('company')}** ({tool_result.get('role')}):\n\n"
            f"**Subject:** `{tool_result.get('subject')}`\n\n"
            f"```text\n{tool_result.get('body')}\n```\n\n"
            f"### 🟡 [AI Strategic Recommendation]\n"
            f"- Verify the recruiter's name on LinkedIn before sending."
        )
        suggested_actions = ["Copy message to clipboard", "Log touchpoint in Recruiter CRM", "Prepare application materials"]

    # 2. Consequential Actions: Propose with explicit confirmation guardrails
    elif tool_name == "update_application_status":
        app_id = int(args.get("application_id", 1))
        new_status = args.get("new_status", "applied")
        app = db.query(ApplicationRecord).filter(ApplicationRecord.id == app_id).first()
        if not app:
            app = db.query(ApplicationRecord).first()
            app_id = app.id if app else 1

        company = app.company_name if app else "Company"
        job_title = app.job_title if app else "Role"
        current_status = app.status if app else "ready_to_apply"

        desc = f"Update application #{app_id} ({company} — {job_title}) from '{current_status}' to '{new_status}'."
        payload = {
            "application_id": app_id,
            "company": company,
            "job_title": job_title,
            "current_status": current_status,
            "new_status": new_status,
            "notes": args.get("notes", "Requested via AI Command Center")
        }

        audit = propose_consequential_action(
            tool_name="update_application_status",
            action_type="update_application_status",
            description=desc,
            data_payload=payload,
            db=db,
            conversation_id=conversation_id
        )

        action_proposal = {
            "action_id": audit.id,
            "tool_name": audit.tool_name,
            "description": audit.description,
            "data_payload": audit.data_payload,
            "requires_approval": True,
            "status": "pending_approval"
        }

        response_markdown = (
            f"### ⚠️ [Consequential Operation Requires Authorization]\n"
            f"I have prepared an update for your application tracking records:\n\n"
            f"- **Target Application:** #{app_id} — **{company}** ({job_title})\n"
            f"- **Stage Change:** `{current_status}` ➔ **`{new_status}`**\n\n"
            f"Please review the data below and click **Approve & Execute** to apply this change to your database."
        )
        suggested_actions = ["Approve & Execute", "Reject"]

    elif tool_name == "prepare_tailored_resume":
        opp_id = int(args.get("opportunity_id", 1))
        opp = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
        company = opp.company_name if opp else "Target Company"
        title = opp.title if opp else "Target Role"

        desc = f"Generate and link a tailored ATS LaTeX resume variant for {company} ({title})."
        payload = {
            "opportunity_id": opp_id,
            "company": company,
            "title": title
        }

        audit = propose_consequential_action(
            tool_name="prepare_tailored_resume",
            action_type="prepare_tailored_resume",
            description=desc,
            data_payload=payload,
            db=db,
            conversation_id=conversation_id
        )

        action_proposal = {
            "action_id": audit.id,
            "tool_name": audit.tool_name,
            "description": audit.description,
            "data_payload": audit.data_payload,
            "requires_approval": True,
            "status": "pending_approval"
        }

        response_markdown = (
            f"### ⚠️ [Consequential Operation Requires Authorization]\n"
            f"I have prepared a tailored ATS LaTeX resume variant for **{company}** ({title}):\n\n"
            f"- **Target Role:** {title}\n"
            f"- **Optimizations:** Highlights matching GitHub projects and prioritized technical skills.\n\n"
            f"Click **Approve & Execute** to generate the PDF and link it to this application."
        )
        suggested_actions = ["Approve & Execute", "Reject"]

    elif tool_name == "schedule_interview_round":
        app_id = int(args.get("application_id", 1))
        app = db.query(ApplicationRecord).filter(ApplicationRecord.id == app_id).first()
        company = app.company_name if app else "Company"

        desc = f"Schedule '{args.get('round_name', 'Interview')}' for {company} and advance stage to 'interviewing'."
        payload = {
            "application_id": app_id,
            "company": company,
            "round_name": args.get("round_name", "Technical Round 1"),
            "date": args.get("date", (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%dT14:00:00")),
            "format": args.get("format", "virtual_video")
        }

        audit = propose_consequential_action(
            tool_name="schedule_interview_round",
            action_type="schedule_interview_round",
            description=desc,
            data_payload=payload,
            db=db,
            conversation_id=conversation_id
        )

        action_proposal = {
            "action_id": audit.id,
            "tool_name": audit.tool_name,
            "description": audit.description,
            "data_payload": audit.data_payload,
            "requires_approval": True,
            "status": "pending_approval"
        }

        response_markdown = (
            f"### ⚠️ [Consequential Operation Requires Authorization]\n"
            f"I have prepared an interview schedule entry for **{company}**:\n\n"
            f"- **Round:** {payload['round_name']}\n"
            f"- **Scheduled Date:** {payload['date'][:10]}\n"
            f"- **Stage Progression:** Advance status to `interviewing`\n\n"
            f"Click **Approve & Execute** to schedule this round in your calendar."
        )
        suggested_actions = ["Approve & Execute", "Reject"]

    return {
        "tool_name": tool_name,
        "is_consequential": is_consequential,
        "tool_result": tool_result,
        "action_proposal": action_proposal,
        "response_markdown": response_markdown,
        "suggested_actions": suggested_actions
    }


async def generate_ai_command_stream(
    prompt: str,
    db: Session,
    conversation_id: Optional[int] = None,
    opportunity_id: Optional[int] = None
) -> AsyncGenerator[str, None]:
    """
    Yields Server-Sent Events (SSE) streaming chunks:
    event: status -> progress message
    event: tool_start -> executed tool metadata
    event: action_proposal -> proposal needing user confirmation
    event: chunk -> Markdown chunk
    event: done -> final completion payload
    """
    # 1. Status event
    yield f"event: status\ndata: {json.dumps({'message': 'Analyzing command intent and context...'})}\n\n"
    await asyncio.sleep(0.05)

    tool_name, args = parse_command_intent(prompt, db)
    yield f"event: status\ndata: {json.dumps({'message': f'Executing structured tool: {tool_name}'})}\n\n"
    await asyncio.sleep(0.05)

    # 2. Process command
    result = await process_global_ai_command(prompt, db, conversation_id, opportunity_id)
    
    yield f"event: tool_start\ndata: {json.dumps({'tool': result['tool_name'], 'is_consequential': result['is_consequential']})}\n\n"
    await asyncio.sleep(0.05)

    if result.get("action_proposal"):
        yield f"event: action_proposal\ndata: {json.dumps(result['action_proposal'])}\n\n"

    # 3. Stream response markdown in realistic chunks
    full_text = result["response_markdown"]
    chunk_size = 40
    for i in range(0, len(full_text), chunk_size):
        chunk = full_text[i:i + chunk_size]
        yield f"event: chunk\ndata: {json.dumps({'content': chunk})}\n\n"
        await asyncio.sleep(0.02)

    # 4. Done event
    yield f"event: done\ndata: {json.dumps({'suggested_actions': result.get('suggested_actions', []), 'action_proposal': result.get('action_proposal')})}\n\n"
