import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, asc

from backend.app.database import get_db
from backend.app.services.rate_limit import rate_limited
from backend.app.models.opportunity import Opportunity
from backend.app.models.application import ApplicationRecord
from backend.app.models.candidate import CandidateProfile
from backend.app.models.candidate_opportunity_match import CandidateOpportunityMatch
from backend.app.models.preferences import UserPreferences
from backend.app.models.recommendation_feedback import RecommendationFeedback
from backend.app.services.discovery_search_service import (
    execute_intelligent_discovery_search,
    build_opportunity_intelligence,
    PaginationSessionExpiredException
)
from backend.app.core.auth import get_current_user_id
from backend.app.services.matching import matching_service
from backend.app.services.recommendation_engine import generate_curated_recommendations
from backend.app.services.discovery_snapshot_manager import snapshot_manager

router = APIRouter(prefix="/opportunities", tags=["Opportunities"])

class OpportunityFeedbackRequest(BaseModel):
    feedback_type: str # dismiss, not_relevant, wrong_location, skill_mismatch, low_stipend, not_interested_company, already_applied, thumbs_up, thumbs_down
    reason_note: Optional[str] = None

@router.get("", dependencies=[Depends(rate_limited("discovery"))])
async def list_opportunities(
    tab: str = Query("recommended", pattern="^(recommended|latest|saved|expiring|applied|dismissed|all)$"),
    search_mode: str = Query("hybrid", pattern="^(hybrid|semantic|keyword|skill|company|location)$"),
    category: Optional[str] = None,
    company: Optional[str] = None,
    location: Optional[str] = None,
    workplace_type: Optional[str] = None,
    internship_type: Optional[str] = None,
    work_mode: Optional[str] = None,
    min_stipend: Optional[float] = None,
    compensation_type: Optional[str] = None,
    skills: Optional[str] = None,
    duration_months: Optional[int] = None,
    max_duration_months: Optional[int] = None,
    posted_days: Optional[int] = None,
    source_platform: Optional[str] = None,
    status: Optional[str] = None,
    eligibility_status: Optional[str] = None,
    min_score: Optional[float] = None,
    search: Optional[str] = None,
    sort_by: str = Query("match_score", pattern="^(match_score|posted_at|min_stipend|deadline_at|quality_score|discovered_at)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    page: Optional[int] = Query(None, ge=1),
    page_size: Optional[int] = Query(None, ge=1, le=100),
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    cursor: Optional[int] = Query(None, ge=0),
    snapshot_id: Optional[str] = Query(None),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    List opportunities with intelligent multi-mode search (semantic, hybrid, keyword, skill, company, location),
    rich opportunity intelligence, tab partitioning, pagination, and sorting.
    """
    if page is not None and page_size is not None:
        effective_limit = page_size
        effective_skip = (page - 1) * page_size
    elif page is not None:
        effective_limit = limit
        effective_skip = (page - 1) * limit
    else:
        effective_limit = limit
        effective_skip = skip

    try:
        items, total, res_snapshot_id, next_cursor, has_more = await execute_intelligent_discovery_search(
            db=db,
            query_str=search,
            search_mode=search_mode,
            tab=tab,
            category=category,
            company=company,
            location=location,
            workplace_type=workplace_type,
            internship_type=internship_type,
            work_mode=work_mode,
            min_stipend=min_stipend,
            compensation_type=compensation_type,
            skills=skills,
            duration_months=duration_months,
            posted_days=posted_days,
            source_platform=source_platform,
            status=status,
            eligibility_status=eligibility_status,
            min_score=min_score,
            sort_by=sort_by,
            sort_order=sort_order,
            skip=effective_skip,
            limit=effective_limit,
            cursor=cursor,
            user_id=user_id,
            snapshot_id=snapshot_id,
            return_cursor=True
        )
    except PaginationSessionExpiredException:
        return JSONResponse(
            status_code=410,
            headers={"X-Restart-Required": "true"},
            content={
                "detail": "Pagination session has expired or is invalid. Please restart search from page 1.",
                "code": "PAGINATION_SESSION_EXPIRED",
                "restart_required": True
            }
        )

    ret_page = (effective_skip // effective_limit) + 1 if effective_limit > 0 else 1
    total_pages = max(1, (total + effective_limit - 1) // effective_limit if effective_limit > 0 else 1)

    return {
        "total": total,
        "page": ret_page,
        "page_size": effective_limit,
        "total_pages": total_pages,
        "page_items": len(items),
        "snapshot_id": res_snapshot_id,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "items": items
    }


@router.get("/summary-metrics")
def get_summary_metrics(db: Session = Depends(get_db)):
    """Summary metrics banner displayed on discovery dashboard."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    total = db.query(Opportunity).count()
    new_today = db.query(Opportunity).filter(Opportunity.discovered_at >= today_start).count()
    high_match = db.query(Opportunity).filter(
        Opportunity.match_score >= 70.0,
        Opportunity.eligibility_status != "disqualified"
    ).count()
    saved = db.query(Opportunity).filter(Opportunity.is_saved == True).count()
    expiring = db.query(Opportunity).filter(
        Opportunity.deadline_at != None,
        Opportunity.deadline_at >= now,
        Opportunity.deadline_at <= now + timedelta(days=7)
    ).count()

    return {
        "total_discovered": total,
        "new_today": new_today,
        "high_match": high_match,
        "saved": saved,
        "expiring_soon": expiring
    }

@router.get("/standard-records")
def get_standard_records(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Retrieve opportunities formatted strictly in the 24-field standardized schema required by Section 4."""
    items = db.query(Opportunity).filter(Opportunity.is_dismissed == False).order_by(Opportunity.quality_score.desc().nulls_last()).offset(skip).limit(limit).all()
    return [item.to_standard_record() for item in items]

@router.post("/batch-verify")
async def batch_verify_opportunities(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Run active SSRF-safe reachability probes on stored opportunities.
    Updates listing_status (verified, expired, closed, unverified, failed_verification) and last_verified_at.
    """
    from backend.app.services.verifier import verify_url_live, classify_staleness
    items = db.query(Opportunity).filter(
        Opportunity.is_dismissed == False,
        Opportunity.status.in_(["verified", "active", "unverified"])
    ).order_by(Opportunity.last_verified_at.asc()).limit(limit).all()

    stats = {"checked": len(items), "verified": 0, "closed": 0, "expired": 0, "unverified": 0, "failed_verification": 0, "stale": 0}
    status_changed_ids = []
    for item in items:
        target_url = item.application_url or item.original_url
        res = await verify_url_live(target_url)
        new_status = res["listing_status"]
        
        # Check staleness if still marked verified
        if new_status == "verified":
            stale_check = classify_staleness({"last_verified_at": item.last_verified_at, "posted_at": item.posted_at, "status": "verified"})
            if stale_check == "stale":
                new_status = "stale"
                
        if item.status != new_status:
            item.content_version = (item.content_version or 1) + 1
            status_changed_ids.append(item.id)

        item.status = new_status
        item.last_verified_at = datetime.utcnow()
        item.verification_details = res
        stats[new_status] = stats.get(new_status, 0) + 1

    db.commit()
    for opp_id in status_changed_ids:
        snapshot_manager.invalidate_opportunity_snapshots(opportunity_id=opp_id, db=db)

    return {"success": True, "stats": stats}

@router.post("/run-test-scenarios")
async def run_scenarios(db: Session = Depends(get_db)):
    """Execute Test Scenarios A through E and return comprehensive validation metrics."""
    from backend.app.services.scenario_tester import execute_all_scenarios
    return await execute_all_scenarios(db)

@router.get("/recommendations")
def get_recommendations(
    limit_per_section: int = Query(6, ge=1, le=20),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Retrieve 7 curated recommendation sections grounded in Master Candidate Profile:
    - Best Matches (>=75% match score)
    - Recently Posted (last 7-14 days)
    - Remote Opportunities
    - AI/ML Internships
    - Full Stack Internships
    - Closing Soon (within 7 days)
    - Opportunities Based on My Projects (linked to candidate's verified projects)
    """
    return generate_curated_recommendations(db, limit_per_section=limit_per_section, user_id=user_id)

class EvaluateMatchRequest(BaseModel):
    force_refresh: bool = False
    use_ai: bool = True


@router.get("/{id}")
def get_opportunity_detail(
    id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Retrieve full opportunity detail view with AI extraction and match deep dive."""
    opp = db.query(Opportunity).filter(Opportunity.id == id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    if opp.user_id is not None and opp.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this opportunity")
        
    candidate = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    preferences = db.query(UserPreferences).first()
    intel = build_opportunity_intelligence(opp, candidate, preferences)

    # Candidate-scoped matching result lookup
    match_rec = (
        db.query(CandidateOpportunityMatch)
        .filter(
            CandidateOpportunityMatch.user_id == user_id,
            CandidateOpportunityMatch.opportunity_id == opp.id
        )
        .first()
    )

    if match_rec:
        match_analysis = match_rec.match_analysis or {}
        profile_match_score = match_rec.match_score
        eligibility_status = match_rec.eligibility_status
        category_scores = match_analysis.get("category_scores", {})
        category_weights = match_analysis.get("category_weights", {})
        requirement_matches = match_analysis.get("requirement_matches", [])
        skill_gaps = match_analysis.get("skill_gaps", [])
        scoring_explanation = match_analysis.get("scoring_explanation", "")
        match_freshness = {
            "calculated_at": match_analysis.get("calculated_at"),
            "is_stale": match_analysis.get("is_stale", False),
            "is_cached": match_analysis.get("is_cached", False)
        }
    elif opp.user_id is not None and opp.user_id == user_id and opp.match_analysis:
        # Fallback for private opportunities owned by this authenticated candidate
        match_analysis = opp.match_analysis or {}
        profile_match_score = match_analysis.get("profile_match_score", opp.match_score or 0.0)
        eligibility_status = opp.eligibility_status or "eligible"
        category_scores = match_analysis.get("category_scores", {})
        category_weights = match_analysis.get("category_weights", {})
        requirement_matches = match_analysis.get("requirement_matches", [])
        skill_gaps = match_analysis.get("skill_gaps", [])
        scoring_explanation = match_analysis.get("scoring_explanation", "")
        match_freshness = {
            "calculated_at": match_analysis.get("calculated_at"),
            "is_stale": match_analysis.get("is_stale", False),
            "is_cached": match_analysis.get("is_cached", False)
        }
    else:
        # Candidate has not evaluated this opportunity yet: return neutral uncalculated state
        match_analysis = {}
        profile_match_score = 0.0
        eligibility_status = "eligible"
        category_scores = {}
        category_weights = {}
        requirement_matches = []
        skill_gaps = []
        scoring_explanation = "Match analysis has not yet been calculated for the authenticated candidate."
        match_freshness = {
            "calculated_at": None,
            "is_stale": False,
            "is_cached": False
        }

    # Ensure intelligence payload reflects candidate-scoped evaluation
    intel["match_score"] = round(profile_match_score or 0.0)
    if "eligibility_assessment" in intel and isinstance(intel["eligibility_assessment"], dict):
        intel["eligibility_assessment"]["status"] = eligibility_status

    return {
        "id": opp.id,
        "title": opp.title,
        "normalized_title": opp.normalized_title,
        "company_name": opp.company_name,
        "location": opp.location,
        "normalized_location": opp.normalized_location,
        "workplace_type": opp.workplace_type,
        "employment_type": opp.employment_type,
        "description": opp.description,
        "stipend_text": opp.stipend_text,
        "min_stipend": opp.min_stipend,
        "max_stipend": opp.max_stipend,
        "currency": opp.currency,
        "stipend_period": opp.stipend_period,
        "duration_months": opp.duration_months,
        "posted_at": opp.posted_at,
        "deadline_at": opp.deadline_at,
        "discovered_at": opp.discovered_at,
        "last_verified_at": opp.last_verified_at,
        "status": opp.status,
        "original_url": opp.original_url,
        "source_platform": opp.source_platform,
        "source_links": opp.source_links,
        "match_score": profile_match_score,
        "profile_match_score": profile_match_score,
        "category_scores": category_scores,
        "category_weights": category_weights,
        "requirement_matches": requirement_matches,
        "skill_gaps": skill_gaps,
        "scoring_explanation": scoring_explanation,
        "match_freshness": match_freshness,
        "eligibility_status": eligibility_status,
        "extracted_data": opp.extracted_data,
        "match_analysis": match_analysis,
        "is_saved": opp.is_saved,
        "is_dismissed": opp.is_dismissed,
        "is_applied": opp.is_applied,
        "user_notes": opp.user_notes,
        "intelligence": intel,
        "why_it_matches": intel["why_it_matches"],
        "matching_skills": intel["matching_skills"],
        "missing_skills": intel["missing_skills"],
        "eligibility_assessment": intel["eligibility_assessment"],
        "source_reliability": intel["source_reliability"],
        "deadline_info": intel["deadline"]
    }


@router.post("/{id}/evaluate-match", dependencies=[Depends(rate_limited("match"))])
@router.post("/{id}/match")
async def evaluate_opportunity_match(
    id: int,
    req: Optional[EvaluateMatchRequest] = None,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    On-demand deterministic and explainable job-to-candidate matching calculation.
    Enforces candidate ownership and tenant isolation.
    """
    force_refresh = req.force_refresh if req else False
    use_ai = req.use_ai if req else True

    opp = db.query(Opportunity).filter(Opportunity.id == id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    if opp.user_id is not None and opp.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this opportunity")

    candidate = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate profile for user {user_id} not found")

    res = await matching_service.evaluate_match(
        candidate=candidate,
        opportunity=opp,
        db=db,
        force_refresh=force_refresh,
        use_ai=use_ai
    )
    return res

@router.post("/{id}/feedback")
def submit_opportunity_feedback(
    id: int,
    data: OpportunityFeedbackRequest,
    db: Session = Depends(get_db)
):
    """
    Record user feedback on an opportunity (dismiss reasons, thumbs up/down)
    to dynamically adapt future recommendation rankings.
    """
    opp = db.query(Opportunity).filter(Opportunity.id == id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    fb = RecommendationFeedback(
        opportunity_id=id,
        feedback_type=data.feedback_type,
        reason_note=data.reason_note,
        created_at=datetime.utcnow()
    )
    db.add(fb)

    dismissive_types = {"dismiss", "not_relevant", "wrong_location", "skill_mismatch", "low_stipend", "not_interested_company", "already_applied", "thumbs_down"}
    if data.feedback_type in dismissive_types:
        opp.is_dismissed = True

    db.commit()
    return {
        "success": True,
        "id": id,
        "feedback_type": data.feedback_type,
        "is_dismissed": opp.is_dismissed
    }

@router.post("/{id}/save")
def toggle_save_opportunity(id: int, db: Session = Depends(get_db)):
    opp = db.query(Opportunity).filter(Opportunity.id == id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    opp.is_saved = not opp.is_saved
    db.commit()
    return {"id": opp.id, "is_saved": opp.is_saved}

@router.post("/{id}/dismiss")
def dismiss_opportunity(id: int, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    opp = db.query(Opportunity).filter(Opportunity.id == id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    opp.is_dismissed = True
    # Candidate-specific dismissal must NEVER modify global opportunity content_version
    db.commit()
    snapshot_manager.invalidate_candidate_snapshots(user_id=user_id, db=db)
    snapshot_manager.invalidate_opportunity_snapshots(opportunity_id=opp.id, db=db)
    return {"id": opp.id, "is_dismissed": True}

@router.post("/{id}/undismiss")
def undismiss_opportunity(id: int, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    opp = db.query(Opportunity).filter(Opportunity.id == id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    opp.is_dismissed = False
    # Candidate-specific dismissal must NEVER modify global opportunity content_version
    db.commit()
    snapshot_manager.invalidate_candidate_snapshots(user_id=user_id, db=db)
    snapshot_manager.invalidate_opportunity_snapshots(opportunity_id=opp.id, db=db)
    return {"id": opp.id, "is_dismissed": False}


class OpportunityUpdateRequest(BaseModel):
    title: Optional[str] = None
    company_name: Optional[str] = None
    description: Optional[str] = None
    required_skills: Optional[List[str]] = None
    preferred_skills: Optional[List[str]] = None
    normalized_location: Optional[str] = None
    workplace_type: Optional[str] = None
    internship_category: Optional[str] = None
    min_stipend: Optional[float] = None
    max_stipend: Optional[float] = None
    stipend_text: Optional[str] = None
    compensation_type: Optional[str] = None
    status: Optional[str] = None
    deadline_at: Optional[datetime] = None


@router.put("/{id}")
def update_opportunity(
    id: int,
    data: OpportunityUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Updates an opportunity's description, skills, company, location, stipend, or status.
    Increments content_version and invalidates matching snapshots.
    """
    opp = db.query(Opportunity).filter(Opportunity.id == id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    content_changed = False
    for field, val in data.model_dump(exclude_unset=True).items():
        if val is not None and getattr(opp, field, None) != val:
            setattr(opp, field, val)
            content_changed = True

    if content_changed:
        opp.content_version = (opp.content_version or 1) + 1
        opp.updated_at = datetime.utcnow()

    db.commit()
    if content_changed:
        snapshot_manager.invalidate_opportunity_snapshots(opportunity_id=opp.id, db=db)
    db.refresh(opp)
    return opp


@router.delete("/{id}")
def delete_opportunity(
    id: int,
    db: Session = Depends(get_db)
):
    """
    Deletes an opportunity and cleans up candidate matches and distributed ranking snapshots.
    """
    opp = db.query(Opportunity).filter(Opportunity.id == id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    db.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.opportunity_id == id).delete(synchronize_session=False)
    db.delete(opp)
    db.commit()
    snapshot_manager.invalidate_opportunity_snapshots(opportunity_id=id, db=db)
    return {"success": True, "id": id, "detail": "Opportunity deleted successfully"}

