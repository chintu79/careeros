import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from backend.app.models.candidate import CandidateProfile
from backend.app.models.opportunity import Opportunity
from backend.app.models.preferences import UserPreferences
from backend.app.models.application import ApplicationRecord
from backend.app.models.application_transition import ApplicationStageTransition
from backend.app.models.interview import InterviewJournalRecord
from backend.app.ai.ollama_client import ollama_client
from backend.app.services.intelligence_cache import embedding_cache

logger = logging.getLogger(__name__)

def get_candidate_context(db: Session, scope: str = "full", user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Retrieves the verified Master Candidate Profile without inventing information.
    Scope can be: 'full', 'skills_only', 'projects_only', 'preferences_only'.
    When user_id is provided, the query is scoped to that candidate.
    """
    cand_q = db.query(CandidateProfile)
    if user_id is not None:
        cand_q = cand_q.filter(CandidateProfile.user_id == user_id)
    cand = cand_q.order_by(CandidateProfile.id.asc()).first()
    pref = db.query(UserPreferences).first()

    if not cand and user_id is None:
        # Legacy singleton bootstrap for code that passed no user_id.
        # Honest fallback — never invents a Candidate-1-shaped profile outside this path.
        cand = CandidateProfile(user_id=1)
        db.add(cand)
        db.commit()
        db.refresh(cand)

    if cand:
        base = {
            "id": cand.id,
            "name": cand.name,
            "email": cand.email,
            "location": cand.location,
            "degree": cand.degree,
            "college": cand.college,
            "graduation_year": cand.graduation_year,
            "cgpa": cand.cgpa,
            "work_authorization": cand.work_authorization,
            "github_url": cand.github_url,
            "portfolio_url": cand.portfolio_url,
            "linkedin_url": cand.linkedin_url,
            "evidence_version": cand.evidence_version or 1,
            "onboarding_status": cand.onboarding_status,
            "is_onboarded": (cand.onboarding_status == "completed"),
        }
    else:
        # Explicit user with no candidate row: return an honest empty shell so callers
        # render "no verified evidence" instead of crashing or fabricating Candidate 1.
        base = {
            "id": None,
            "name": None,
            "email": None,
            "location": None,
            "degree": None,
            "college": None,
            "graduation_year": None,
            "cgpa": None,
            "work_authorization": None,
            "github_url": None,
            "portfolio_url": None,
            "linkedin_url": None,
            "evidence_version": 0,
            "onboarding_status": "not_started",
            "is_onboarded": False,
        }

    if scope in ("full", "skills_only"):
        raw_skills = (cand.skills if cand else []) or []
        base["verified_skills"] = [
            {
                "name": s.get("name") if isinstance(s, dict) else str(s),
                "level": s.get("level", "intermediate") if isinstance(s, dict) else "intermediate",
                "category": s.get("category", "technical") if isinstance(s, dict) else "technical",
                "evidence": s.get("evidence", "Verified in candidate profile") if isinstance(s, dict) else "Verified in candidate profile"
            } for s in raw_skills
        ]

    if scope in ("full", "projects_only"):
        raw_projects = (cand.projects if cand else []) or []
        base["verified_projects"] = [
            {
                "title": p.get("title", ""),
                "description": p.get("description", ""),
                "tech_stack": p.get("tech_stack", []),
                "url": p.get("url", "")
            } for p in raw_projects
        ]
        base["verified_experiences"] = (cand.experience if cand else []) or []
        base["certifications"] = (cand.certifications if cand else []) or []
        base["achievements"] = (cand.achievements if cand else []) or []

    if scope in ("full", "preferences_only") and pref:
        base["preferences"] = {
            "min_stipend": pref.min_stipend,
            "paid_only": pref.paid_only,
            "allow_unpaid": pref.allow_unpaid,
            "workplace_types": pref.workplace_types or ["remote", "hybrid", "onsite"],
            "preferred_locations": pref.preferred_locations or [],
            "excluded_companies": pref.excluded_companies or [],
            "preferred_categories": pref.preferred_categories or []
        }

    return base

def get_opportunity_context(db: Session, opportunity_id: int, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Retrieves complete verified opportunity record and requirements from database."""
    opp_q = db.query(Opportunity).filter(Opportunity.id == opportunity_id)
    if user_id is not None:
        # Opportunities carry a user_id when discovered exclusively. Null user_id
        # rows are treated as shared and remain accessible to the caller.
        opp_q = opp_q.filter((Opportunity.user_id == user_id) | (Opportunity.user_id.is_(None)))
    opp = opp_q.first()
    if not opp:
        return None

    extracted = opp.extracted_data or {}
    return {
        "id": opp.id,
        "title": opp.title,
        "normalized_title": opp.normalized_title,
        "company_name": opp.company_name,
        "company_website": opp.company_website,
        "location": opp.normalized_location or opp.location,
        "workplace_type": opp.workplace_type,
        "employment_type": opp.employment_type,
        "internship_category": opp.internship_category,
        "description": opp.description or "",
        "required_skills": opp.required_skills or extracted.get("mandatory_technical_skills", []),
        "preferred_skills": opp.preferred_skills or extracted.get("preferred_skills", []),
        "responsibilities": extracted.get("responsibilities", []),
        "eligibility": opp.eligibility or extracted.get("educational_requirements", ""),
        "experience_required": opp.experience_required,
        "stipend_text": opp.stipend_text or "Undisclosed",
        "min_stipend": opp.min_stipend,
        "max_stipend": opp.max_stipend,
        "currency": opp.currency,
        "compensation_type": opp.compensation_type,
        "duration_months": opp.duration_months,
        "posted_at": opp.posted_at.isoformat() if opp.posted_at else None,
        "discovered_at": opp.discovered_at.isoformat() if opp.discovered_at else None,
        "deadline_at": opp.deadline_at.isoformat() if opp.deadline_at else None,
        "status": opp.status,
        "original_url": opp.original_url,
        "application_url": opp.application_url or opp.original_url,
        "quality_score": opp.quality_score,
        "match_score": opp.match_score,
        "eligibility_status": opp.eligibility_status,
        "match_analysis": opp.match_analysis or {}
    }

async def search_opportunities_vector(
    db: Session,
    query: str,
    limit: int = 5,
    min_score: float = 0.0
) -> List[Dict[str, Any]]:
    """
    Performs semantic vector search using BGE-M3 1024-dim embedding + pgvector cosine similarity.
    Seamlessly falls back to structured SQL keyword search if embeddings are not available.
    """
    clean_query = query.strip()
    if not clean_query:
        # Default top opportunities by match score
        opps = db.query(Opportunity).filter(
            Opportunity.employment_type == "internship",
            Opportunity.match_score >= min_score
        ).order_by(desc(Opportunity.match_score)).limit(limit).all()
        return [get_opportunity_context(db, o.id) for o in opps if o]

    # Try semantic vector search
    cache_key = f"embed_search:{clean_query.lower()}:{limit}:{min_score}"
    cached = embedding_cache.get(cache_key)
    if cached:
        return cached

    results = []
    try:
        embedding = await ollama_client.get_embedding(clean_query)
        if embedding and len(embedding) == 1024:
            vector_matches = db.query(Opportunity).filter(
                Opportunity.embedding.isnot(None),
                Opportunity.employment_type == "internship",
                Opportunity.match_score >= min_score
            ).order_by(
                Opportunity.embedding.cosine_distance(embedding)
            ).limit(limit).all()

            if vector_matches:
                results = [get_opportunity_context(db, o.id) for o in vector_matches if o]
    except Exception as e:
        logger.warning(f"Vector search failed, falling back to SQL text search: {e}")

    # Fallback to keyword text search if vector returned few results
    if len(results) < limit:
        needed = limit - len(results)
        existing_ids = {r["id"] for r in results if r}
        text_matches = db.query(Opportunity).filter(
            Opportunity.employment_type == "internship",
            Opportunity.match_score >= min_score,
            ~Opportunity.id.in_(existing_ids) if existing_ids else True,
            (Opportunity.title.ilike(f"%{clean_query}%")) |
            (Opportunity.company_name.ilike(f"%{clean_query}%")) |
            (Opportunity.description.ilike(f"%{clean_query}%"))
        ).order_by(desc(Opportunity.match_score)).limit(needed).all()

        for o in text_matches:
            ctx = get_opportunity_context(db, o.id)
            if ctx:
                results.append(ctx)

    if results:
        embedding_cache.set(cache_key, results, ttl=300)
    return results

def get_pipeline_context(db: Session, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Retrieves full application pipeline context, conversion metrics, and pending actions."""
    apps = db.query(ApplicationRecord).order_by(desc(ApplicationRecord.created_at)).all()
    by_stage: Dict[str, List[Dict[str, Any]]] = {}
    overdue_follow_ups: List[Dict[str, Any]] = []
    now = datetime.utcnow()

    for a in apps:
        item = {
            "id": a.id,
            "opportunity_id": a.opportunity_id,
            "company_name": a.company_name,
            "job_title": a.job_title,
            "status": a.status,
            "applied_date": a.applied_date.isoformat() if a.applied_date else None,
            "match_score": a.match_score,
            "follow_up_date": a.follow_up_date.isoformat() if a.follow_up_date else None,
            "submission_mode": a.submission_mode
        }
        by_stage.setdefault(a.status, []).append(item)

        # Detect overdue follow-ups
        if a.status in ("applied", "ready_to_apply") and a.applied_date:
            days_since = (now - a.applied_date).days
            if days_since >= 7:
                item["days_waiting"] = days_since
                overdue_follow_ups.append(item)

    transitions = db.query(ApplicationStageTransition).order_by(
        desc(ApplicationStageTransition.transitioned_at)
    ).limit(15).all()

    return {
        "total_applications": len(apps),
        "stages": by_stage,
        "stages_count": {stage: len(items) for stage, items in by_stage.items()},
        "overdue_follow_ups": overdue_follow_ups,
        "recent_transitions": [
            {
                "application_id": t.application_id,
                "from_stage": t.from_stage,
                "to_stage": t.to_stage,
                "at": t.transitioned_at.isoformat() if t.transitioned_at else None,
                "notes": t.notes
            } for t in transitions
        ]
    }

def get_interview_history_context(db: Session) -> Dict[str, Any]:
    """Retrieves interview performance history, Q&A patterns, and diagnostic takeaways."""
    interviews = db.query(InterviewJournalRecord).order_by(
        desc(InterviewJournalRecord.scheduled_at)
    ).all()

    all_strengths = []
    all_weaknesses = []
    qa_summary = []
    round_types = {}

    for iv in interviews:
        round_types[iv.round_type] = round_types.get(iv.round_type, 0) + 1
        feedback = iv.ai_feedback or {}
        for s in feedback.get("strengths", []):
            if s and s not in all_strengths:
                all_strengths.append(s)
        for w in feedback.get("weaknesses", []):
            if w and w not in all_weaknesses:
                all_weaknesses.append(w)

        for q in (iv.questions_asked or [])[:3]:
            qa_summary.append({
                "company": iv.company_name,
                "round": iv.round_name,
                "question": q.get("question", ""),
                "answer": q.get("candidate_answer") or q.get("user_answer", "")
            })

    avg_performance = (
        sum(iv.performance_rating for iv in interviews if iv.performance_rating) / len(interviews)
        if interviews else 0.0
    )
    avg_difficulty = (
        sum(iv.difficulty_rating for iv in interviews if iv.difficulty_rating) / len(interviews)
        if interviews else 0.0
    )

    return {
        "total_interviews": len(interviews),
        "round_types_breakdown": round_types,
        "average_performance": round(avg_performance, 1),
        "average_difficulty": round(avg_difficulty, 1),
        "historical_strengths": all_strengths[:5],
        "historical_weaknesses": all_weaknesses[:5],
        "logged_questions": qa_summary[:8]
    }

def get_market_skills_context(db: Session, top_n: int = 20) -> Dict[str, Any]:
    """Aggregates real-time market technical skill demand across all live internships in CareerOS."""
    opps = db.query(Opportunity).filter(
        Opportunity.employment_type == "internship",
        Opportunity.status.in_(["active", "verified"])
    ).all()

    skill_counts: Dict[str, int] = {}
    category_counts: Dict[str, int] = {}

    for o in opps:
        cat = o.internship_category or "software_engineering"
        category_counts[cat] = category_counts.get(cat, 0) + 1

        reqs = o.required_skills or []
        for s in reqs:
            s_name = s.strip()
            if len(s_name) > 1:
                skill_counts[s_name] = skill_counts.get(s_name, 0) + 1

    sorted_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return {
        "total_opportunities_analyzed": len(opps),
        "top_market_demanded_skills": [{"skill": s, "frequency": c} for s, c in sorted_skills],
        "category_distribution": category_counts
    }
