import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Set
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, or_, and_

from backend.app.models.opportunity import Opportunity
from backend.app.models.candidate import CandidateProfile
from backend.app.models.preferences import UserPreferences
from backend.app.models.recommendation_feedback import RecommendationFeedback
from backend.app.services.discovery_search_service import build_opportunity_intelligence

logger = logging.getLogger(__name__)

def get_feedback_adjustments(db: Session) -> Dict[str, Any]:
    """
    Extract user feedback weights to dynamically adjust recommendations:
    - Penalize companies marked 'not_interested_company'
    - Penalize or exclude dismissed opportunities
    """
    feedbacks = db.query(RecommendationFeedback).all()
    penalized_companies = set()
    penalized_categories = set()
    boosted_companies = set()

    for fb in feedbacks:
        fb_type = (fb.feedback_type or "").lower()
        if fb_type == "not_interested_company":
            # Find the company name of that opportunity
            opp = db.query(Opportunity.company_name).filter(Opportunity.id == fb.opportunity_id).first()
            if opp and opp[0]:
                penalized_companies.add(opp[0].lower().strip())
        elif fb_type == "not_relevant":
            opp = db.query(Opportunity.internship_category).filter(Opportunity.id == fb.opportunity_id).first()
            if opp and opp[0]:
                penalized_categories.add(opp[0].lower().strip())
        elif fb_type == "thumbs_up":
            opp = db.query(Opportunity.company_name).filter(Opportunity.id == fb.opportunity_id).first()
            if opp and opp[0]:
                boosted_companies.add(opp[0].lower().strip())

    return {
        "penalized_companies": penalized_companies,
        "penalized_categories": penalized_categories,
        "boosted_companies": boosted_companies
    }

from backend.app.models.candidate_opportunity_match import CandidateOpportunityMatch

def score_with_feedback(opp: Opportunity, adjustments: Dict[str, Any], cand_score: float = 0.0) -> float:
    """Calculate effective match score after applying historical feedback weights."""
    score = cand_score
    comp = (opp.company_name or "").lower().strip()
    cat = (opp.internship_category or "").lower().strip()

    if comp in adjustments["penalized_companies"]:
        score -= 40.0
    if cat in adjustments["penalized_categories"]:
        score -= 15.0
    if comp in adjustments["boosted_companies"]:
        score += 10.0

    # Penalize heavily seen unacted opportunities slightly to prevent stale repetition
    impressions = opp.recommendation_impressions or 0
    if impressions > 5:
        score -= min(15.0, (impressions - 5) * 1.5)

    return max(0.0, min(100.0, score))

def format_recommendation_card(
    opp: Opportunity,
    candidate: CandidateProfile,
    preferences: UserPreferences,
    project_context: Dict[str, Any] = None,
    match_rec: Optional[CandidateOpportunityMatch] = None
) -> Dict[str, Any]:
    """Serialize genuine opportunity into high-density recommendation card."""
    intel = build_opportunity_intelligence(opp, candidate, preferences, match_rec=match_rec)
    
    card = {
        "id": opp.id,
        "title": opp.title,
        "normalized_title": opp.normalized_title,
        "company_name": opp.company_name,
        "location": opp.normalized_location or opp.location,
        "workplace_type": opp.workplace_type,
        "internship_category": opp.internship_category or "software_engineering",
        "stipend_text": opp.stipend_text,
        "min_stipend": opp.min_stipend,
        "max_stipend": opp.max_stipend,
        "duration_months": opp.duration_months,
        "deadline_at": opp.deadline_at.isoformat() if opp.deadline_at else None,
        "posted_at": opp.posted_at.isoformat() if opp.posted_at else None,
        "discovered_at": opp.discovered_at.isoformat() if opp.discovered_at else None,
        "last_verified_at": opp.last_verified_at.isoformat() if opp.last_verified_at else None,
        "original_url": opp.original_url,
        "application_url": opp.application_url or opp.original_url,
        "source_platform": opp.source_platform,
        "match_score": intel["match_score"],
        "eligibility_status": match_rec.eligibility_status if match_rec else opp.eligibility_status,
        "top_skills": (opp.extracted_data or {}).get("mandatory_technical_skills", [])[:5],
        "is_saved": opp.is_saved,
        "is_dismissed": opp.is_dismissed,
        "is_applied": opp.is_applied,
        "intelligence": intel,
        "why_it_matches": intel["why_it_matches"],
        "matching_skills": intel["matching_skills"],
        "missing_skills": intel["missing_skills"],
        "eligibility_assessment": intel["eligibility_assessment"],
        "source_reliability": intel["source_reliability"],
        "deadline_info": intel["deadline"],
        "posting_and_discovery_dates": intel["posting_and_discovery_dates"]
    }
    
    if project_context:
        card["based_on_project"] = project_context
        
    return card

