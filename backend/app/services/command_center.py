import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from backend.app.models.opportunity import Opportunity
from backend.app.models.candidate import CandidateProfile
from backend.app.models.application import ApplicationRecord
from backend.app.models.application_transition import ApplicationStageTransition
from backend.app.models.interview import InterviewJournalRecord
from backend.app.models.resume import ResumeDocument
from backend.app.services.context_retriever import (
    get_candidate_context,
    get_market_skills_context,
    get_interview_history_context
)

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_command_center_overview(db: Session, date_range: str = "30d") -> Dict[str, Any]:
    """
    Computes a comprehensive, actionable Command Center overview answering the 5 core career questions:
    1. What is happening with my applications?
    2. Which opportunities should I prioritize?
    3. What action should I take today?
    4. Where am I improving or struggling?
    5. What should I focus on next?
    """
    now = _utc_now()
    
    # Calculate date cutoff
    cutoff: Optional[datetime] = None
    if date_range == "7d":
        cutoff = now - timedelta(days=7)
    elif date_range == "30d":
        cutoff = now - timedelta(days=30)
    elif date_range == "90d":
        cutoff = now - timedelta(days=90)
    elif date_range == "all":
        cutoff = None
    else:
        cutoff = now - timedelta(days=30)

    # -------------------------------------------------------------
    # 1. What is happening with my applications? (Pipeline & Funnel)
    # -------------------------------------------------------------
    app_query = db.query(ApplicationRecord)
    if cutoff:
        app_query = app_query.filter(ApplicationRecord.created_at >= cutoff)
    all_apps = app_query.order_by(desc(ApplicationRecord.created_at)).all()

    stages_count: Dict[str, int] = {
        "saved": 0,
        "ready_to_apply": 0,
        "applied": 0,
        "screening": 0,
        "interviewing": 0,
        "offered": 0,
        "rejected": 0,
        "archived": 0
    }
    for a in all_apps:
        st = a.status.lower()
        stages_count[st] = stages_count.get(st, 0) + 1

    applied_total = stages_count.get("applied", 0) + stages_count.get("screening", 0) + \
                    stages_count.get("interviewing", 0) + stages_count.get("offered", 0) + \
                    stages_count.get("rejected", 0)
    
    advanced_past_applied = stages_count.get("screening", 0) + stages_count.get("interviewing", 0) + \
                            stages_count.get("offered", 0) + stages_count.get("rejected", 0)

    response_rate = round((advanced_past_applied / applied_total * 100), 1) if applied_total > 0 else 0.0
    interview_rate = round((stages_count.get("interviewing", 0) / applied_total * 100), 1) if applied_total > 0 else 0.0
    offer_rate = round((stages_count.get("offered", 0) / max(1, stages_count.get("interviewing", 0)) * 100), 1) if stages_count.get("interviewing", 0) > 0 else 0.0

    # Overdue follow-ups (>7 days or follow_up_date <= now)
    follow_ups_due = []
    for a in all_apps:
        if a.status in ("applied", "ready_to_apply"):
            is_overdue = False
            days_waiting = 0
            if a.follow_up_date and a.follow_up_date <= now:
                is_overdue = True
                days_waiting = (now - a.follow_up_date).days
            elif a.applied_date:
                days_waiting = (now - a.applied_date).days
                if days_waiting >= 7:
                    is_overdue = True
            
            if is_overdue:
                follow_ups_due.append({
                    "application_id": a.id,
                    "opportunity_id": a.opportunity_id,
                    "company_name": a.company_name,
                    "job_title": a.job_title,
                    "status": a.status,
                    "applied_date": a.applied_date.isoformat() if a.applied_date else None,
                    "follow_up_date": a.follow_up_date.isoformat() if a.follow_up_date else None,
                    "days_waiting": days_waiting
                })

    # Activity Timeline
    timeline_events: List[Dict[str, Any]] = []

    # 1. Transitions
    trans_query = db.query(ApplicationStageTransition)
    if cutoff:
        trans_query = trans_query.filter(ApplicationStageTransition.transitioned_at >= cutoff)
    transitions = trans_query.order_by(desc(ApplicationStageTransition.transitioned_at)).limit(15).all()

    # Map app IDs to company name
    app_company_map = {a.id: a for a in all_apps}
    for t in transitions:
        app_ref = app_company_map.get(t.application_id)
        c_name = app_ref.company_name if app_ref else f"Application #{t.application_id}"
        j_title = app_ref.job_title if app_ref else ""
        timeline_events.append({
            "type": "stage_transition",
            "timestamp": t.transitioned_at.isoformat() if t.transitioned_at else now.isoformat(),
            "title": f"Moved to {t.to_stage.replace('_', ' ').title()}",
            "description": f"{c_name} - {j_title}".strip(" -"),
            "target_tab": "tracker",
            "target_id": t.application_id,
            "badge": t.to_stage
        })

    # 2. Resumes
    resume_query = db.query(ResumeDocument)
    if cutoff:
        resume_query = resume_query.filter(ResumeDocument.updated_at >= cutoff)
    recent_resumes = resume_query.order_by(desc(ResumeDocument.updated_at)).limit(5).all()
    for r in recent_resumes:
        timeline_events.append({
            "type": "resume_updated",
            "timestamp": r.updated_at.isoformat() if r.updated_at else now.isoformat(),
            "title": f"Tailored Resume: {r.title}",
            "description": f"Target: {r.target_company or 'General'} • PDF {'Ready' if r.pdf_path else 'Draft'}",
            "target_tab": "resumes",
            "target_id": r.id,
            "badge": "ATS Tailored" if not r.is_master else "Master Resume"
        })

    # 3. Interviews
    interview_query = db.query(InterviewJournalRecord)
    if cutoff:
        interview_query = interview_query.filter(InterviewJournalRecord.created_at >= cutoff)
    recent_interviews = interview_query.order_by(desc(InterviewJournalRecord.created_at)).limit(5).all()
    for iv in recent_interviews:
        timeline_events.append({
            "type": "interview_logged",
            "timestamp": iv.created_at.isoformat() if iv.created_at else now.isoformat(),
            "title": f"Interview: {iv.company_name}",
            "description": f"{iv.round_name} ({iv.round_type}) • Rating {iv.performance_rating or 'N/A'}/5.0",
            "target_tab": "interviews",
            "target_id": iv.id,
            "badge": iv.round_type
        })

    # Sort unified timeline descending
    timeline_events.sort(key=lambda x: x["timestamp"], reverse=True)
    timeline_events = timeline_events[:15]

    # -------------------------------------------------------------
    # 2. Which opportunities should I prioritize? (Rankings & Deadlines)
    # -------------------------------------------------------------
    # Upcoming deadlines within next 14 days
    deadlines_query = db.query(Opportunity).filter(
        Opportunity.deadline_at.isnot(None),
        Opportunity.deadline_at >= now
    )
    if cutoff:
        deadlines_query = deadlines_query.filter(Opportunity.deadline_at <= now + timedelta(days=14))
    upcoming_deadlines_raw = deadlines_query.order_by(Opportunity.deadline_at.asc()).limit(8).all()

    # Track which opportunities already have an application
    applied_opp_ids = {a.opportunity_id: a for a in all_apps}

    upcoming_deadlines = []
    for o in upcoming_deadlines_raw:
        days_left = max(0, (o.deadline_at - now).days)
        hours_left = max(0, int((o.deadline_at - now).total_seconds() // 3600))
        app_exists = applied_opp_ids.get(o.id)
        upcoming_deadlines.append({
            "id": o.id,
            "company_name": o.company_name,
            "title": o.title,
            "match_score": o.match_score,
            "location": o.normalized_location or o.location,
            "deadline_at": o.deadline_at.isoformat(),
            "days_left": days_left,
            "hours_left": hours_left,
            "urgency": "urgent" if days_left <= 3 else "high" if days_left <= 7 else "medium",
            "application_status": app_exists.status if app_exists else None
        })

    # Recently discovered high-match opportunities
    top_matches_query = db.query(Opportunity).filter(
        Opportunity.employment_type == "internship",
        Opportunity.match_score >= 60.0,
        Opportunity.status.in_(["active", "verified"])
    )
    if cutoff:
        top_matches_query = top_matches_query.filter(Opportunity.discovered_at >= cutoff)
    recent_relevant_raw = top_matches_query.order_by(
        desc(Opportunity.match_score),
        desc(Opportunity.discovered_at)
    ).limit(6).all()

    recently_discovered_relevant = []
    for o in recent_relevant_raw:
        app_exists = applied_opp_ids.get(o.id)
        recently_discovered_relevant.append({
            "id": o.id,
            "title": o.title,
            "company_name": o.company_name,
            "location": o.normalized_location or o.location,
            "stipend_text": o.stipend_text or "Undisclosed",
            "match_score": o.match_score,
            "source_platform": o.source_platform,
            "discovered_at": o.discovered_at.isoformat() if o.discovered_at else None,
            "deadline_at": o.deadline_at.isoformat() if o.deadline_at else None,
            "application_status": app_exists.status if app_exists else None
        })

    # -------------------------------------------------------------
    # 3. What action should I take today? (Intelligent Prioritization)
    # -------------------------------------------------------------
    prioritized_actions: List[Dict[str, Any]] = []

    # Check 1: Scheduled Interviews in next 3 days
    scheduled_interviews = db.query(InterviewJournalRecord).filter(
        InterviewJournalRecord.scheduled_at.isnot(None),
        InterviewJournalRecord.scheduled_at >= now,
        InterviewJournalRecord.scheduled_at <= now + timedelta(days=3)
    ).order_by(InterviewJournalRecord.scheduled_at.asc()).all()

    for iv in scheduled_interviews:
        prioritized_actions.append({
            "id": f"action_iv_{iv.id}",
            "priority": "urgent",
            "category": "interview",
            "title": f"Interview Preparation: {iv.company_name} ({iv.round_name})",
            "reason": f"Scheduled in {(iv.scheduled_at - now).days} day(s). Review core technical competencies and talking points.",
            "action_label": "Open Interview Prep",
            "action_type": "navigate_tab",
            "target_tab": "chat",
            "target_id": iv.application_id
        })

    # Check 2: Overdue or Pending Follow-ups
    for f in follow_ups_due[:3]:
        prioritized_actions.append({
            "id": f"action_fu_{f['application_id']}",
            "priority": "urgent" if f["days_waiting"] >= 10 else "high",
            "category": "follow_up",
            "title": f"Follow Up with {f['company_name']} ({f['job_title']})",
            "reason": f"Waiting for {f['days_waiting']} days without status transition. A professional check-in improves recruiter recall.",
            "action_label": "View in Tracker",
            "action_type": "navigate_tab",
            "target_tab": "tracker",
            "target_id": f["application_id"]
        })

    # Check 3: Approaching Deadlines on High-Match Roles (Not Yet Applied)
    for d in upcoming_deadlines:
        if not d.get("application_status") and d["days_left"] <= 7:
            prioritized_actions.append({
                "id": f"action_dl_{d['id']}",
                "priority": "urgent" if d["days_left"] <= 3 else "high",
                "category": "deadline",
                "title": f"Deadline Approaching: {d['company_name']} - {d['title']}",
                "reason": f"Application portal closes in {d['days_left']} day(s). Match score is {round(d['match_score'])}%.",
                "action_label": "Prepare Application",
                "action_type": "prepare_apply",
                "target_tab": "discover",
                "target_id": d["id"]
            })

    # Check 4: Missing Tailored Resumes for Tracked Applications
    ready_apps_no_resume = [
        a for a in all_apps if a.status in ("ready_to_apply", "applied") and not a.resume_id
    ]
    for a in ready_apps_no_resume[:2]:
        prioritized_actions.append({
            "id": f"action_res_{a.id}",
            "priority": "high",
            "category": "resume",
            "title": f"Generate ATS Resume for {a.company_name}",
            "reason": f"Application is marked as {a.status.replace('_', ' ')} but has no job-specific tailored LaTeX resume linked.",
            "action_label": "Tailor Resume Now",
            "action_type": "tailor_resume",
            "target_tab": "resumes",
            "target_id": a.opportunity_id
        })

    # Check 5: Top Unapplied Opportunity (>75% Match)
    for opp in recently_discovered_relevant:
        if not opp.get("application_status") and opp["match_score"] >= 75.0:
            prioritized_actions.append({
                "id": f"action_opp_{opp['id']}",
                "priority": "medium",
                "category": "apply",
                "title": f"High Match Opportunity: {opp['company_name']} - {opp['title']}",
                "reason": f"{round(opp['match_score'])}% verified profile alignment. Ideal target for your next submission.",
                "action_label": "Review & Apply",
                "action_type": "prepare_apply",
                "target_tab": "discover",
                "target_id": opp["id"]
            })
            break  # Limit to 1 top recommendation

    # Sort actions by priority (urgent -> high -> medium)
    priority_weights = {"urgent": 0, "high": 1, "medium": 2}
    prioritized_actions.sort(key=lambda x: priority_weights.get(x["priority"], 3))

    # -------------------------------------------------------------
    # 4. Where am I improving or struggling? (Readiness & Gaps)
    # -------------------------------------------------------------
    # Interview Readiness
    history_ctx = get_interview_history_context(db)
    
    # Resume Performance
    total_resumes = db.query(ResumeDocument).count()
    tailored_resumes = db.query(ResumeDocument).filter(ResumeDocument.is_master == False).count()
    compiled_resumes = db.query(ResumeDocument).filter(ResumeDocument.pdf_path.isnot(None)).count()
    pdf_compilation_rate = round((compiled_resumes / total_resumes * 100), 1) if total_resumes > 0 else 0.0

    # Skill Demand Gaps (Real Market Data)
    market_ctx = get_market_skills_context(db, top_n=10)
    cand_ctx = get_candidate_context(db, scope="skills_only")
    cand_skills_set = {s["name"].lower() for s in cand_ctx.get("verified_skills", [])}

    market_demanded_skills = market_ctx.get("top_market_demanded_skills", [])
    missing_skill_gaps = [
        {"skill": m["skill"], "frequency": m["frequency"]}
        for m in market_demanded_skills
        if m["skill"].lower() not in cand_skills_set
    ][:4]

    mastered_market_skills = [
        {"skill": m["skill"], "frequency": m["frequency"]}
        for m in market_demanded_skills
        if m["skill"].lower() in cand_skills_set
    ][:4]

    # -------------------------------------------------------------
    # 5. What should I focus on next? (Strategic Roadmap)
    # -------------------------------------------------------------
    next_skill_to_learn = missing_skill_gaps[0]["skill"] if missing_skill_gaps else "System Design"
    demand_count = missing_skill_gaps[0]["frequency"] if missing_skill_gaps else 1

    strategic_recommendation = {
        "focus_area": f"Acquire {next_skill_to_learn}",
        "reason": f"Required in {demand_count} active database listings not currently verified on your profile.",
        "milestone_project": f"Build a focused micro-service incorporating {next_skill_to_learn} into your existing GitHub portfolio.",
        "weekly_pace": "Aim for 3-5 verified applications with >=75% match score per week."
    }

    return {
        "date_range": date_range,
        "pipeline_summary": {
            "total_applications": len(all_apps),
            "stages_count": stages_count,
            "response_rate": response_rate,
            "interview_rate": interview_rate,
            "offer_rate": offer_rate,
            "overdue_follow_ups_count": len(follow_ups_due)
        },
        "prioritized_actions": prioritized_actions,
        "upcoming_deadlines": upcoming_deadlines,
        "follow_ups_due": follow_ups_due,
        "recently_discovered_relevant": recently_discovered_relevant,
        "readiness_diagnostics": {
            "interview": {
                "total_logged": history_ctx.get("total_interviews", 0),
                "average_performance": history_ctx.get("average_performance", 0.0),
                "average_difficulty": history_ctx.get("average_difficulty", 0.0),
                "strengths": history_ctx.get("historical_strengths", []),
                "weaknesses": history_ctx.get("historical_weaknesses", [])
            },
            "resume": {
                "total_resumes": total_resumes,
                "tailored_count": tailored_resumes,
                "compiled_pdf_rate": pdf_compilation_rate,
                "missing_resume_apps_count": len(ready_apps_no_resume)
            },
            "skills": {
                "verified_skills_count": len(cand_skills_set),
                "market_demanded_mastered": mastered_market_skills,
                "missing_high_roi_gaps": missing_skill_gaps
            }
        },
        "strategic_focus": strategic_recommendation,
        "activity_timeline": timeline_events
    }
