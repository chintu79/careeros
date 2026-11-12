import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, asc, func, case, literal

from backend.app.models.opportunity import Opportunity
from backend.app.models.candidate import CandidateProfile
from backend.app.models.candidate_opportunity_match import CandidateOpportunityMatch
from backend.app.models.preferences import UserPreferences
from backend.app.models.search_history import SearchHistory
from backend.app.models.discovery_ranking_snapshot import DiscoveryRankingSnapshot
import json
import hashlib
from fastapi import HTTPException, status
from backend.app.ai.ollama_client import ollama_client
from backend.app.services.intelligence_cache import embedding_cache, ranking_snapshot_cache
from backend.app.services.discovery_snapshot_manager import snapshot_manager

logger = logging.getLogger(__name__)

RANKING_CONFIG_VERSION = "2.2.0"


class PaginationSessionExpiredException(HTTPException):
    """
    Raised when an active pagination session token (snapshot_id) has expired or is invalid on skip > 0.
    Informs client to restart discovery search from page 1.
    """
    def __init__(self, detail: str = "Pagination session has expired or is invalid. Please restart search from page 1."):
        super().__init__(
            status_code=status.HTTP_410_GONE,
            detail=detail,
            headers={"X-Restart-Required": "true"}
        )


PLATFORM_RELIABILITY_MAP = {
    "greenhouse": {"score": 98, "tier": "High", "badge": "Direct ATS Integration"},
    "lever": {"score": 98, "tier": "High", "badge": "Direct ATS Integration"},
    "ashby": {"score": 98, "tier": "High", "badge": "Direct ATS Integration"},
    "smartrecruiters": {"score": 95, "tier": "High", "badge": "Verified ATS Feed"},
    "internshala": {"score": 95, "tier": "High", "badge": "Internshala Official Source"},
    "linkedin": {"score": 92, "tier": "High", "badge": "LinkedIn Verified"},
    "remotive": {"score": 90, "tier": "High", "badge": "Curated Remote Feed"},
    "remoteok": {"score": 88, "tier": "Medium", "badge": "Curated Feed"},
    "rss": {"score": 85, "tier": "Medium", "badge": "Verified RSS Feed"}
}

def compute_source_reliability(source_platform: str, quality_score: float = 0.0) -> Dict[str, Any]:
    """Calculate transparent source reliability score and badge."""
    plat_key = (source_platform or "unknown").lower().strip()
    base = PLATFORM_RELIABILITY_MAP.get(plat_key, {"score": 80, "tier": "Standard", "badge": "Verified Aggregator"})
    
    score = base["score"]
    if quality_score and quality_score > 0:
        # Blend quality score (0-100)
        score = round((score * 0.7) + (quality_score * 0.3))
    
    return {
        "score": min(100, max(50, score)),
        "tier": base["tier"],
        "badge": base["badge"],
        "platform": source_platform or "Direct"
    }