def generate_curated_recommendations(
    db: Session,
    limit_per_section: int = 6,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Generate 7 curated, non-repetitive recommendation sections grounded in real database records:
    1. Best Matches (Match Score >= 75%)
    2. Recently Posted (Last 7-14 days)
    3. Remote Opportunities
    4. AI/ML Internships
    5. Full Stack Internships
    6. Closing Soon (Deadlines <= 7 days)
    7. Opportunities Based on My Projects
    """
    if user_id is not None:
        candidate = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    else:
        candidate = db.query(CandidateProfile).first()
    preferences = db.query(UserPreferences).first()
    adjustments = get_feedback_adjustments(db)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Pre-fetch candidate-scoped matches
    cand_matches = {}
    effective_uid = user_id or (candidate.user_id if candidate else None)
    if effective_uid is not None:
        matches = db.query(CandidateOpportunityMatch).filter(CandidateOpportunityMatch.user_id == effective_uid).all()
        cand_matches = {m.opportunity_id: m for m in matches}

    def get_cand_score(o: Opportunity) -> float:
        m = cand_matches.get(o.id)
        if m:
            return m.match_score
        if candidate and o.user_id is not None and o.user_id == candidate.user_id:
            return o.match_score or 0.0
        return 0.0

    # Base pool: verified, un-dismissed, un-applied internships
    base_query = db.query(Opportunity).filter(
        Opportunity.employment_type == "internship",
        Opportunity.is_dismissed == False,
        Opportunity.is_applied == False,
        Opportunity.status.in_(["verified", "active", "possibly_expired", "unverified"]),
        Opportunity.eligibility_status != "disqualified"
    )

    all_eligible = base_query.all()
    # Sort with feedback adjustments using candidate-scoped score
    all_eligible.sort(key=lambda o: score_with_feedback(o, adjustments, cand_score=get_cand_score(o)), reverse=True)

    seen_ids: Set[int] = set()

    # Section 1: Best Matches
    best_matches = []
    for opp in all_eligible:
        score_val = get_cand_score(opp)
        if opp.id not in seen_ids and score_val >= 70.0:
            best_matches.append(format_recommendation_card(opp, candidate, preferences, match_rec=cand_matches.get(opp.id)))
            seen_ids.add(opp.id)
            if len(best_matches) >= limit_per_section:
                break

    # Section 2: Recently Posted
    recently_posted = []
    recent_candidates = [
        o for o in all_eligible 
        if o.posted_at and o.posted_at >= now - timedelta(days=14)
    ]
    recent_candidates.sort(key=lambda o: (o.posted_at or now), reverse=True)
    for opp in recent_candidates:
        if opp.id not in seen_ids:
            recently_posted.append(format_recommendation_card(opp, candidate, preferences, match_rec=cand_matches.get(opp.id)))
            seen_ids.add(opp.id)
            if len(recently_posted) >= limit_per_section:
                break
    # Fallback if fewer than 3 were found
    if len(recently_posted) < 3:
        for opp in all_eligible:
            if opp.id not in seen_ids:
                recently_posted.append(format_recommendation_card(opp, candidate, preferences, match_rec=cand_matches.get(opp.id)))
                seen_ids.add(opp.id)
                if len(recently_posted) >= limit_per_section:
                    break

    # Section 3: Remote Opportunities
    remote_opps = []
    remote_candidates = [
        o for o in all_eligible 
        if o.workplace_type == "remote" or "remote" in (o.location or "").lower()
    ]
    for opp in remote_candidates:
        if opp.id not in seen_ids:
            remote_opps.append(format_recommendation_card(opp, candidate, preferences, match_rec=cand_matches.get(opp.id)))
            seen_ids.add(opp.id)
            if len(remote_opps) >= limit_per_section:
                break

    # Section 4: AI/ML Internships
    aiml_opps = []
    aiml_keywords = ["ai", "machine learning", "ml", "nlp", "deep learning", "pytorch", "tensorflow", "data science", "generative ai"]
    for opp in all_eligible:
        if opp.id not in seen_ids:
            text = f"{opp.title} {opp.description} {opp.internship_category}".lower()
            if any(kw in text for kw in aiml_keywords) or opp.internship_category in ["ai_ml", "data_science"]:
                aiml_opps.append(format_recommendation_card(opp, candidate, preferences, match_rec=cand_matches.get(opp.id)))
                seen_ids.add(opp.id)
                if len(aiml_opps) >= limit_per_section:
                    break

    # Section 5: Full Stack Internships
    fullstack_opps = []
    fs_keywords = ["full stack", "fullstack", "frontend", "backend", "react", "fastapi", "django", "node", "express", "web developer"]
    for opp in all_eligible:
        if opp.id not in seen_ids:
            text = f"{opp.title} {opp.description} {opp.internship_category}".lower()
            if any(kw in text for kw in fs_keywords) or opp.internship_category in ["fullstack", "software_engineering", "backend", "frontend"]:
                fullstack_opps.append(format_recommendation_card(opp, candidate, preferences, match_rec=cand_matches.get(opp.id)))
                seen_ids.add(opp.id)
                if len(fullstack_opps) >= limit_per_section:
                    break

    # Section 6: Closing Soon
    closing_soon = []
    expiring_candidates = [
        o for o in all_eligible 
        if o.deadline_at and o.deadline_at >= now and o.deadline_at <= now + timedelta(days=10)
    ]
    expiring_candidates.sort(key=lambda o: o.deadline_at)
    for opp in expiring_candidates:
        if opp.id not in seen_ids:
            closing_soon.append(format_recommendation_card(opp, candidate, preferences, match_rec=cand_matches.get(opp.id)))
            seen_ids.add(opp.id)
            if len(closing_soon) >= limit_per_section:
                break

    # Section 7: Opportunities Based on My Projects
    project_based_opps = []
    candidate_projects = candidate.projects if candidate and candidate.projects else []
    
    for proj in candidate_projects:
        proj_title = proj.get("title", "")
        proj_tech = [t.lower() for t in proj.get("tech_stack", [])]
        if not proj_tech:
            continue

        # Find best matching real opportunity for this project
        best_opp = None
        best_overlap = []
        best_score = -1.0

        for opp in all_eligible:
            # Note: allow project matching even if in seen_ids if it's the strongest match
            opp_text = f"{opp.title} {opp.description} {' '.join(opp.required_skills or [])}".lower()
            overlap = [t for t in proj_tech if t in opp_text]
            opp_cand_score = get_cand_score(opp)
            if len(overlap) > len(best_overlap) or (len(overlap) == len(best_overlap) and opp_cand_score > best_score):
                best_opp = opp
                best_overlap = overlap
                best_score = opp_cand_score

        if best_opp and best_overlap and len(best_overlap) >= 1:
            context = {
                "project_title": proj_title,
                "matching_tech": [t.capitalize() for t in best_overlap],
                "relevance_reason": f"Your project '{proj_title}' demonstrates verified competency in {', '.join([t.capitalize() for t in best_overlap[:3]])} required for this role."
            }
            # Only add if not already added to project_based_opps
            if not any(p["id"] == best_opp.id for p in project_based_opps):
                project_based_opps.append(format_recommendation_card(best_opp, candidate, preferences, context, match_rec=cand_matches.get(best_opp.id)))
                if len(project_based_opps) >= limit_per_section:
                    break

    # Increment recommendation impression counters in background
    all_recommended_ids = [c["id"] for c in best_matches + recently_posted + remote_opps + aiml_opps + fullstack_opps + closing_soon + project_based_opps]
    if all_recommended_ids:
        try:
            db.query(Opportunity).filter(Opportunity.id.in_(all_recommended_ids)).update(
                {Opportunity.recommendation_impressions: Opportunity.recommendation_impressions + 1},
                synchronize_session=False
            )
            db.commit()
        except Exception as e:
            logger.warning(f"Could not update impression counts: {e}")
            db.rollback()

    return {
        "best_matches": best_matches,
        "recently_posted": recently_posted,
        "remote_opportunities": remote_opps,
        "aiml_internships": aiml_opps,
        "fullstack_internships": fullstack_opps,
        "closing_soon": closing_soon,
        "based_on_projects": project_based_opps,
        "meta": {
            "total_recommended": len(all_recommended_ids),
            "generated_at": now.isoformat(),
            "candidate_name": candidate.name if candidate else "Candidate",
            "active_feedback_penalties": len(adjustments["penalized_companies"]) + len(adjustments["penalized_categories"])
        }
    }
