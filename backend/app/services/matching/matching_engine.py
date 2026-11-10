"""
Deterministic Requirement-to-Evidence Matching Engine for CareerOS.
Implements granular requirement matching (strong, partial, weak, no evidence, not applicable),
distinguishes exact technology matches from related/transferable technologies,
and executes a transparent, reproducible weighted scoring model.
"""
import re
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional

from backend.app.schemas.matching import (
    ParsedJobDescription,
    ExtractedRequirement,
    RequirementPriority,
    UnifiedCandidateEvidence,
    CandidateEvidenceItem,
    RequirementMatchResult,
    MatchStatus,
    ProfileMatchResult,
    EvidenceProvenanceType
)
from backend.app.services.matching.taxonomy import (
    canonicalize_tech_name,
    get_technology_relationship
)

logger = logging.getLogger(__name__)

# Configurable Category Weights (Sum = 1.0)
CATEGORY_WEIGHTS: Dict[str, float] = {
    "mandatory_technical_skills": 0.40,
    "preferred_technical_skills": 0.15,
    "relevant_experience": 0.20,
    "project_evidence": 0.15,
    "education_and_certifications": 0.10
}


def match_single_requirement(
    req: ExtractedRequirement,
    candidate_evidence: UnifiedCandidateEvidence
) -> RequirementMatchResult:
    """
    Evaluates candidate evidence against a single extracted requirement.
    Returns: RequirementMatchResult with status, strength, confidence, and explanation.
    """
    req_name = req.name
    req_canon = canonicalize_tech_name(req_name)
    req_lower = req_canon.lower()

    best_match_type = "none"
    best_strength = 0.0
    best_status = MatchStatus.NO_EVIDENCE
    best_confidence = "unverified"
    best_explanation = f"No candidate evidence found for {req_canon}."
    matched_items: List[CandidateEvidenceItem] = []

    for item in candidate_evidence.evidence_items:
        cand_canon = item.canonical_name
        rel_type, strength, rationale = get_technology_relationship(cand_canon, req_canon)

        if rel_type == "none":
            continue

        # Adjust strength based on verification provenance
        if not item.is_verified:
            # Unverified evidence (e.g. unverified commit authorship, AI-derived project claim)
            effective_strength = min(0.20, strength * 0.3)
            confidence = "unverified"
            explanation = f"Unverified signal: {item.evidence_text}. Candidate authorship not proven."
            status = MatchStatus.WEAK_MATCH
        elif rel_type == "exact":
            effective_strength = 1.0
            confidence = "high"
            status = MatchStatus.STRONG_MATCH
            explanation = f"Verified exact match: Candidate demonstrates {cand_canon} via {item.provenance.value} ({item.source_identifier})."
        elif rel_type == "related":
            effective_strength = strength # e.g. 0.55 - 0.65
            confidence = "medium"
            status = MatchStatus.PARTIAL_MATCH
            explanation = f"Related technology: {rationale} (Source: {item.source_identifier}). Note: Not an exact match."
        elif rel_type == "transferable":
            effective_strength = strength # e.g. 0.35 - 0.40
            confidence = "medium"
            status = MatchStatus.WEAK_MATCH
            explanation = f"Transferable skill: {rationale} (Source: {item.source_identifier})."
        else:
            continue

        if effective_strength > best_strength:
            best_strength = effective_strength
            best_match_type = rel_type
            best_status = status
            best_confidence = confidence
            best_explanation = explanation

        matched_items.append(item)

    missing_desc = None
    if best_status in [MatchStatus.NO_EVIDENCE, MatchStatus.WEAK_MATCH]:
        missing_desc = f"Candidate lacks verified hands-on production or project evidence in {req_canon}."

    return RequirementMatchResult(
        requirement=req,
        status=best_status,
        matched_evidence=matched_items[:3],
        evidence_strength=round(best_strength, 2),
        confidence=best_confidence,
        match_type=best_match_type,
        explanation=best_explanation,
        missing_evidence_description=missing_desc
    )


