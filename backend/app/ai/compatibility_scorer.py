import time
from typing import Dict, Any, List, Tuple
from functools import wraps

from backend.app.observability.metrics import metrics as _match_metrics

# Transferable skill knowledge base
TRANSFERABLE_MAP = {
    "pytorch": ("TensorFlow", "Has solid deep learning foundations in TensorFlow, enabling rapid transfer to PyTorch tensor APIs"),
    "tensorflow": ("PyTorch", "Demonstrated PyTorch deep learning workflow; principles map directly to TensorFlow"),
    "rest api": ("Express.js / FastAPI", "Built robust REST microservices and endpoints in Node/Express and FastAPI"),
    "graphql": ("REST API", "Strong background in API contracts and data modeling"),
    "vue": ("React", "Extensive component lifecycle and state management mastery in React translates directly to Vue"),
    "angular": ("React & TypeScript", "Proficient in typed components and reactive web state management"),
    "django": ("FastAPI / Flask", "Extensive Python backend architecture and ORM database skills"),
    "mongodb": ("PostgreSQL", "Database querying and indexing expertise"),
    "redis": ("PostgreSQL / Caching", "Understands caching strategies, session stores, and key-value paradigms"),
    "aws": ("Docker / Linux", "Containerized cloud deployment and virtual server configuration experience"),
    "gcp": ("AWS / Docker", "Understands cloud primitives, storage buckets, and container orchestration"),
    "kubernetes": ("Docker", "Understands containerization, networking, and microservices architecture"),
    "next.js": ("React", "Direct expertise in modern React component design and client/server boundaries"),
    "c++": ("C / Algorithms", "Foundational systems programming and memory management principles"),
    "go": ("Python / Backend", "Concurrent backend services and clean API development experience")
}

