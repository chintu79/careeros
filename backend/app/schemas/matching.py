from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class RequirementPriority(str, Enum):
    MANDATORY = "mandatory"
    PREFERRED = "preferred"
    OPTIONAL = "optional"


class MatchStatus(str, Enum):
    STRONG_MATCH = "strong_match"
    PARTIAL_MATCH = "partial_match"
    WEAK_MATCH = "weak_match"
    NO_EVIDENCE = "no_evidence"
    NOT_APPLICABLE = "not_applicable"


class EvidenceProvenanceType(str, Enum):
    MANUAL_SKILL = "manual_skill"
    GITHUB_MANIFEST = "github_manifest"
    GITHUB_TOPOLOGY = "github_topology"
    GITHUB_COMMIT = "github_commit"
    CURATED_PROJECT = "curated_project"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    CERTIFICATION = "certification"
    AI_DERIVED_PROJECT = "ai_derived_project"


class ExtractedRequirement(BaseModel):
    name: str = Field(description="Normalized requirement or skill name")
    category: str = Field(description="Category: language, framework, database, cloud_devops, education, experience, certification, soft_skill")
    priority: RequirementPriority = Field(default=RequirementPriority.MANDATORY, description="Mandatory, Preferred, or Optional")
    source_text: str = Field(default="", description="Verbatim source sentence or snippet from job description")
    evidence_reference: str = Field(default="", description="Reference identifier for traceability")


class ParsedJobDescription(BaseModel):
    job_title: str = Field(default="", description="Job title")
    company: Optional[str] = Field(default=None, description="Hiring company name")
    role_category: str = Field(default="software_engineering", description="Classified role category")
    experience_requirements: str = Field(default="0-1 years / Fresher", description="Stated experience constraints")
    mandatory_skills: List[str] = Field(default_factory=list, description="Mandatory technical skills")
    preferred_skills: List[str] = Field(default_factory=list, description="Preferred technical skills")
    programming_languages: List[str] = Field(default_factory=list, description="Extracted programming languages")
    frameworks_libraries: List[str] = Field(default_factory=list, description="Extracted frameworks and libraries")
    database_technologies: List[str] = Field(default_factory=list, description="Extracted databases and storage")
    cloud_devops: List[str] = Field(default_factory=list, description="Extracted cloud and devops tools")
    education_requirements: str = Field(default="", description="Stated educational prerequisites")
    certifications: List[str] = Field(default_factory=list, description="Certifications requested")
    responsibilities: List[str] = Field(default_factory=list, description="Key duties and deliverables")
    location: Optional[str] = Field(default=None, description="Stated location")
    work_mode: str = Field(default="remote", description="remote, hybrid, or onsite")
    employment_type: str = Field(default="internship", description="internship, entry_level, full_time")
    requirements: List[ExtractedRequirement] = Field(default_factory=list, description="Individual extracted requirements with provenance")
    content_hash: str = Field(default="", description="SHA-256 hash of opportunity description")


class CandidateEvidenceItem(BaseModel):
    name: str = Field(description="Raw skill or item name")
    canonical_name: str = Field(description="Normalized canonical identifier")
    provenance: EvidenceProvenanceType = Field(description="Source of candidate evidence")
    source_identifier: str = Field(description="Traceable reference e.g. manifest filename, repo, project ID")
    evidence_text: str = Field(default="", description="Supporting factual context or snippet")
    is_verified: bool = Field(default=True, description="Whether supported by direct verified source (never AI-derived alone)")
    proficiency: Optional[str] = Field(default=None, description="Optional level: beginner, intermediate, advanced")


class UnifiedCandidateEvidence(BaseModel):
    candidate_id: Optional[int] = Field(default=None, description="Candidate profile ID")
    user_id: int = Field(description="Associated User ID")
    evidence_items: List[CandidateEvidenceItem] = Field(default_factory=list, description="Aggregated candidate evidence units")
    education: Dict[str, Any] = Field(default_factory=dict, description="Degrees, college, graduation year, CGPA")
    experience_years: float = Field(default=0.0, description="Estimated total verified professional experience in years")
    certifications: List[str] = Field(default_factory=list, description="Verified candidate certifications")
    content_hash: str = Field(default="", description="SHA-256 hash of unified candidate evidence")


class RequirementMatchResult(BaseModel):
    requirement: ExtractedRequirement = Field(description="Target job requirement")
    status: MatchStatus = Field(description="Match rating: strong_match, partial_match, weak_match, no_evidence, not_applicable")
    matched_evidence: List[CandidateEvidenceItem] = Field(default_factory=list, description="Candidate evidence supporting this requirement")
    evidence_strength: float = Field(ge=0.0, le=1.0, description="Numerical strength: 1.0=exact, 0.5-0.65=related, 0.35=transferable, 0=none")
    confidence: str = Field(default="high", description="high, medium, low, unverified")
    match_type: str = Field(description="exact, related, transferable, mismatch, none")
    explanation: str = Field(description="Human-readable justification for the match rating")
    missing_evidence_description: Optional[str] = Field(default=None, description="Specific details of what evidence is lacking")


class SkillGap(BaseModel):
    skill_name: str = Field(description="Missing or insufficient required skill")
    priority: RequirementPriority = Field(description="Mandatory or Preferred")
    current_evidence: Optional[str] = Field(default=None, description="Candidate's current partial/related evidence if any")
    missing_evidence: str = Field(description="Precise description of missing evidence")
    suggested_learning_or_improvement: str = Field(description="Concrete actionable recommendation")


class ProfileMatchResult(BaseModel):
    profile_match_score: float = Field(ge=0.0, le=100.0, description="Explainable composite score (Profile Match Score, 0-100)")
    category_scores: Dict[str, float] = Field(description="Individual scores per category")
    category_weights: Dict[str, float] = Field(description="Configured weights per category")
    requirement_matches: List[RequirementMatchResult] = Field(default_factory=list, description="Fine-grained match evaluations")
    skill_gaps: List[SkillGap] = Field(default_factory=list, description="Identified skill gaps with concrete recommendations")
    eligibility_status: str = Field(default="eligible", description="eligible, flagged, or disqualified")
    disqualifying_reasons: List[str] = Field(default_factory=list, description="Reasons for flagging or disqualification")
    scoring_explanation: str = Field(description="Full step-by-step mathematical explanation of the match score")
    candidate_content_hash: str = Field(description="SHA-256 hash of candidate evidence inputs used")
    opportunity_content_hash: str = Field(description="SHA-256 hash of opportunity inputs used")
    calculated_at: str = Field(description="ISO timestamp of calculation")
    is_stale: bool = Field(default=False, description="Whether previous calculation was preserved after a failure")
    is_cached: bool = Field(default=False, description="Whether result was served directly from cache")
    engine_version: str = Field(default="2.0.0", description="Matching engine algorithm and taxonomy version")
    user_id: Optional[int] = Field(default=None, description="Candidate User ID who owns this match result")