def evaluate_experience_match(
    exp_requirement_text: str,
    candidate_exp_years: float,
    is_internship: bool = True
) -> Tuple[float, str]:
    """
    Evaluates candidate experience against stated job requirements.
    Returns: (category_score [0-100], explanation)
    """
    req_lower = exp_requirement_text.lower()
    
    # Check for required years in JD (e.g. "5+ years", "3-5 years", "2 to 4 yrs")
    match = re.search(r'(\d+)\s*(?:\+|plus)?\s*(?:to|-)?\s*(?:\d+)?\s*(?:years?|yrs?)', req_lower)
    if not match:
        # No explicit experience required or fresher friendly
        return (100.0, "Experience requirement is entry-level / not explicitly specified. Candidate eligible.")

    min_required_years = float(match.group(1))

    if min_required_years <= 1.0 or is_internship:
        return (100.0, f"Role requires {min_required_years} yr(s). Candidate entry-level experience aligns with target cohort.")

    # Senior / Mid-level role requirement mismatch
    if candidate_exp_years >= min_required_years:
        return (100.0, f"Candidate has {candidate_exp_years} yrs experience, satisfying {min_required_years} yrs requirement.")
    
    ratio = min(1.0, max(0.2, candidate_exp_years / min_required_years))
    score = round(ratio * 100.0, 1)
    return (score, f"Experience level gap: Job requires {min_required_years} years. Candidate has {candidate_exp_years} years.")


def evaluate_education_and_certifications(
    edu_requirement_text: str,
    cert_requirements: List[str],
    candidate_education: Dict[str, Any],
    candidate_certs: List[str]
) -> Tuple[float, str]:
    """
    Evaluates educational background and requested certifications.
    Returns: (category_score [0-100], explanation)
    """
    score = 100.0
    notes = []

    req_lower = edu_requirement_text.lower()
    cand_deg = (candidate_education.get("degree") or "").lower()

    if "phd" in req_lower and "phd" not in cand_deg:
        score -= 30.0
        notes.append("Job specifies Ph.D. prerequisite; candidate has undergraduate engineering degree.")
    elif "master" in req_lower and not any(m in cand_deg for m in ["master", "m.tech", "ms"]):
        score -= 15.0
        notes.append("Job prefers Master's degree; candidate is enrolled in Bachelor's program.")
    else:
        notes.append("Candidate academic background matches degree requirement.")

    if cert_requirements:
        cand_certs_lower = [c.lower() for c in candidate_certs]
        matched_certs = [c for c in cert_requirements if any(c.lower() in cc for cc in cand_certs_lower)]
        if matched_certs:
            notes.append(f"Verified certifications: {', '.join(matched_certs)}.")
        else:
            score -= 15.0
            notes.append(f"Lacks preferred certifications: {', '.join(cert_requirements[:2])}.")
    else:
        notes.append("No specialized industry certifications required.")

    final_score = max(0.0, min(100.0, score))
    return (round(final_score, 1), " ".join(notes))


def evaluate_project_portfolio(
    parsed_jd: ParsedJobDescription,
    candidate_evidence: UnifiedCandidateEvidence
) -> Tuple[float, str]:
    """
    Evaluates candidate project portfolio depth and relevance.
    Returns: (category_score [0-100], explanation)
    """
    job_techs = {r.name.lower() for r in parsed_jd.requirements}
    
    # Find candidate curated projects that overlap with job technologies
    matching_project_sources = set()
    for item in candidate_evidence.evidence_items:
        if item.provenance == EvidenceProvenanceType.CURATED_PROJECT and item.is_verified:
            if item.canonical_name.lower() in job_techs:
                matching_project_sources.add(item.source_identifier)

    count = len(matching_project_sources)
    if count >= 2:
        return (100.0, f"Strong portfolio alignment: {count} verified curated projects demonstrate core job technologies.")
    elif count == 1:
        return (75.0, "Moderate portfolio alignment: 1 verified project directly demonstrates required tech stack.")
    else:
        # Check if candidate has any verified projects
        total_projects = len({item.source_identifier for item in candidate_evidence.evidence_items if item.provenance == EvidenceProvenanceType.CURATED_PROJECT})
        if total_projects > 0:
            return (50.0, f"General portfolio credit: {total_projects} projects demonstrate general engineering principles.")
        return (25.0, "No verified project portfolio items available in candidate profile.")