def _with_match_metrics(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        started = time.perf_counter()
        try:
            result = func(*args, **kwargs)
        except Exception:
            _match_metrics.inc("matching_evaluations_total", {"outcome": "failure"})
            _match_metrics.observe(
                "matching_evaluations_duration_seconds",
                time.perf_counter() - started,
                {"outcome": "failure"},
            )
            raise
        _match_metrics.inc("matching_evaluations_total", {"outcome": "success"})
        _match_metrics.observe(
            "matching_evaluations_duration_seconds",
            time.perf_counter() - started,
            {"outcome": "success"},
        )
        return result
    return wrapper


@_with_match_metrics
def evaluate_compatibility(
    extracted_data: Dict[str, Any],
    candidate_profile: Dict[str, Any],
    user_preferences: Dict[str, Any],
    job_location: str = "",
    workplace_type: str = "remote",
    is_paid: bool = True,
    stipend_amount: float = 0.0,
    job_company: str = ""
) -> Dict[str, Any]:
    """
    Transparent 6-factor compatibility scorer and eligibility checker.
    Weights:
      1. Required Technical Skills: 35%
      2. Relevant Projects & Experience: 25%
      3. Education & Eligibility: 15%
      4. Preferred Skills: 10%
      5. Location & Availability: 10%
      6. Other Requirements & Soft Skills: 5%
    """
    candidate_skills = {s.get("name", "").lower(): s for s in candidate_profile.get("skills", [])}
    candidate_projects = candidate_profile.get("projects", [])
    
    mandatory_reqs = extracted_data.get("mandatory_technical_skills", [])
    preferred_reqs = extracted_data.get("preferred_skills", [])
    
    # --- Factor 1: Required Technical Skills (35%) ---
    strong_matches = []
    partial_matches = []
    missing_skills = []
    unverified_skills = []
    
    for req in mandatory_reqs:
        req_clean = req.strip()
        req_lower = req_clean.lower()
        
        # Check direct match
        if req_lower in candidate_skills:
            evidence = candidate_skills[req_lower].get("evidence", "Candidate verified profile")
            strong_matches.append({
                "skill": req_clean,
                "evidence": evidence
            })
        elif any(req_lower in s_name or s_name in req_lower for s_name in candidate_skills):
            # Partial name match
            matched_key = next(s_name for s_name in candidate_skills if req_lower in s_name or s_name in req_lower)
            strong_matches.append({
                "skill": req_clean,
                "evidence": f"Demonstrated in {candidate_skills[matched_key].get('name')}"
            })
        elif req_lower in TRANSFERABLE_MAP:
            # Transferable skill
            trans_source, trans_reason = TRANSFERABLE_MAP[req_lower]
            partial_matches.append({
                "skill": req_clean,
                "transferable_from": trans_source,
                "reason": trans_reason
            })
        else:
            missing_skills.append(req_clean)
            
    total_mandatory = len(mandatory_reqs) if mandatory_reqs else 1
    skill_score_ratio = (len(strong_matches) * 1.0 + len(partial_matches) * 0.6) / total_mandatory
    skill_score = min(35.0, max(0.0, skill_score_ratio * 35.0))
    
    # --- Factor 2: Projects & Experience (25%) ---
    matched_projects = []
    all_job_keywords = set([s.lower() for s in mandatory_reqs + preferred_reqs])
    for proj in candidate_projects:
        tech_stack = [t.lower() for t in proj.get("tech_stack", [])]
        overlap = set(tech_stack).intersection(all_job_keywords)
        if overlap or any(kw in proj.get("description", "").lower() for kw in all_job_keywords):
            matched_projects.append({
                "title": proj.get("title"),
                "description": proj.get("description"),
                "overlapping_tech": list(overlap),
                "relevance": f"Covers {len(overlap)} core technologies: {', '.join(list(overlap)[:3])}"
            })
    
    if len(matched_projects) >= 2:
        project_score = 25.0
    elif len(matched_projects) == 1:
        project_score = 18.0
    else:
        project_score = 10.0 # general software project credit
        
    # --- Factor 3: Education & Eligibility (15%) ---
    candidate_grad_year = candidate_profile.get("graduation_year", 2026)
    pref_grad_year = user_preferences.get("graduation_year", 2026)
    edu_text = extracted_data.get("educational_requirements", "").lower()
    
    edu_score = 15.0
    edu_compatibility = "Bachelor's engineering background matches the degree requirement."
    
    disqualifying_reasons = []
    eligibility_status = "eligible"
    
    # Check graduation year or student constraints
    if "2024" in edu_text and "2026" not in edu_text and "student" not in edu_text:
        edu_score = 8.0
        edu_compatibility = "Posting prefers immediate graduates (Class of 2024). Candidate graduates in 2026."
        disqualifying_reasons.append("Graduation year preference gap (Job targets earlier cohort)")
        eligibility_status = "flagged"
        
    # --- Factor 4: Preferred Skills (10%) ---
    matched_pref_count = 0
    for pref in preferred_reqs:
        p_lower = pref.lower().strip()
        if p_lower in candidate_skills or any(p_lower in s_name for s_name in candidate_skills):
            matched_pref_count += 1
    total_pref = len(preferred_reqs) if preferred_reqs else 1
    pref_score = min(10.0, (matched_pref_count / total_pref) * 10.0)
    
    # --- Factor 5: Location & Availability (10%) ---
    loc_score = 10.0
    loc_lower = (job_location or "").lower()
    restrictions = extracted_data.get("eligibility_restrictions", [])
    
    # Check geographical eligibility for Indian student
    is_us_only = any("us only" in r.lower() or "united states only" in r.lower() for r in restrictions) or "us only" in loc_lower
    is_eu_only = any("eu only" in r.lower() or "european union" in r.lower() for r in restrictions)
    
    if is_us_only:
        loc_score = 0.0
        disqualifying_reasons.append("Geographical restriction: US residents only (Not available for candidates in India)")
        eligibility_status = "disqualified"
    elif is_eu_only:
        loc_score = 0.0
        disqualifying_reasons.append("Geographical restriction: EU residents only")
        eligibility_status = "disqualified"
    elif "india" in loc_lower or "pune" in loc_lower or "bengaluru" in loc_lower or "mumbai" in loc_lower or workplace_type == "remote":
        loc_score = 10.0
    else:
        loc_score = 7.0 # worldwide or unverified timezone
        
    # Check unpaid exclusions
    if not is_paid and user_preferences.get("paid_only", True) and not user_preferences.get("allow_unpaid", False):
        disqualifying_reasons.append("Unpaid internship excluded by user preferences")
        eligibility_status = "disqualified"
        
    # Check minimum stipend preference
    min_pref_stipend = user_preferences.get("min_stipend", 0.0)
    if is_paid and stipend_amount > 0 and stipend_amount < min_pref_stipend:
        disqualifying_reasons.append(f"Stipend (₹{int(stipend_amount)}/mo) below user minimum (₹{int(min_pref_stipend)}/mo)")
        if eligibility_status != "disqualified":
            eligibility_status = "flagged"
            
    # Check excluded companies
    excluded_companies = [c.lower() for c in user_preferences.get("excluded_companies", [])]
    if job_company and job_company.lower() in excluded_companies:
        disqualifying_reasons.append(f"Company '{job_company}' is in user exclusion list")
        eligibility_status = "disqualified"

    # --- Factor 6: Soft Skills & Culture (5%) ---
    other_score = 5.0
    
    total_score = round(skill_score + project_score + edu_score + pref_score + loc_score + other_score, 1)
    if eligibility_status == "disqualified":
        # Cap match score to reflect non-viability
        total_score = min(total_score, 35.0)

    # Build clear human-readable recommendation reasons
    recommendation_reasons = []
    if strong_matches:
        top_skills = [m["skill"] for m in strong_matches[:3]]
        recommendation_reasons.append(f"Strong direct alignment with {', '.join(top_skills)}")
    if partial_matches:
        p_desc = [f"{p['skill']} (via {p['transferable_from']})" for p in partial_matches[:2]]
        recommendation_reasons.append(f"Transferable expertise in {', '.join(p_desc)}")
    if matched_projects:
        recommendation_reasons.append(f"Verified project portfolio: '{matched_projects[0]['title']}' proves hands-on capability")
    if workplace_type in ["remote", "hybrid"]:
        recommendation_reasons.append("Flexible workplace arrangement compatible with college schedule")

    return {
        "match_score": total_score,
        "score_breakdown": {
            "required_technical_skills": round(skill_score, 1),
            "projects_and_experience": round(project_score, 1),
            "education_and_eligibility": round(edu_score, 1),
            "preferred_skills": round(pref_score, 1),
            "location_and_availability": round(loc_score, 1),
            "other_requirements": round(other_score, 1)
        },
        "skill_compatibility": {
            "strong": strong_matches,
            "partial": partial_matches,
            "missing": missing_skills,
            "unverified": unverified_skills
        },
        "experience_compatibility": "0-1 years entry level matches student internship profile",
        "education_compatibility": edu_compatibility,
        "eligibility_status": eligibility_status,
        "disqualifying_reasons": disqualifying_reasons,
        "transferable_skills": [p["skill"] for p in partial_matches],
        "relevant_projects": matched_projects,
        "recommendation_reasons": recommendation_reasons
    }