def format_relative_time(dt: Optional[datetime]) -> str:
    """Format human readable relative duration."""
    if not dt:
        return "Recently"
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    dt_clean = dt.replace(tzinfo=None) if dt else now_utc
    diff = now_utc - dt_clean
    seconds = diff.total_seconds()
    if seconds < 0:
        return "Just now"
    if seconds < 3600:
        mins = max(1, int(seconds // 60))
        return f"{mins}m ago"
    if seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours}h ago"
    days = int(seconds // 86400)
    if days == 1:
        return "1d ago"
    if days < 30:
        return f"{days}d ago"
    return dt.strftime("%b %d, %Y")

def build_opportunity_intelligence(
    opp: Opportunity,
    candidate: Optional[CandidateProfile] = None,
    preferences: Optional[UserPreferences] = None,
    match_rec: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Construct complete, explainable opportunity intelligence:
    - Match score (candidate-scoped)
    - Why it matches (bullets)
    - Matching skills
    - Missing skills
    - Structured ranking reasons
    - Eligibility assessment
    - Application deadline countdown
    - Source reliability
    - Posting and discovery dates
    - Last verification timestamp
    """
    cand_skills = {}
    if candidate and candidate.skills:
        for s in candidate.skills:
            if isinstance(s, dict):
                cand_skills[s.get("name", "").lower().strip()] = s.get("name", "")
            elif isinstance(s, str):
                cand_skills[s.lower().strip()] = s

    extracted = opp.extracted_data or {}
    
    # Candidate-scoped match intelligence
    is_stale = False
    if match_rec:
        match_analysis = match_rec.match_analysis or {}
        score_val = match_rec.match_score
        eligibility_status = match_rec.eligibility_status or "eligible"
        is_evaluated = True
        is_stale = bool(match_analysis.get("is_stale", False)) or (getattr(match_rec, "engine_version", None) != "2.0.0")
    elif candidate and opp.user_id is not None and opp.user_id == candidate.user_id and opp.match_analysis:
        match_analysis = opp.match_analysis or {}
        score_val = opp.match_score or 0.0
        eligibility_status = opp.eligibility_status or "eligible"
        is_evaluated = True
        is_stale = bool(match_analysis.get("is_stale", False)) or (match_analysis.get("engine_version") != "2.0.0")
    else:
        match_analysis = {}
        score_val = 0.0
        eligibility_status = opp.eligibility_status or "eligible"
        is_evaluated = False
        is_stale = False
    
    # 1. Matching & Missing Skills
    mandatory = extracted.get("mandatory_technical_skills") or opp.required_skills or []
    preferred = extracted.get("preferred_skills") or opp.preferred_skills or []
    
    matching_skills = []
    missing_skills = []
    
    for req in mandatory:
        req_clean = req.strip()
        req_lower = req_clean.lower()
        if req_lower in cand_skills:
            matching_skills.append(cand_skills[req_lower])
        elif any(req_lower in cs or cs in req_lower for cs in cand_skills):
            matched_name = next(cand_skills[cs] for cs in cand_skills if req_lower in cs or cs in req_lower)
            matching_skills.append(matched_name)
        else:
            missing_skills.append(req_clean)

    # 2. Why it matches
    why_it_matches = []
    if matching_skills:
        top_m = matching_skills[:4]
        why_it_matches.append(f"Technical Skills Alignment: Matches verified competencies in {', '.join(top_m)}.")
    
    # Check project overlap
    if candidate and candidate.projects:
        for proj in candidate.projects:
            p_tech = [t.lower() for t in proj.get("tech_stack", [])]
            overlap = [t for t in p_tech if t in [m.lower() for m in mandatory + preferred]]
            if overlap:
                why_it_matches.append(
                    f"Portfolio Relevance: Verified project '{proj.get('title')}' demonstrates production use of {', '.join(overlap[:3])}."
                )
                break
                
    # Workplace & Location match
    cand_locs = [l.lower() for l in (candidate.preferred_locations if candidate else [])]
    job_loc = (opp.normalized_location or opp.location or "").lower()
    is_remote = opp.workplace_type == "remote" or "remote" in job_loc
    if is_remote:
        why_it_matches.append("Schedule Compatibility: Remote internship format offers flexible asynchronous workflow.")
    elif any(cl in job_loc for cl in cand_locs if cl != "remote"):
        why_it_matches.append(f"Geographic Preference: Located in preferred candidate market ({opp.normalized_location or opp.location}).")

    if not why_it_matches:
        why_it_matches.append(f"Foundational Alignment: Entry-level {opp.internship_category or 'software'} engineering role matching academic background.")

    # 3. Eligibility Assessment
    disqualifying = match_analysis.get("disqualifying_reasons", [])
    eligibility_summary = "Eligible: Verified student status and India work authorization satisfied."
    if eligibility_status == "disqualified":
        eligibility_summary = f"Disqualified: {'; '.join(disqualifying) if disqualifying else 'Restricted geographical jurisdiction'}"
    elif eligibility_status == "flagged":
        eligibility_summary = f"Review Notice: {'; '.join(disqualifying) if disqualifying else 'Cohort or stipend preference discrepancy'}"

    # 4. Deadline Countdown
    deadline_info = {
        "deadline_at": opp.deadline_at.isoformat() if opp.deadline_at else None,
        "deadline_formatted": opp.deadline_at.strftime("%b %d, %Y") if opp.deadline_at else "Open / Rolling",
        "days_left": None,
        "urgency": "normal"
    }
    if opp.deadline_at:
        now_dt = datetime.now(timezone.utc).replace(tzinfo=None)
        opp_dl = opp.deadline_at.replace(tzinfo=None)
        diff_days = (opp_dl - now_dt).total_seconds() / 86400.0
        days_left = max(0, int(diff_days))
        deadline_info["days_left"] = days_left
        if diff_days <= 1:
            deadline_info["urgency"] = "urgent"
            deadline_info["deadline_formatted"] = "Closing Today!"
        elif diff_days <= 3:
            deadline_info["urgency"] = "urgent"
            deadline_info["deadline_formatted"] = f"{days_left}d left"
        elif diff_days <= 7:
            deadline_info["urgency"] = "soon"
            deadline_info["deadline_formatted"] = f"{days_left}d left"

    # 5. Dates & Verification
    reliability = compute_source_reliability(opp.source_platform, opp.quality_score or 0.0)
    
    if not is_evaluated:
        evaluation_state = "not_evaluated"
        primary_factor = "catalog_default"
    elif is_stale:
        evaluation_state = "stale"
        primary_factor = "stale_evaluation"
    elif (score_val or 0.0) >= 70.0:
        evaluation_state = "evaluated_high"
        primary_factor = "evaluated_candidate_match"
    elif (score_val or 0.0) >= 50.0:
        evaluation_state = "evaluated_moderate"
        primary_factor = "evaluated_candidate_match"
    else:
        evaluation_state = "evaluated_low"
        primary_factor = "evaluated_candidate_match"

    ranking_reasons = {
        "primary_factor": primary_factor,
        "evaluation_state": evaluation_state,
        "match_score": round(score_val or 0.0, 1),
        "is_evaluated": is_evaluated,
        "is_stale": is_stale,
        "eligibility_status": eligibility_status,
        "highlights": why_it_matches
    }

    return {
        "match_score": round(score_val or 0.0),
        "why_it_matches": why_it_matches,
        "matching_skills": list(dict.fromkeys(matching_skills)),
        "missing_skills": list(dict.fromkeys(missing_skills)),
        "ranking_reasons": ranking_reasons,
        "eligibility_assessment": {
            "status": eligibility_status,
            "summary": eligibility_summary,
            "disqualifying_reasons": disqualifying
        },
        "deadline": deadline_info,
        "source_reliability": reliability,
        "posting_and_discovery_dates": {
            "posted_at": opp.posted_at.isoformat() if opp.posted_at else None,
            "posted_relative": format_relative_time(opp.posted_at),
            "discovered_at": opp.discovered_at.isoformat() if opp.discovered_at else None,
            "discovered_relative": format_relative_time(opp.discovered_at)
        },
        "last_verification": {
            "last_verified_at": opp.last_verified_at.isoformat() if opp.last_verified_at else None,
            "verified_relative": format_relative_time(opp.last_verified_at),
            "status": opp.status or "verified"
        },
        "match_analysis": match_analysis,
        "category_scores": match_analysis.get("category_scores") or match_analysis.get("score_breakdown") or {},
        "category_weights": match_analysis.get("category_weights") or {},
        "skill_gaps": match_analysis.get("skill_gaps") or [],
        "requirement_matches": match_analysis.get("requirement_matches") or [],
        "scoring_explanation": match_analysis.get("scoring_explanation") or "",
        "match_freshness": {
            "calculated_at": match_analysis.get("calculated_at"),
            "is_stale": is_stale,
            "is_cached": match_analysis.get("is_cached", False)
        }
    }


def compute_search_signature(
    tab: str = "recommended",
    search_mode: str = "keyword",
    query_str: Optional[str] = None,
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
    posted_days: Optional[int] = None,
    source_platform: Optional[str] = None,
    status: Optional[str] = None,
    eligibility_status: Optional[str] = None,
    min_score: Optional[float] = None,
    sort_by: str = "match_score",
    sort_order: str = "desc",
    user_id: Optional[int] = None,
    candidate_evidence_version: Optional[str] = None,
    employment_type: Optional[str] = "internship",
    page_size: Optional[int] = 25,
    matching_engine_version: str = "2.0.0",
    ranking_config_version: str = RANKING_CONFIG_VERSION
) -> str:
    """
    Canonical SHA-256 signature accounting for all 25 search, candidate evidence, and engine parameters.
    Uses canonical JSON serialization (sorted keys, compact delimiters) to guarantee deterministic cache keys.
    """
    sig_payload = {
        "auth_user_id": user_id,
        "candidate_evidence_version": str(candidate_evidence_version or ""),
        "category": (category or "").strip().lower(),
        "company": (company or "").strip().lower(),
        "compensation_type": (compensation_type or "").strip().lower(),
        "duration_months": duration_months,
        "eligibility_status": (eligibility_status or "").strip().lower(),
        "employment_type": (employment_type or "internship").strip().lower(),
        "internship_type": (internship_type or "").strip().lower(),
        "location": (location or "").strip().lower(),
        "matching_engine_version": str(matching_engine_version),
        "min_score": float(min_score) if min_score is not None else None,
        "min_stipend": float(min_stipend) if min_stipend is not None else None,
        "page_size": page_size,
        "posted_days": posted_days,
        "query_str": (query_str or "").strip().lower(),
        "ranking_config_version": str(ranking_config_version),
        "search_mode": (search_mode or "keyword").strip().lower(),
        "skills": (skills or "").strip().lower(),
        "sort_by": (sort_by or "match_score").strip().lower(),
        "sort_order": (sort_order or "desc").strip().lower(),
        "source_platform": (source_platform or "").strip().lower(),
        "status": (status or "").strip().lower(),
        "tab": (tab or "recommended").strip().lower(),
        "work_mode": (work_mode or "").strip().lower(),
        "workplace_type": (workplace_type or "").strip().lower(),
    }
    canonical_json = json.dumps(sig_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


async def execute_intelligent_discovery_search(
    db: Session,
    query_str: Optional[str] = None,
    search_mode: str = "hybrid",
    tab: str = "recommended",
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
    posted_days: Optional[int] = None,
    source_platform: Optional[str] = None,
    status: Optional[str] = None,
    eligibility_status: Optional[str] = None,
    min_score: Optional[float] = None,
    sort_by: str = "match_score",
    sort_order: str = "desc",
    skip: int = 0,
    limit: int = 25,
    cursor: Optional[int] = None,
    user_id: Optional[int] = None,
    snapshot_id: Optional[str] = None,
    return_snapshot_id: bool = False,
    return_cursor: bool = False
) -> Any:
    """
    Execute multi-mode intelligent discovery search:
    - semantic: pgvector cosine distance using BGE-M3
    - keyword: multi-field ILIKE
    - skill: targeted skill filtering
    - company: specific company match
    - location: geographic filter
    - hybrid: vector similarity blended with keyword and candidate matching
    - candidate-aware: strictly isolated candidate-specific scoring and ranking
    """
    if user_id is not None:
        candidate = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    else:
        candidate = None
    preferences = db.query(UserPreferences).first()

    # Build candidate-scoped match expressions
    cand_match_score = func.coalesce(
        CandidateOpportunityMatch.match_score,
        case((Opportunity.user_id == user_id, Opportunity.match_score), else_=None) if user_id is not None else None
    )

    effective_cand_score = func.coalesce(cand_match_score, 0.0).label("effective_cand_score")

    rank_tier = case(
        (cand_match_score >= 50.0, 2),
        (cand_match_score.is_(None), 1),
        else_=0
    ).label("rank_tier")

    effective_eligibility = func.coalesce(
        CandidateOpportunityMatch.eligibility_status,
        Opportunity.eligibility_status,
        "eligible"
    ).label("effective_eligibility")

    join_condition = and_(
        CandidateOpportunityMatch.opportunity_id == Opportunity.id,
        CandidateOpportunityMatch.user_id == user_id
    ) if user_id is not None else literal(False)

    query = db.query(
        Opportunity,
        CandidateOpportunityMatch
    ).outerjoin(
        CandidateOpportunityMatch,
        join_condition
    ).filter(Opportunity.employment_type == "internship")
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Tab handling
    if tab == "recommended":
        query = query.filter(
            Opportunity.is_dismissed == False,
            Opportunity.status.in_(["verified", "active", "possibly_expired", "unverified"]),
            effective_eligibility != "disqualified"
        )
    elif tab == "latest":
        query = query.filter(Opportunity.is_dismissed == False)
    elif tab == "saved":
        query = query.filter(Opportunity.is_saved == True, Opportunity.is_dismissed == False)
    elif tab == "expiring":
        query = query.filter(
            Opportunity.is_dismissed == False,
            Opportunity.deadline_at != None,
            Opportunity.deadline_at >= now,
            Opportunity.deadline_at <= now + timedelta(days=7)
        )
    elif tab == "applied":
        query = query.filter(Opportunity.is_applied == True)
    elif tab == "dismissed":
        query = query.filter(Opportunity.is_dismissed == True)

    clean_query = (query_str or "").strip()
    vector_ordered_ids = []

    # Semantic or Hybrid Vector Search via Ollama BGE-M3
    if clean_query and search_mode in ("semantic", "hybrid"):
        try:
            cache_key = f"embed_search_v2:{clean_query.lower()}:100"
            query_embedding = embedding_cache.get(cache_key)
            if not query_embedding:
                query_embedding = await ollama_client.get_embedding(clean_query)
                if query_embedding:
                    embedding_cache.set(cache_key, query_embedding, ttl=3600)

            if query_embedding and len(query_embedding) == 1024:
                # Query nearest vectors in postgres
                nearest = db.query(Opportunity.id).filter(
                    Opportunity.embedding.isnot(None),
                    Opportunity.is_dismissed == (tab == "dismissed")
                ).order_by(
                    Opportunity.embedding.cosine_distance(query_embedding)
                ).limit(100).all()
                vector_ordered_ids = [n[0] for n in nearest]
        except Exception as e:
            logger.warning(f"Vector search failed in discovery, falling back to keyword: {e}")

    # Mode-specific filtering
    if clean_query:
        if search_mode == "semantic" and vector_ordered_ids:
            query = query.filter(Opportunity.id.in_(vector_ordered_ids))
        elif search_mode == "company":
            query = query.filter(Opportunity.company_name.ilike(f"%{clean_query}%"))
        elif search_mode == "location":
            query = query.filter(
                or_(
                    Opportunity.location.ilike(f"%{clean_query}%"),
                    Opportunity.normalized_location.ilike(f"%{clean_query}%"),
                    Opportunity.workplace_type.ilike(f"%{clean_query}%")
                )
            )
        elif search_mode == "skill":
            skill_pattern = f"%{clean_query}%"
            query = query.filter(
                or_(
                    Opportunity.description.ilike(skill_pattern),
                    Opportunity.title.ilike(skill_pattern)
                )
            )
        elif search_mode == "hybrid" and vector_ordered_ids:
            # Hybrid: include vector nearest OR keyword matches
            term = f"%{clean_query}%"
            query = query.filter(
                or_(
                    Opportunity.id.in_(vector_ordered_ids),
                    Opportunity.title.ilike(term),
                    Opportunity.company_name.ilike(term),
                    Opportunity.description.ilike(term),
                    Opportunity.internship_category.ilike(term)
                )
            )
        else: # keyword or default fallback
            term = f"%{clean_query}%"
            query = query.filter(
                or_(
                    Opportunity.title.ilike(term),
                    Opportunity.company_name.ilike(term),
                    Opportunity.description.ilike(term),
                    Opportunity.normalized_location.ilike(term),
                    Opportunity.internship_category.ilike(term)
                )
            )

    # Standard faceted filters
    if category:
        query = query.filter(
            or_(
                Opportunity.internship_category.ilike(f"%{category}%"),
                Opportunity.normalized_title.ilike(f"%{category}%")
            )
        )
    if company and search_mode != "company":
        query = query.filter(Opportunity.company_name.ilike(f"%{company}%"))
    if location and search_mode != "location":
        query = query.filter(
            or_(
                Opportunity.location.ilike(f"%{location}%"),
                Opportunity.normalized_location.ilike(f"%{location}%")
            )
        )
    if workplace_type:
        query = query.filter(Opportunity.workplace_type == workplace_type)
    if internship_type:
        query = query.filter(Opportunity.internship_type == internship_type)
    if work_mode:
        query = query.filter(Opportunity.work_mode == work_mode)
    if min_stipend is not None:
        query = query.filter(Opportunity.min_stipend >= min_stipend)
    if compensation_type and compensation_type != "all":
        query = query.filter(Opportunity.compensation_type == compensation_type)
    if duration_months is not None:
        query = query.filter(Opportunity.duration_months == duration_months)
    if posted_days is not None and posted_days > 0:
        query = query.filter(
            Opportunity.posted_at != None,
            Opportunity.posted_at >= now - timedelta(days=posted_days)
        )
    if source_platform:
        query = query.filter(Opportunity.source_platform.ilike(source_platform))
    if status and status != "all":
        query = query.filter(Opportunity.status == status)
    if eligibility_status:
        query = query.filter(effective_eligibility == eligibility_status)
    if min_score is not None:
        query = query.filter(effective_cand_score >= min_score)
    if skills and skills.strip():
        for st in [s.strip().lower() for s in skills.split(",") if s.strip()]:
            pat = f"%{st}%"
            query = query.filter(or_(Opportunity.description.ilike(pat), Opportunity.title.ilike(pat)))

    # Sorting
    if search_mode == "semantic" and vector_ordered_ids:
        # Prioritize vector order if specifically in semantic mode
        pass
    elif sort_by == "match_score":
        if sort_order == "desc":
            query = query.order_by(
                desc(rank_tier),
                desc(cand_match_score).nulls_last(),
                desc(Opportunity.id)
            )
        else:
            query = query.order_by(
                asc(rank_tier),
                asc(cand_match_score).nulls_first(),
                asc(Opportunity.id)
            )
    else:
        sort_column = getattr(Opportunity, sort_by, Opportunity.id)
        if sort_order == "desc":
            query = query.order_by(desc(sort_column).nulls_last(), desc(Opportunity.id))
        else:
            query = query.order_by(asc(sort_column).nulls_last(), asc(Opportunity.id))

    cand_evidence_version = None
    if candidate:
        try:
            from backend.app.services.matching.candidate_evidence import build_unified_candidate_evidence
            cand_evidence_hash = build_unified_candidate_evidence(candidate).content_hash
            cand_evidence_version = f"{cand_evidence_hash}:{getattr(candidate, 'evidence_version', 1)}"
        except Exception:
            cand_evidence_version = f"v{getattr(candidate, 'evidence_version', 1)}"

    sig = compute_search_signature(
        tab=tab, search_mode=search_mode, query_str=query_str, category=category,
        company=company, location=location, workplace_type=workplace_type,
        internship_type=internship_type, work_mode=work_mode, employment_type=internship_type or "internship",
        min_stipend=min_stipend, compensation_type=compensation_type, skills=skills,
        duration_months=duration_months, posted_days=posted_days, source_platform=source_platform,
        status=status, eligibility_status=eligibility_status, min_score=min_score,
        sort_by=sort_by, sort_order=sort_order, user_id=user_id,
        candidate_evidence_version=cand_evidence_version, page_size=limit
    )
    snapshot_key = f"snap:{user_id}:{sig}" if user_id is not None else None

    from backend.app.services.matching.service import matching_service, MATCHING_ENGINE_VERSION
    max_eval_per_request = 15

    active_snapshot_id = snapshot_id
    cached_snapshot = None
    if snapshot_id:
        cached_snapshot = snapshot_manager.get_snapshot_by_id(snapshot_id, db, user_id=user_id)
    elif snapshot_key:
        cached_snapshot = snapshot_manager.get_snapshot(snapshot_key, db)

    effective_offset = cursor if cursor is not None else skip

    # Active pagination contract (Phase 1 & 2):
    # Subsequent pages (effective_offset > 0) MUST read from an established snapshot.
    # If snapshot is missing, invalidated, expired, or belongs to another user, reject with HTTP 410 Gone.
    if effective_offset > 0 and not cached_snapshot:
        raise PaginationSessionExpiredException()

    next_cursor = None
    has_more = False

    if cached_snapshot:
        snapshot_ids, total = cached_snapshot
        if not active_snapshot_id and snapshot_key:
            row = db.query(DiscoveryRankingSnapshot).filter(
                DiscoveryRankingSnapshot.snapshot_key == snapshot_key,
                DiscoveryRankingSnapshot.expires_at > datetime.now(timezone.utc).replace(tzinfo=None)
            ).first()
            if row and row.snapshot_id:
                active_snapshot_id = row.snapshot_id

        # Scan-fill algorithm (Iteration 2.4):
        # Starting from effective_offset, scan snapshot_ids forward to collect up to 'limit'
        # display-eligible opportunities (skipping closed, deleted, and dismissed items).
        page_items = []
        scan_idx = effective_offset
        chunk_size = max(limit * 2, 25)

        while len(page_items) < limit and scan_idx < len(snapshot_ids):
            chunk_ids = snapshot_ids[scan_idx : scan_idx + chunk_size]
            if not chunk_ids:
                break

            pairs = db.query(
                Opportunity,
                CandidateOpportunityMatch
            ).outerjoin(
                CandidateOpportunityMatch,
                and_(
                    CandidateOpportunityMatch.opportunity_id == Opportunity.id,
                    CandidateOpportunityMatch.user_id == user_id
                )
            ).filter(Opportunity.id.in_(chunk_ids)).all()

            pair_map = {opp.id: (opp, match_rec) for opp, match_rec in pairs}

            for pid in chunk_ids:
                scan_idx += 1
                if pid in pair_map:
                    opp, match_rec = pair_map[pid]
                    if tab == "recommended":
                        is_eligible = (
                            opp is not None and
                            not opp.is_dismissed and
                            opp.status in ["verified", "active", "possibly_expired", "unverified"]
                        )
                    elif tab == "latest":
                        is_eligible = opp is not None and not opp.is_dismissed
                    elif tab == "saved":
                        is_eligible = opp is not None and opp.is_saved and not opp.is_dismissed
                    elif tab == "dismissed":
                        is_eligible = opp is not None and opp.is_dismissed
                    elif tab == "applied":
                        is_eligible = opp is not None and opp.is_applied
                    else:
                        is_eligible = (
                            opp is not None and
                            not opp.is_dismissed and
                            opp.status in ["verified", "active", "possibly_expired", "unverified"]
                        )
                    if status and status != "all" and opp is not None:
                        is_eligible = is_eligible and (opp.status == status)
                    if is_eligible:
                        page_items.append((opp, match_rec))
                        if len(page_items) == limit:
                            break

        if scan_idx < len(snapshot_ids):
            next_cursor = scan_idx
            has_more = True
        else:
            next_cursor = None
            has_more = False

        if candidate and user_id and page_items:
            unevaluated_pairs = [
                (opp, match_rec) for opp, match_rec in page_items
                if match_rec is None or match_rec.engine_version != MATCHING_ENGINE_VERSION
            ]
            if unevaluated_pairs:
                opps_to_evaluate = [p[0] for p in unevaluated_pairs[:max_eval_per_request]]
                try:
                    batch_results = await matching_service.evaluate_matches_batch(
                        candidate=candidate,
                        opportunities=opps_to_evaluate,
                        db=db,
                        force_refresh=False,
                        use_ai=False
                    )
                    updated_items = []
                    for opp, rec in page_items:
                        if opp.id in batch_results:
                            _, new_rec = batch_results[opp.id]
                            updated_items.append((opp, new_rec))
                        else:
                            updated_items.append((opp, rec))
                    page_items = updated_items
                except Exception as e:
                    logger.warning(f"Batch on-demand evaluation failed on paginated page: {e}")

        items = page_items

    else:
        total = query.with_entities(func.count(Opportunity.id)).order_by(None).scalar() or 0

        # Bounded candidate pool retrieval:
        # Retrieve a top pool of up to min(max(limit * 2, 50), 100)
        # to evaluate high-potential unevaluated opportunities and rerank them into the current response.
        pool_size = min(max(limit * 2, 50), 100)
        pool_items = query.limit(pool_size).all()

        if candidate and user_id and pool_items:
            # Find unevaluated or stale opportunities in the pool
            unevaluated_pairs = [
                (opp, match_rec) for opp, match_rec in pool_items 
                if match_rec is None or match_rec.engine_version != MATCHING_ENGINE_VERSION
            ]

            if unevaluated_pairs:
                cand_skills_lower = set()
                if candidate.skills:
                    for s in candidate.skills:
                        if isinstance(s, dict):
                            cand_skills_lower.add(s.get("name", "").lower().strip())
                        elif isinstance(s, str):
                            cand_skills_lower.add(s.lower().strip())

                def eval_priority_score(item_tuple):
                    opp, _ = item_tuple
                    text = f"{opp.title} {opp.description or ''}".lower()
                    overlap = sum(1 for sk in cand_skills_lower if sk in text)
                    cat_match = 2 if opp.internship_category == "software_engineering" else 0
                    return (overlap * 2 + cat_match, opp.id)

                unevaluated_pairs.sort(key=eval_priority_score, reverse=True)
                opps_to_evaluate = [p[0] for p in unevaluated_pairs[:max_eval_per_request]]

                try:
                    batch_results = await matching_service.evaluate_matches_batch(
                        candidate=candidate,
                        opportunities=opps_to_evaluate,
                        db=db,
                        force_refresh=False,
                        use_ai=False
                    )
                    updated_pool = []
                    for opp, rec in pool_items:
                        if opp.id in batch_results:
                            _, new_rec = batch_results[opp.id]
                            updated_pool.append((opp, new_rec))
                        else:
                            updated_pool.append((opp, rec))
                    pool_items = updated_pool
                except Exception as e:
                    logger.warning(f"Batch on-demand evaluation failed: {e}")

        # Same-response reranking when sort_by == "match_score"
        if sort_by == "match_score":
            def pool_sort_key(item_tuple):
                opp, match_rec = item_tuple
                if match_rec and match_rec.match_score is not None:
                    score = match_rec.match_score
                    tier = 2 if score >= 50.0 else 0
                    return (tier, score, opp.id)
                else:
                    return (1, 0.0, opp.id)

            pool_items.sort(key=pool_sort_key, reverse=(sort_order == "desc"))

        # Establish ranking snapshot across L1 and L2 PostgreSQL for subsequent pagination
        if snapshot_key and total > 0:
            top_pool_ids = [opp.id for opp, _ in pool_items]
            if total <= len(top_pool_ids):
                snapshot_ids = top_pool_ids
            else:
                top_pool_id_set = set(top_pool_ids)
                all_db_ids = [r[0] for r in query.with_entities(Opportunity.id).all()]
                snapshot_ids = top_pool_ids + [pid for pid in all_db_ids if pid not in top_pool_id_set]

            active_snapshot_id = snapshot_manager.set_snapshot(
                snapshot_key=snapshot_key,
                user_id=user_id,
                signature=sig,
                candidate_evidence_version=cand_evidence_version or "",
                snapshot_ids=snapshot_ids,
                total_count=total,
                db=db,
                snapshot_id=snapshot_id,
                ttl_seconds=1800
            )

        # Slice to requested pagination window
        if effective_offset == 0:
            items = pool_items[:limit]
            scan_idx = len(items)
            if snapshot_key and total > 0:
                has_more = (scan_idx < total)
                next_cursor = scan_idx if has_more else None
        else:
            # Deterministic reconstruction fallback: slice exact window from snapshot_ids
            page_ids = snapshot_ids[skip : skip + limit] if snapshot_key and total > 0 else []
            if page_ids:
                pairs = db.query(
                    Opportunity,
                    CandidateOpportunityMatch
                ).outerjoin(
                    CandidateOpportunityMatch,
                    and_(
                        CandidateOpportunityMatch.opportunity_id == Opportunity.id,
                        CandidateOpportunityMatch.user_id == user_id
                    )
                ).filter(Opportunity.id.in_(page_ids)).all()
                pair_map = {opp.id: (opp, match_rec) for opp, match_rec in pairs}
                items = [
                    pair_map[pid] for pid in page_ids
                    if pid in pair_map and pair_map[pid][0] is not None and not pair_map[pid][0].is_dismissed
                ]
            else:
                items = []

    results = []
    for item, match_rec in items:
        intel = build_opportunity_intelligence(item, candidate, preferences, match_rec=match_rec)
        item_match_score = intel["match_score"]
        item_elig_status = intel["eligibility_assessment"]["status"]
        
        results.append({
            "id": item.id,
            "title": item.title,
            "description": item.description,
            "normalized_title": item.normalized_title,
            "internship_category": item.internship_category or "software_engineering",
            "company_name": item.company_name,
            "company_website": item.company_website or "",
            "location": item.location,
            "normalized_location": item.normalized_location,
            "workplace_type": item.workplace_type,
            "internship_type": item.internship_type or "in-office",
            "work_mode": item.work_mode or "full-time",
            "employment_type": item.employment_type,
            "stipend_text": item.stipend_text,
            "min_stipend": item.min_stipend,
            "max_stipend": item.max_stipend,
            "currency": item.currency,
            "compensation_type": item.compensation_type or "undisclosed",
            "duration_months": item.duration_months,
            "posted_at": item.posted_at,
            "deadline_at": item.deadline_at,
            "discovered_at": item.discovered_at,
            "last_fetched_at": item.last_fetched_at,
            "last_verified_at": item.last_verified_at,
            "status": item.status,
            "original_url": item.original_url,
            "application_url": item.application_url or item.original_url,
            "source_url": item.source_url or item.original_url,
            "source_platform": item.source_platform,
            "source_links": item.source_links,
            "match_score": item_match_score,
            "eligibility_status": item_elig_status,
            "quality_score": item.quality_score or 0.0,
            "quality_breakdown": item.quality_breakdown or {},
            "top_skills": (item.extracted_data or {}).get("mandatory_technical_skills", [])[:5],
            "is_saved": item.is_saved,
            "is_dismissed": item.is_dismissed,
            "is_applied": item.is_applied,
            "recommendation_impressions": item.recommendation_impressions or 0,
            
            # Opportunity Intelligence
            "intelligence": intel,
            "ranking_reasons": intel.get("ranking_reasons", {}),
            "match_analysis": intel.get("match_analysis", {}),
            "category_scores": intel.get("category_scores", {}),
            "category_weights": intel.get("category_weights", {}),
            "skill_gaps": intel.get("skill_gaps", []),
            "requirement_matches": intel.get("requirement_matches", []),
            "scoring_explanation": intel.get("scoring_explanation", ""),
            "match_freshness": intel.get("match_freshness", {}),
            "content_version": item.content_version,
            "why_it_matches": intel["why_it_matches"],
            "matching_skills": intel["matching_skills"],
            "missing_skills": intel["missing_skills"],
            "eligibility_assessment": intel["eligibility_assessment"],
            "source_reliability": intel["source_reliability"],
            "deadline_info": intel["deadline"],
            "standard_record": item.to_standard_record()
        })

    # Log search history if a query was provided
    if clean_query:
        try:
            history_entry = SearchHistory(
                query=clean_query,
                search_mode=search_mode,
                filters={
                    "category": category, "location": location, "workplace_type": workplace_type,
                    "min_stipend": min_stipend, "sort_by": sort_by
                },
                results_count=total
            )
            db.add(history_entry)
            db.commit()
        except Exception as e:
            logger.warning(f"Could not record search history: {e}")
            db.rollback()

    if return_cursor:
        return results, total, active_snapshot_id, next_cursor, has_more
    if return_snapshot_id:
        return results, total, active_snapshot_id
    return results, total
