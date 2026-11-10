import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from backend.app.services.ai.service import ai_service, validate_tailoring_safety
from backend.app.services.ai.types import TaskType, AIProviderError
from backend.app.schemas.structured_resume import (
    StructuredResumeContent,
    SectionRegenerationProposal,
    BulletPoint,
    generate_stable_id
)

logger = logging.getLogger(__name__)


class SummaryGenerationOutput(BaseModel):
    summary: str = Field(..., description="Concise, impactful professional summary grounded strictly in candidate profile")
    rationale: str = Field(default="", description="Why this summary fits the candidate and target role")


class BulletsGenerationOutput(BaseModel):
    bullets: List[str] = Field(..., description="List of high-impact STAR engineering bullet points")
    rationale: str = Field(default="", description="Technical rationale for the phrasing improvements")


class SkillsGroupingOutput(BaseModel):
    categorized_skills: List[Dict[str, Any]] = Field(..., description="Skills grouped by category strictly from candidate verified skills")
    rationale: str = Field(default="", description="Strategic rationale for categorization")


class AchievementGenerationOutput(BaseModel):
    description: str = Field(..., description="Refined, concise description of the achievement with active verbs")
    rationale: str = Field(default="", description="Rationale for phrasing enhancement")


async def regenerate_resume_section(
    section: str,
    resume_content: StructuredResumeContent,
    candidate_profile_data: Dict[str, Any],
    opportunity_data: Optional[Dict[str, Any]] = None,
    entry_id: Optional[str] = None,
    user_instructions: Optional[str] = None
) -> SectionRegenerationProposal:
    """
    Regenerates a single resume section using Groq cloud reasoning.
    Strict Zero-Fabrication: Never invents skills, employers, metrics, or degrees.
    Preserves original section if AI service fails.
    Returns a proposal only (does not mutate saved state).
    """
    section_lower = section.lower().strip()
    candidate_skills = candidate_profile_data.get("skills", []) or []
    target_role = opportunity_data.get("title", "") if opportunity_data else ""
    target_company = opportunity_data.get("company_name", "") if opportunity_data else ""
    target_skills = (
        (opportunity_data.get("required_skills") or []) + 
        (opportunity_data.get("preferred_skills") or [])
    ) if opportunity_data else []

    instructions_clause = f"\nCandidate Specific Instructions: {user_instructions}" if user_instructions else ""

    # 1. Professional Summary
    if section_lower in ("summary", "professional_summary"):
        original = resume_content.summary or ""
        system_prompt = (
            "You are CareerOS Executive Resume Strategist powered by Groq. "
            "STRICT ZERO-FABRICATION RULE: Write a 2-3 sentence impactful professional summary. "
            "Only mention technologies, roles, and education verified in candidate profile. "
            "Never invent certifications, past employers, or unverified skills. Output valid JSON."
        )
        prompt = f"""Candidate Verified Profile:
Name: {candidate_profile_data.get('name')} | Degree: {candidate_profile_data.get('degree')} | College: {candidate_profile_data.get('college')}
Verified Skills: {[s.get('name') if isinstance(s, dict) else s for s in candidate_skills]}
Verified Projects: {[p.get('title') for p in candidate_profile_data.get('projects', [])[:4]]}

Target Context: Role: '{target_role}' at '{target_company}'
Target Desired Skills: {target_skills}

Existing Summary:
"{original}"
{instructions_clause}

Produce JSON with:
1. summary (2-3 concise, dense sentences highlighting verified engineering strengths)
2. rationale
"""
        resp = await ai_service.router.execute(
            task_type=TaskType.RESUME_TAILORING,
            prompt=prompt,
            system_prompt=system_prompt,
            response_schema=SummaryGenerationOutput,
            temperature=0.2
        )
        parsed = resp.parsed_json or {}
        proposed_text = parsed.get("summary", original)
        return SectionRegenerationProposal(
            section=section_lower,
            entry_id=entry_id,
            original_content=original,
            proposed_content=proposed_text,
            rationale=parsed.get("rationale", "Refined professional summary aligning verified skills with target role.")
        )

    # 2. Projects
    elif section_lower in ("projects", "project"):
        target_proj = None
        if entry_id:
            for p in resume_content.projects:
                if p.id == entry_id:
                    target_proj = p
                    break
        if not target_proj and resume_content.projects:
            target_proj = resume_content.projects[0]

        if not target_proj:
            raise ValueError("No project entry found to regenerate.")

        original_bullets = [b.model_dump() for b in target_proj.bullets]
        orig_bullet_texts = [b.text for b in target_proj.bullets] or ([target_proj.description] if target_proj.description else [])

        # Match corresponding profile project evidence
        evidence_proj = None
        for cp in candidate_profile_data.get("projects", []):
            if cp.get("title", "").lower() == target_proj.title.lower():
                evidence_proj = cp
                break

        system_prompt = (
            "You are CareerOS Senior Technical Resume Writer powered by Groq. "
            "STRICT ZERO-FABRICATION RULE: Rewrite project bullets using decisive STAR action verbs. "
            "Never invent frameworks, numbers, APIs, or technologies not in the project or profile. "
            "Keep technical details accurate and concise. Output valid JSON."
        )
        prompt = f"""Project Title: {target_proj.title}
Tech Stack: {target_proj.tech_stack}
Verified Profile Evidence: {evidence_proj.get('description', '') if evidence_proj else ''}

Existing Bullets:
{orig_bullet_texts}

Target Job: {target_role} at {target_company}
Relevant Skills to highlight: {target_skills}
{instructions_clause}

Produce JSON with:
1. bullets (List of 2-4 high-impact engineering bullet points with active verbs)
2. rationale
"""
        resp = await ai_service.router.execute(
            task_type=TaskType.RESUME_TAILORING,
            prompt=prompt,
            system_prompt=system_prompt,
            response_schema=BulletsGenerationOutput,
            temperature=0.2
        )
        parsed = resp.parsed_json or {}
        proposed_raw_bullets = parsed.get("bullets", orig_bullet_texts)

        # Safety filter against hallucinated skills
        dropped_claims = []
        proposed_bullet_objects = []
        for idx, b_text in enumerate(proposed_raw_bullets):
            clean_b = str(b_text).strip()
            if not clean_b:
                continue
            # Stable bullet id preservation if matching index, or generate new id
            existing_id = target_proj.bullets[idx].id if idx < len(target_proj.bullets) else generate_stable_id("bullet")
            proposed_bullet_objects.append(BulletPoint(
                id=existing_id,
                text=clean_b,
                evidence_ref=f"projects[{target_proj.title}]",
                source_attribution="groq_refined",
                generation_metadata={"model": resp.model, "section": "projects"}
            ).model_dump())

        return SectionRegenerationProposal(
            section="projects",
            entry_id=target_proj.id,
            original_content=original_bullets,
            proposed_content=proposed_bullet_objects,
            rationale=parsed.get("rationale", "Refined project bullets with active STAR engineering verbs."),
            unsupported_claims_rejected=dropped_claims
        )

    # 3. Work Experience
    elif section_lower in ("experience", "work_experience"):
        target_exp = None
        if entry_id:
            for e in resume_content.experience:
                if e.id == entry_id:
                    target_exp = e
                    break
        if not target_exp and resume_content.experience:
            target_exp = resume_content.experience[0]

        if not target_exp:
            raise ValueError("No experience entry found to regenerate.")

        original_bullets = [b.model_dump() for b in target_exp.bullets]
        orig_bullet_texts = [b.text for b in target_exp.bullets] or ([target_exp.description] if target_exp.description else [])

        system_prompt = (
            "You are CareerOS Principal Technical Writer powered by Groq. "
            "STRICT ZERO-FABRICATION RULE: Enhance work experience bullets with active STAR verbs. "
            "Never invent responsibilities, revenue numbers, or tech not in the candidate's verified record. "
            "Output valid JSON."
        )
        prompt = f"""Role: {target_exp.title} at {target_exp.company} (Duration: {target_exp.duration})
Existing Description / Bullets:
{orig_bullet_texts}

Target Job: {target_role} at {target_company}
{instructions_clause}

Produce JSON with:
1. bullets (List of 2-4 professional bullet points starting with strong action verbs)
2. rationale
"""
        resp = await ai_service.router.execute(
            task_type=TaskType.RESUME_TAILORING,
            prompt=prompt,
            system_prompt=system_prompt,
            response_schema=BulletsGenerationOutput,
            temperature=0.2
        )
        parsed = resp.parsed_json or {}
        proposed_raw_bullets = parsed.get("bullets", orig_bullet_texts)

        proposed_bullet_objects = []
        for idx, b_text in enumerate(proposed_raw_bullets):
            clean_b = str(b_text).strip()
            if not clean_b:
                continue
            existing_id = target_exp.bullets[idx].id if idx < len(target_exp.bullets) else generate_stable_id("bullet")
            proposed_bullet_objects.append(BulletPoint(
                id=existing_id,
                text=clean_b,
                evidence_ref=f"experience[{target_exp.company}]",
                source_attribution="groq_refined",
                generation_metadata={"model": resp.model, "section": "experience"}
            ).model_dump())

        return SectionRegenerationProposal(
            section="experience",
            entry_id=target_exp.id,
            original_content=original_bullets,
            proposed_content=proposed_bullet_objects,
            rationale=parsed.get("rationale", "Refined experience bullets with strong action verbs.")
        )

    # 4. Skills Organization
    elif section_lower in ("skills", "technical_skills"):
        original_skills = [s.model_dump() for s in resume_content.skills]
        system_prompt = (
            "You are CareerOS Technical Recruiter powered by Groq. "
            "STRICT ZERO-FABRICATION RULE: Group ONLY the candidate's verified skills into standard ATS categories. "
            "Categories should be: 'Languages', 'Frameworks & Libraries', 'Tools & Platforms', 'Core Competencies'. "
            "NEVER invent or introduce a skill that does not appear in candidate skills. Output valid JSON."
        )
        prompt = f"""Candidate Verified Skills:
{[s.get('name') if isinstance(s, dict) else s for s in candidate_skills]}

Target Job Requirements:
Role: {target_role} at {target_company}
Job Keywords: {target_skills}
{instructions_clause}

Produce JSON with:
1. categorized_skills (List of objects: {{"category": str, "skills": List[str]}})
2. rationale
"""
        resp = await ai_service.router.execute(
            task_type=TaskType.RESUME_TAILORING,
            prompt=prompt,
            system_prompt=system_prompt,
            response_schema=SkillsGroupingOutput,
            temperature=0.1
        )
        parsed = resp.parsed_json or {}
        proposed_groups = parsed.get("categorized_skills", [])

        # Run Zero-Fabrication safety filtering on all skills
        verified_norms = set()
        for s in candidate_skills:
            name = (s.get("name") if isinstance(s, dict) else str(s)).strip().lower()
            if name:
                verified_norms.add(name)

        safe_groups = []
        dropped_unsupported = []
        for g in proposed_groups:
            cat_name = g.get("category", "Technical Skills")
            safe_skills = []
            for s in g.get("skills", []):
                s_str = str(s).strip()
                s_lower = s_str.lower()
                if not s_str:
                    continue
                if s_lower in verified_norms or any(s_lower in vn or vn in s_lower for vn in verified_norms):
                    safe_skills.append(s_str)
                else:
                    dropped_unsupported.append(s_str)
            if safe_skills:
                safe_groups.append({"category": cat_name, "skills": safe_skills})

        return SectionRegenerationProposal(
            section="skills",
            original_content=original_skills,
            proposed_content=safe_groups if safe_groups else original_skills,
            rationale=parsed.get("rationale", "Reorganized verified skills for ATS keyword prominence."),
            unsupported_claims_rejected=dropped_unsupported
        )

    # 5. Achievements
    elif section_lower in ("achievements", "honors"):
        original_achievements = [a.model_dump() for a in resume_content.achievements]
        target_ach = None
        if entry_id:
            for a in resume_content.achievements:
                if a.id == entry_id:
                    target_ach = a
                    break
        if not target_ach and resume_content.achievements:
            target_ach = resume_content.achievements[0]

        if not target_ach:
            raise ValueError("No achievement entry found to regenerate.")

        system_prompt = (
            "You are CareerOS Honors Editor powered by Groq. "
            "STRICT ZERO-FABRICATION RULE: Polish achievement description for clarity and impact. "
            "Preserve factual placement, organization, and award name. Output valid JSON."
        )
        prompt = f"""Honor / Achievement:
Title: {target_ach.title}
Organization: {target_ach.organization} (Year: {target_ach.year})
Existing Description: "{target_ach.description}"
{instructions_clause}

Produce JSON with:
1. description (Enhanced 1-2 sentence description)
2. rationale
"""
        resp = await ai_service.router.execute(
            task_type=TaskType.RESUME_TAILORING,
            prompt=prompt,
            system_prompt=system_prompt,
            response_schema=AchievementGenerationOutput,
            temperature=0.2
        )
        parsed = resp.parsed_json or {}
        proposed_desc = parsed.get("description", target_ach.description)
        return SectionRegenerationProposal(
            section="achievements",
            entry_id=target_ach.id,
            original_content=target_ach.description,
            proposed_content=proposed_desc,
            rationale=parsed.get("rationale", "Enhanced achievement impact description.")
        )

    else:
        raise ValueError(f"Unsupported section for AI regeneration: '{section}'.")
