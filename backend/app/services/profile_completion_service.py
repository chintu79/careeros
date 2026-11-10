"""
Candidate Profile Completeness & Evidence Density Intelligence Service.
Evaluates persisted candidate data, distinguishes missing from unverified evidence,
and produces actionable recommendations without mutating the deterministic matching formula.
"""
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.app.models.candidate import CandidateProfile
from backend.app.models.resume import ResumeDocument
from backend.app.services.matching.taxonomy import canonicalize_tech_name


def assess_candidate_profile_completeness(candidate: CandidateProfile, db: Session) -> Dict[str, Any]:
    """
    Evaluates profile completeness and evidence readiness for the given candidate profile.
    Strictly isolated to the authenticated candidate's persisted records.
    """
    if not candidate:
        return {
            "completeness_score": 0,
            "readiness_stage": "getting_started",
            "is_onboarded": False,
            "onboarding_status": "not_started",
            "onboarding_step": 1,
            "category_scores": {},
            "verified_evidence": [],
            "unverified_evidence": [],
            "missing_evidence": ["Candidate profile record not found."],
            "actionable_recommendations": [
                {
                    "priority": "high",
                    "title": "Initialize candidate profile",
                    "description": "Start the onboarding journey to establish your verified profile.",
                    "action_target": "onboarding"
                }
            ],
            "skills_summary": {
                "total": 0,
                "verified": 0,
                "unverified": 0,
                "items": []
            },
            "disclaimer": "Profile readiness measures available evidence density for opportunity matching, not candidate qualifications."
        }

    # 1. Basic Info Assessment (15 pts max)
    basic_score = 0
    basic_missing = []
    if candidate.name and candidate.name.strip():
        basic_score += 5
    else:
        basic_missing.append("Full name")

    if candidate.email and candidate.email.strip():
        basic_score += 5
    else:
        basic_missing.append("Email address")

    secondary_basic = 0
    if candidate.location and candidate.location.strip():
        secondary_basic += 2
    if candidate.bio and candidate.bio.strip():
        secondary_basic += 2
    if candidate.phone and candidate.phone.strip():
        secondary_basic += 1
    basic_score += min(5, secondary_basic)

    # 2. Education Assessment (15 pts max)
    edu_score = 0
    edu_missing = []
    if candidate.degree and candidate.degree.strip():
        edu_score += 5
    else:
        edu_missing.append("Degree")

    if candidate.college and candidate.college.strip():
        edu_score += 5
    else:
        edu_missing.append("College or university")

    if candidate.graduation_year:
        edu_score += 5
    else:
        edu_missing.append("Graduation year")

    # 3. Project Evidence Assessment (25 pts max)
    projects = candidate.projects or []
    proj_score = 0
    proj_missing = []
    if len(projects) >= 1:
        proj_score += 15
        has_tech = any(bool(p.get("tech_stack")) for p in projects if isinstance(p, dict))
        if has_tech:
            proj_score += 5
        has_links = any(bool(p.get("url")) for p in projects if isinstance(p, dict)) or len(projects) >= 2
        if has_links:
            proj_score += 5
    else:
        proj_missing.append("Technical projects with technology stacks")

    # Collect project technology tokens for skill verification
    project_tech_tokens = set()
    for p in projects:
        if isinstance(p, dict):
            for t in (p.get("tech_stack") or []):
                project_tech_tokens.add(canonicalize_tech_name(str(t)).lower())
            p_desc = f"{p.get('title', '')} {p.get('description', '')}".lower()
            for token in p_desc.split():
                clean_t = token.strip(".,;:()[]{}'\"")
                if clean_t:
                    project_tech_tokens.add(clean_t)

    # Collect GitHub detected tokens if available
    github_tokens = set()
    if candidate.github_data and isinstance(candidate.github_data, dict):
        for lang in candidate.github_data.get("languages_detected", []):
            github_tokens.add(canonicalize_tech_name(str(lang)).lower())
        for top in candidate.github_data.get("topics_detected", []):
            github_tokens.add(canonicalize_tech_name(str(top)).lower())

    # 4. Technical Skills Assessment & Verification (25 pts max)
    skills = candidate.skills or []
    skill_items = []
    verified_skills_count = 0
    unverified_skills_count = 0

    for s in skills:
        if isinstance(s, dict):
            raw_name = s.get("name", "")
            canon_name = canonicalize_tech_name(raw_name)
            canon_lower = canon_name.lower()
            level = s.get("level", "intermediate")
            category = s.get("category", "General")
            manual_evidence = s.get("evidence", "")

            # Check verification against project tech stack or github
            is_project_verified = canon_lower in project_tech_tokens or any(
                canon_lower in str(t).lower() for t in project_tech_tokens
            )
            is_github_verified = canon_lower in github_tokens

            if is_project_verified:
                status = "verified"
                source = "project_code"
                verified_skills_count += 1
            elif is_github_verified:
                status = "verified"
                source = "github_repositories"
                verified_skills_count += 1
            elif manual_evidence and len(manual_evidence.strip()) > 5:
                status = "verified"
                source = "documented_evidence"
                verified_skills_count += 1
            else:
                status = "unverified"
                source = "self_reported"
                unverified_skills_count += 1

            skill_items.append({
                "name": canon_name,
                "raw_name": raw_name,
                "category": category,
                "level": level,
                "status": status,
                "verification_source": source,
                "evidence": manual_evidence
            })

    skill_score = 0
    if len(skills) >= 1:
        skill_score += 10
    if len(skills) >= 3:
        skill_score += 10
    if verified_skills_count >= 1:
        skill_score += 5

    # 5. Resume Status Assessment (15 pts max)
    resume_score = 0
    has_master_resume = False
    resume_versions_count = 0

    master_res = db.query(ResumeDocument).filter(
        ResumeDocument.user_id == candidate.user_id,
        ResumeDocument.is_master == True
    ).first()

    if master_res:
        has_master_resume = True
        resume_score += 15
        resume_versions_count = master_res.version or 1
    elif candidate.raw_resume_text and len(candidate.raw_resume_text.strip()) > 50:
        resume_score += 10
    else:
        # Check if any custom resume exists
        any_res = db.query(ResumeDocument).filter(ResumeDocument.user_id == candidate.user_id).first()
        if any_res:
            resume_score += 10

    # 6. Career Goals & Intent (5 pts max)
    goals_score = 0
    career_goals = candidate.career_goals or {}
    if isinstance(career_goals, dict):
        if career_goals.get("target_roles") or candidate.preferred_locations or candidate.work_authorization:
            goals_score += 5

    # Calculate Total Evidence Completeness Score (0-100)
    total_score = min(100, basic_score + edu_score + proj_score + skill_score + resume_score + goals_score)

    # Classify Readiness Stage
    if total_score >= 75:
        stage = "high_confidence_readiness"
    elif total_score >= 40:
        stage = "core_evidence_ready"
    else:
        stage = "getting_started"

    # Assemble Evidence Lists
    verified_evidence = []
    unverified_evidence = []
    missing_evidence = []

    if candidate.name and candidate.email:
        verified_evidence.append(f"Identity confirmed: {candidate.name} ({candidate.email})")
    if candidate.degree and candidate.college:
        verified_evidence.append(f"Education: {candidate.degree} from {candidate.college}")
    if candidate.graduation_year:
        verified_evidence.append(f"Eligibility: Expected graduation year {candidate.graduation_year}")
    if len(projects) > 0:
        verified_evidence.append(f"{len(projects)} technical project(s) documented with technology stacks")
    if verified_skills_count > 0:
        verified_evidence.append(f"{verified_skills_count} skill(s) verified by project code or external repositories")
    if has_master_resume:
        verified_evidence.append("Master Resume initialized and available for ATS tailoring")
    if candidate.github_username or candidate.github_url:
        verified_evidence.append(f"GitHub connected: {candidate.github_username or candidate.github_url}")

    for s in skill_items:
        if s["status"] == "unverified":
            unverified_evidence.append(f"Skill '{s['name']}' is self-reported without supporting project code")

    for m in basic_missing:
        missing_evidence.append(f"Basic information: {m}")
    for m in edu_missing:
        missing_evidence.append(f"Education: {m}")
    for m in proj_missing:
        missing_evidence.append(f"Portfolio: {m}")
    if len(skills) == 0:
        missing_evidence.append("Technical skills: No technical skills added")
    if not has_master_resume and not candidate.raw_resume_text:
        missing_evidence.append("Resume: No master resume document initialized")

    # Generate Prioritized Actionable Recommendations
    recommendations = []
    if len(skills) == 0:
        recommendations.append({
            "priority": "critical",
            "title": "Add your core technical skills",
            "description": "Mandatory skills account for 40% of the opportunity matching score.",
            "action_target": "skills"
        })

    if len(projects) == 0:
        recommendations.append({
            "priority": "high",
            "title": "Add technical projects",
            "description": "Projects demonstrate hands-on software engineering capabilities (15% match weight).",
            "action_target": "projects"
        })
    elif unverified_skills_count > 0:
        recommendations.append({
            "priority": "medium",
            "title": "Link projects to verify skills",
            "description": f"You have {unverified_skills_count} self-reported skills. Adding project evidence verifies proficiency for matching algorithms.",
            "action_target": "projects"
        })

    if not has_master_resume:
        recommendations.append({
            "priority": "high",
            "title": "Upload or generate your Master Resume",
            "description": "A master resume unlocks 1-click tailored ATS exports and ensures comprehensive profile parsing.",
            "action_target": "resumes"
        })

    if not candidate.graduation_year:
        recommendations.append({
            "priority": "high",
            "title": "Specify your graduation year",
            "description": "Graduation year is required to verify eligibility filters for internships and new-grad roles.",
            "action_target": "education"
        })

    if not candidate.github_username and not candidate.github_url:
        recommendations.append({
            "priority": "medium",
            "title": "Connect your GitHub profile",
            "description": "Enables deep code manifest intelligence and automated language verification.",
            "action_target": "github"
        })

    if not career_goals.get("target_roles"):
        recommendations.append({
            "priority": "medium",
            "title": "Define your target career roles",
            "description": "Guides discovery search algorithms toward your preferred engineering specializations.",
            "action_target": "career_goals"
        })

    return {
        "completeness_score": total_score,
        "readiness_stage": stage,
        "is_onboarded": (candidate.onboarding_status == "completed"),
        "onboarding_status": candidate.onboarding_status or "not_started",
        "onboarding_step": candidate.onboarding_step or 1,
        "category_scores": {
            "basic_info": {"score": basic_score, "max": 15},
            "education": {"score": edu_score, "max": 15},
            "technical_skills": {"score": skill_score, "max": 25},
            "projects": {"score": proj_score, "max": 25},
            "resume": {"score": resume_score, "max": 15},
            "career_goals": {"score": goals_score, "max": 5}
        },
        "verified_evidence": verified_evidence,
        "unverified_evidence": unverified_evidence,
        "missing_evidence": missing_evidence,
        "actionable_recommendations": recommendations,
        "skills_summary": {
            "total": len(skills),
            "verified": verified_skills_count,
            "unverified": unverified_skills_count,
            "items": skill_items
        },
        "has_master_resume": has_master_resume,
        "master_resume_version": resume_versions_count,
        "projects_count": len(projects),
        "disclaimer": "Profile readiness measures available evidence density for opportunity matching, not candidate qualifications."
    }
