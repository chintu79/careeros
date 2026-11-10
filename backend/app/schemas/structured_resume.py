import uuid
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


def generate_stable_id(prefix: str = "item") -> str:
    """Generate a clean, stable identifier."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class BulletPoint(BaseModel):
    id: str = Field(default_factory=lambda: generate_stable_id("bullet"))
    text: str = Field(..., min_length=1, max_length=2000, description="The bullet text content")
    evidence_ref: Optional[str] = Field(default=None, description="Reference to candidate profile source entry")
    source_attribution: Optional[str] = Field(default=None, description="Attribution, e.g. candidate_profile, user_manual, groq_refined")
    generation_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Metadata such as action verb, model, timestamp")

    @field_validator("text")
    @classmethod
    def clean_text(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Bullet text cannot be empty or pure whitespace.")
        return s

    @field_validator("id", mode="before")
    @classmethod
    def ensure_id(cls, v: Any) -> str:
        if not v or not str(v).strip():
            return generate_stable_id("bullet")
        return str(v).strip()


class PersonalInfo(BaseModel):
    name: str = Field(..., min_length=1, description="Full candidate name")
    email: str = Field(..., min_length=3, description="Candidate contact email")
    phone: Optional[str] = Field(default="", description="Contact phone number")
    location: Optional[str] = Field(default="", description="Location or city")
    github_url: Optional[str] = Field(default="", description="GitHub profile link")
    linkedin_url: Optional[str] = Field(default="", description="LinkedIn profile link")
    portfolio_url: Optional[str] = Field(default="", description="Portfolio or personal website link")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Name cannot be empty.")
        return s

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        s = v.strip()
        if not s or "@" not in s:
            raise ValueError("Valid email is required.")
        return s


class EducationEntry(BaseModel):
    id: str = Field(default_factory=lambda: generate_stable_id("edu"))
    college: str = Field(..., min_length=1, description="College or University name")
    degree: str = Field(..., min_length=1, description="Degree or program title")
    graduation_year: Optional[Union[int, str]] = Field(default=None, description="Graduation year")
    cgpa: Optional[Union[float, str]] = Field(default=None, description="CGPA or percentage")
    coursework: List[str] = Field(default_factory=list, description="Relevant coursework")

    @field_validator("id", mode="before")
    @classmethod
    def ensure_id(cls, v: Any) -> str:
        if not v or not str(v).strip():
            return generate_stable_id("edu")
        return str(v).strip()


class SkillCategory(BaseModel):
    category: str = Field(..., min_length=1, description="Category name, e.g. Languages, Frameworks, Tools")
    skills: List[str] = Field(default_factory=list, description="List of technical skills in this category")

    @field_validator("skills", mode="before")
    @classmethod
    def clean_skills(cls, v: Any) -> List[str]:
        if not isinstance(v, list):
            return []
        res = []
        for s in v:
            if isinstance(s, dict):
                val = s.get("name", "").strip()
            else:
                val = str(s).strip()
            if val and val not in res:
                res.append(val)
        return res


class ProjectEntry(BaseModel):
    id: str = Field(default_factory=lambda: generate_stable_id("proj"))
    title: str = Field(..., min_length=1, description="Project title")
    tech_stack: List[str] = Field(default_factory=list, description="Technologies used")
    url: Optional[str] = Field(default=None, description="Repository or live deployment link")
    description: Optional[str] = Field(default="", description="High-level summary (optional if bullets present)")
    bullets: List[BulletPoint] = Field(default_factory=list, description="Structured bullet points")

    @field_validator("id", mode="before")
    @classmethod
    def ensure_id(cls, v: Any) -> str:
        if not v or not str(v).strip():
            return generate_stable_id("proj")
        return str(v).strip()

    @field_validator("tech_stack", mode="before")
    @classmethod
    def clean_tech_stack(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        return []

    @field_validator("bullets", mode="before")
    @classmethod
    def normalize_bullets(cls, v: Any) -> List[Any]:
        if not isinstance(v, list):
            return []
        normalized = []
        for b in v:
            if isinstance(b, str):
                normalized.append({"text": b})
            elif isinstance(b, (dict, BulletPoint)):
                normalized.append(b)
            else:
                normalized.append(b)
        return normalized


class ExperienceEntry(BaseModel):
    id: str = Field(default_factory=lambda: generate_stable_id("exp"))
    title: str = Field(..., min_length=1, description="Job title or role")
    company: str = Field(..., min_length=1, description="Company or organization name")
    duration: Optional[str] = Field(default="", description="Employment timeline / dates")
    location: Optional[str] = Field(default="", description="Work location")
    description: Optional[str] = Field(default="", description="Overview description (optional if bullets present)")
    bullets: List[BulletPoint] = Field(default_factory=list, description="Structured bullet points")

    @field_validator("id", mode="before")
    @classmethod
    def ensure_id(cls, v: Any) -> str:
        if not v or not str(v).strip():
            return generate_stable_id("exp")
        return str(v).strip()

    @field_validator("bullets", mode="before")
    @classmethod
    def normalize_bullets(cls, v: Any) -> List[Any]:
        if not isinstance(v, list):
            return []
        normalized = []
        for b in v:
            if isinstance(b, str):
                normalized.append({"text": b})
            elif isinstance(b, (dict, BulletPoint)):
                normalized.append(b)
            else:
                normalized.append(b)
        return normalized


class CertificationEntry(BaseModel):
    id: str = Field(default_factory=lambda: generate_stable_id("cert"))
    name: str = Field(..., min_length=1, description="Certificate title")
    issuer: Optional[str] = Field(default="", description="Issuing organization")
    year: Optional[Union[int, str]] = Field(default="", description="Year issued")
    url: Optional[str] = Field(default=None, description="Verification URL")

    @field_validator("id", mode="before")
    @classmethod
    def ensure_id(cls, v: Any) -> str:
        if not v or not str(v).strip():
            return generate_stable_id("cert")
        return str(v).strip()


class AchievementEntry(BaseModel):
    id: str = Field(default_factory=lambda: generate_stable_id("ach"))
    title: str = Field(..., min_length=1, description="Honor or award title")
    organization: Optional[str] = Field(default="", description="Granting organization")
    year: Optional[Union[int, str]] = Field(default="", description="Year achieved")
    description: Optional[str] = Field(default="", description="Details or metric")

    @field_validator("id", mode="before")
    @classmethod
    def ensure_id(cls, v: Any) -> str:
        if not v or not str(v).strip():
            return generate_stable_id("ach")
        return str(v).strip()


class PublicationEntry(BaseModel):
    id: str = Field(default_factory=lambda: generate_stable_id("pub"))
    title: str = Field(..., min_length=1, description="Paper or publication title")
    venue: Optional[str] = Field(default="", description="Conference, Journal, or Workshop")
    year: Optional[Union[int, str]] = Field(default="", description="Publication year")
    url: Optional[str] = Field(default=None, description="Paper link or DOI")
    authors: List[str] = Field(default_factory=list, description="Authors list")

    @field_validator("id", mode="before")
    @classmethod
    def ensure_id(cls, v: Any) -> str:
        if not v or not str(v).strip():
            return generate_stable_id("pub")
        return str(v).strip()


class AdditionalLink(BaseModel):
    label: str = Field(..., min_length=1, description="Link label, e.g. Medium, LeetCode")
    url: str = Field(..., min_length=4, description="Destination URL")


class StructuredResumeContent(BaseModel):
    """Complete structured representation of resume content, independent of LaTeX layout."""
    personal_info: PersonalInfo
    summary: Optional[str] = Field(default=None, description="Professional summary or profile overview")
    education: List[EducationEntry] = Field(default_factory=list)
    skills: List[SkillCategory] = Field(default_factory=list)
    projects: List[ProjectEntry] = Field(default_factory=list)
    experience: List[ExperienceEntry] = Field(default_factory=list)
    certifications: List[CertificationEntry] = Field(default_factory=list)
    achievements: List[AchievementEntry] = Field(default_factory=list)
    publications: List[PublicationEntry] = Field(default_factory=list)
    additional_links: List[AdditionalLink] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Optional layout or configuration metadata")

    @field_validator("summary")
    @classmethod
    def clean_summary(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        return s if s else None


class StructuredSectionUpdateRequest(BaseModel):
    """
    Partial section update request.
    Only specified sections are updated; untouched sections remain strictly preserved.
    """
    expected_version: Optional[int] = Field(
        default=None,
        description="Current resume version for optimistic concurrency control"
    )
    change_summary: Optional[str] = Field(
        default="Updated structured resume sections",
        description="Version change audit summary"
    )
    target_page_count: Optional[int] = Field(
        default=None,
        description="Optional target page count override (1 or 2)"
    )
    page_size: Optional[str] = Field(
        default=None,
        description="Optional page size override ('letter' or 'a4')"
    )
    personal_info: Optional[PersonalInfo] = None
    summary: Optional[str] = None
    education: Optional[List[EducationEntry]] = None
    skills: Optional[List[SkillCategory]] = None
    projects: Optional[List[ProjectEntry]] = None
    experience: Optional[List[ExperienceEntry]] = None
    certifications: Optional[List[CertificationEntry]] = None
    achievements: Optional[List[AchievementEntry]] = None
    publications: Optional[List[PublicationEntry]] = None
    additional_links: Optional[List[AdditionalLink]] = None

    @field_validator("summary")
    @classmethod
    def clean_summary(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        return s if s else None


class CompileResumeRequest(BaseModel):
    """Request payload for compiling a resume with optional layout budgeting parameters."""
    target_page_count: Optional[int] = Field(
        default=None,
        description="Optional target page count override (1 or 2)"
    )
    page_size: Optional[str] = Field(
        default=None,
        description="Optional page size override ('letter' or 'a4')"
    )


class SectionRegenerateRequest(BaseModel):
    """Request for individual section AI regeneration."""
    section: str = Field(..., description="Section to regenerate: summary, projects, experience, skills, achievements")
    entry_id: Optional[str] = Field(default=None, description="Specific project or experience entry ID to regenerate")
    opportunity_id: Optional[int] = Field(default=None, description="Target opportunity ID for tailoring context")
    user_instructions: Optional[str] = Field(default=None, description="Specific guidance or emphasis from candidate")


class SectionRegenerationProposal(BaseModel):
    """Proposal returned by section regenerator without modifying stored state."""
    section: str
    entry_id: Optional[str] = None
    original_content: Any
    proposed_content: Any
    rationale: str
    unsupported_claims_rejected: List[str] = Field(default_factory=list)


def profile_to_structured_resume(profile_data: Dict[str, Any]) -> StructuredResumeContent:
    """Builds a StructuredResumeContent model from candidate profile dictionary."""
    personal = PersonalInfo(
        name=profile_data.get("name") or "Candidate",
        email=profile_data.get("email") or "candidate@example.com",
        phone=profile_data.get("phone") or "",
        location=profile_data.get("location") or "",
        github_url=profile_data.get("github_url") or "",
        linkedin_url=profile_data.get("linkedin_url") or "",
        portfolio_url=profile_data.get("portfolio_url") or ""
    )

    edu_list = []
    if profile_data.get("college") or profile_data.get("degree"):
        edu_list.append(EducationEntry(
            id=generate_stable_id("edu"),
            college=profile_data.get("college") or "",
            degree=profile_data.get("degree") or "",
            graduation_year=profile_data.get("graduation_year"),
            cgpa=profile_data.get("cgpa")
        ))

    skills_raw = profile_data.get("skills", []) or []
    cat_map: Dict[str, List[str]] = {
        "Languages": [],
        "Frameworks & Libraries": [],
        "Tools & Platforms": [],
        "Core Competencies": []
    }
    for s in skills_raw:
        s_name = s.get("name", "") if isinstance(s, dict) else str(s)
        s_name = s_name.strip()
        if not s_name:
            continue
        s_cat = (s.get("category", "") if isinstance(s, dict) else "").lower()
        if any(k in s_cat for k in ["lang", "language"]):
            if s_name not in cat_map["Languages"]:
                cat_map["Languages"].append(s_name)
        elif any(k in s_cat for k in ["framework", "lib", "frontend", "backend", "web"]):
            if s_name not in cat_map["Frameworks & Libraries"]:
                cat_map["Frameworks & Libraries"].append(s_name)
        elif any(k in s_cat for k in ["tool", "platform", "cloud", "devops", "db", "database"]):
            if s_name not in cat_map["Tools & Platforms"]:
                cat_map["Tools & Platforms"].append(s_name)
        else:
            if s_name not in cat_map["Core Competencies"]:
                cat_map["Core Competencies"].append(s_name)

    skill_cats = [
        SkillCategory(category=cat, skills=items)
        for cat, items in cat_map.items()
        if items
    ]

    projs_list = []
    for idx, p in enumerate(profile_data.get("projects", []) or []):
        p_bullets = []
        raw_bullets = p.get("bullets", [])
        if raw_bullets:
            for b_idx, b in enumerate(raw_bullets):
                b_text = b.get("text", "") if isinstance(b, dict) else str(b)
                if b_text.strip():
                    p_bullets.append(BulletPoint(
                        id=f"proj_{idx}_b_{b_idx}",
                        text=b_text.strip(),
                        evidence_ref=f"projects[{idx}]",
                        source_attribution="candidate_profile"
                    ))
        elif p.get("description"):
            p_bullets.append(BulletPoint(
                id=f"proj_{idx}_b_0",
                text=p["description"].strip(),
                evidence_ref=f"projects[{idx}]",
                source_attribution="candidate_profile"
            ))

        projs_list.append(ProjectEntry(
            id=p.get("id") or f"proj_{idx}",
            title=p.get("title", ""),
            tech_stack=p.get("tech_stack", []) or [],
            url=p.get("url") or "",
            description=p.get("description") or "",
            bullets=p_bullets
        ))

    exp_list = []
    for idx, e in enumerate(profile_data.get("experience", []) or []):
        e_bullets = []
        raw_bullets = e.get("bullets", [])
        if raw_bullets:
            for b_idx, b in enumerate(raw_bullets):
                b_text = b.get("text", "") if isinstance(b, dict) else str(b)
                if b_text.strip():
                    e_bullets.append(BulletPoint(
                        id=f"exp_{idx}_b_{b_idx}",
                        text=b_text.strip(),
                        evidence_ref=f"experience[{idx}]",
                        source_attribution="candidate_profile"
                    ))
        elif e.get("description"):
            e_bullets.append(BulletPoint(
                id=f"exp_{idx}_b_0",
                text=e["description"].strip(),
                evidence_ref=f"experience[{idx}]",
                source_attribution="candidate_profile"
            ))

        exp_list.append(ExperienceEntry(
            id=e.get("id") or f"exp_{idx}",
            title=e.get("title", ""),
            company=e.get("company", ""),
            duration=e.get("duration", "") or "",
            location=e.get("location", "") or "",
            description=e.get("description") or "",
            bullets=e_bullets
        ))

    certs_list = [
        CertificationEntry(
            id=c.get("id") or f"cert_{idx}",
            name=c.get("name", ""),
            issuer=c.get("issuer", "") or "",
            year=c.get("year", "") or "",
            url=c.get("url")
        )
        for idx, c in enumerate(profile_data.get("certifications", []) or [])
        if c.get("name")
    ]

    achs_list = [
        AchievementEntry(
            id=a.get("id") or f"ach_{idx}",
            title=a.get("title", ""),
            organization=a.get("organization", "") or "",
            year=a.get("year", "") or "",
            description=a.get("description", "") or ""
        )
        for idx, a in enumerate(profile_data.get("achievements", []) or [])
        if a.get("title")
    ]

    return StructuredResumeContent(
        personal_info=personal,
        summary=profile_data.get("summary"),
        education=edu_list,
        skills=skill_cats,
        projects=projs_list,
        experience=exp_list,
        certifications=certs_list,
        achievements=achs_list,
        publications=[],
        additional_links=[]
    )