def calculate_profile_match(
    parsed_jd: ParsedJobDescription,
    candidate_evidence: UnifiedCandidateEvidence,
    weights: Optional[Dict[str, float]] = None
) -> Tuple[ProfileMatchResult, List[RequirementMatchResult]]:
    """
    Executes complete deterministic matching and explainable scoring calculation.
    """
    active_weights = dict(weights or CATEGORY_WEIGHTS)
    
    # 1. Deduplicate requirements by canonical name and priority to prevent duplicate requirement score inflation
    deduped_reqs: List[ExtractedRequirement] = []
    seen_req_keys = set()
    for req in parsed_jd.requirements:
        canon = canonicalize_tech_name(req.name).lower()
        key = (canon, req.priority.value)
        if key not in seen_req_keys:
            seen_req_keys.add(key)
            deduped_reqs.append(req)

    # 1B. Match each requirement against candidate evidence
    req_matches: List[RequirementMatchResult] = []
    for req in deduped_reqs:
        m = match_single_requirement(req, candidate_evidence)
        req_matches.append(m)

    # 2. Score Category 1: Mandatory Technical Skills (Weight: 40%)
    mand_matches = [m for m in req_matches if m.requirement.priority == RequirementPriority.MANDATORY]
    if mand_matches:
        mand_score = sum(m.evidence_strength for m in mand_matches) / len(mand_matches) * 100.0
    else:
        # Missing data neutrality: if JD specifies no mandatory skills, neutral full score
        mand_score = 100.0

    # 3. Score Category 2: Preferred Technical Skills (Weight: 15%)
    pref_matches = [m for m in req_matches if m.requirement.priority == RequirementPriority.PREFERRED]
    if pref_matches:
        pref_score = sum(m.evidence_strength for m in pref_matches) / len(pref_matches) * 100.0
    else:
        # Missing data neutrality
        pref_score = 100.0

    # 4. Score Category 3: Relevant Experience (Weight: 20%)
    is_intern = parsed_jd.employment_type == "internship"
    exp_score, exp_expl = evaluate_experience_match(parsed_jd.experience_requirements, candidate_evidence.experience_years, is_intern)

    # 5. Score Category 4: Project Evidence (Weight: 15%)
    proj_score, proj_expl = evaluate_project_portfolio(parsed_jd, candidate_evidence)

    # 6. Score Category 5: Education & Certifications (Weight: 10%)
    edu_score, edu_expl = evaluate_education_and_certifications(
        parsed_jd.education_requirements,
        parsed_jd.certifications,
        candidate_evidence.education,
        candidate_evidence.certifications
    )

    category_scores = {
        "mandatory_technical_skills": round(mand_score, 1),
        "preferred_technical_skills": round(pref_score, 1),
        "relevant_experience": round(exp_score, 1),
        "project_evidence": round(proj_score, 1),
        "education_and_certifications": round(edu_score, 1)
    }

    # 7. Composite Profile Match Score (0.0 - 100.0)
    composite = sum(category_scores[cat] * active_weights[cat] for cat in active_weights.keys())
    final_score = round(max(0.0, min(100.0, composite)), 1)

    # 8. Eligibility and Flags
    eligibility_status = "eligible"
    disqualifying_reasons = []

    # Flag if significant mandatory requirements are missing
    missing_mandatory = [m.requirement.name for m in mand_matches if m.status == MatchStatus.NO_EVIDENCE]
    if len(missing_mandatory) >= 3 or (len(mand_matches) > 0 and mand_score < 30.0):
        eligibility_status = "flagged"
        disqualifying_reasons.append(f"Significant mandatory technical gaps: {', '.join(missing_mandatory[:3])}")

    # 9. Build Clear Mathematical Scoring Explanation
    explanation_parts = [
        f"Profile Match Score: {final_score}/100.",
        f"Category Breakdown (Formula: Score = sum(Category * Weight)):",
        f"1. Mandatory Technical Skills ({int(active_weights['mandatory_technical_skills']*100)}%): {category_scores['mandatory_technical_skills']}/100 "
        f"({len(mand_matches) - len(missing_mandatory)}/{len(mand_matches)} matched).",
        f"2. Preferred Technical Skills ({int(active_weights['preferred_technical_skills']*100)}%): {category_scores['preferred_technical_skills']}/100.",
        f"3. Relevant Experience ({int(active_weights['relevant_experience']*100)}%): {category_scores['relevant_experience']}/100 ({exp_expl}).",
        f"4. Project Evidence ({int(active_weights['project_evidence']*100)}%): {category_scores['project_evidence']}/100 ({proj_expl}).",
        f"5. Education & Certifications ({int(active_weights['education_and_certifications']*100)}%): {category_scores['education_and_certifications']}/100 ({edu_expl})."
    ]
    scoring_explanation = "\n".join(explanation_parts)

    match_result = ProfileMatchResult(
        profile_match_score=final_score,
        category_scores=category_scores,
        category_weights=active_weights,
        requirement_matches=req_matches,
        skill_gaps=[], # Populated by gap_analyzer
        eligibility_status=eligibility_status,
        disqualifying_reasons=disqualifying_reasons,
        scoring_explanation=scoring_explanation,
        candidate_content_hash=candidate_evidence.content_hash,
        opportunity_content_hash=parsed_jd.content_hash,
        calculated_at=datetime.now(timezone.utc).isoformat(),
        is_stale=False,
        is_cached=False,
        engine_version="2.0.0",
        user_id=candidate_evidence.user_id
    )

    return match_result, req_matches
