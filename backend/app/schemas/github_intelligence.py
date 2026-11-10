from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class RepositoryAnalysisState(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    STALE = "stale"
    ANALYSIS_UNAVAILABLE = "analysis_unavailable"


class EvidenceCategory(str, Enum):
    DIRECTLY_OBSERVED = "directly_observed"       # Category A: Manifests, git tree, commits, README, language stats
    AI_DERIVED = "ai_derived"                     # Category B: Architecture, purpose, trade-offs
    CANDIDATE_ATTRIBUTED = "candidate_attributed" # Category C: Authenticated commit/author evidence
    UNVERIFIED = "unverified"                     # Category D: Unsupported or unproven claims


class TechnologyEvidence(BaseModel):
    name: str = Field(..., description="Technology, library, or framework name")
    category: str = Field(..., description="Category: Language, Framework, Database, Testing, CI/CD, Containerization, Tooling")
    source_file: str = Field(..., description="Manifest or config file path where evidence was found")
    confidence: str = Field(default="high", description="Confidence rating: high, medium, inferred")
    version: Optional[str] = Field(default=None, description="Specified version constraint if available")
    evidence_id: str = Field(default="", description="Unique deterministic evidence identifier (e.g. tech_fastapi)")


class StructureEvidence(BaseModel):
    signal_name: str = Field(..., description="Name of structural pattern detected")
    detected: bool = Field(default=True, description="Whether pattern was confirmed present")
    evidence_paths: List[str] = Field(default_factory=list, description="Observed paths matching pattern")
    observed_description: str = Field(default="", description="Factual description of observed structure")
    evidence_id: str = Field(default="", description="Unique structural pattern identifier (e.g. struct_api_routing)")


class RepositoryCommitMetadata(BaseModel):
    sha: str = Field(..., description="Short commit SHA")
    message: str = Field(..., description="Commit message header")
    author_name: str = Field(default="Unknown", description="Commit author name")
    author_email: Optional[str] = Field(default=None, description="Commit author email if available")
    author_date: Optional[str] = Field(default=None, description="ISO timestamp of commit")
    evidence_id: str = Field(default="", description="Unique commit identifier (e.g. commit_abc1234)")


class GroundedClaim(BaseModel):
    claim_text: str = Field(..., description="The factual or architectural claim")
    category: EvidenceCategory = Field(default=EvidenceCategory.AI_DERIVED, description="Evidence provenance category")
    evidence_ids: List[str] = Field(default_factory=list, description="Referenced evidence IDs supporting this claim")
    supporting_paths: List[str] = Field(default_factory=list, description="Source files or directory paths providing proof")
    is_verified: bool = Field(default=False, description="Whether claim is verified by directly observed evidence")
    confidence: str = Field(default="medium", description="high, medium, or unverified")


class GitHubProjectAnalysisOutput(BaseModel):
    project_purpose: str = Field(description="Core purpose and problem solved by this project")
    main_technical_architecture: str = Field(description="Architectural design, system components, and structure")
    key_features: List[str] = Field(default_factory=list, description="Core technical capabilities implemented")
    technology_stack: List[str] = Field(default_factory=list, description="Verified languages, frameworks, and databases")
    engineering_decisions_and_tradeoffs: List[str] = Field(default_factory=list, description="Notable design decisions and engineering trade-offs")
    candidate_contribution_evidence: str = Field(description="Observed contribution evidence or unverified note")
    candidate_contribution_verified: bool = Field(default=False, description="Whether candidate contribution is backed by verified author/commit evidence")
    technical_strengths_demonstrated: List[str] = Field(default_factory=list, description="Demonstrated engineering competencies")
    missing_or_unclear_information: List[str] = Field(default_factory=list, description="Gaps in documentation, test coverage, or architecture")
    suggested_improvements: List[str] = Field(default_factory=list, description="Concrete engineering enhancements")
    grounded_claims: List[GroundedClaim] = Field(default_factory=list, description="Individual technical claims with evidence provenance")
    referenced_evidence_ids: List[str] = Field(default_factory=list, description="List of evidence IDs referenced from repository evidence")


class GitHubProjectIntelligence(BaseModel):
    repo_name: str
    full_name: str
    html_url: str
    description: Optional[str] = ""
    default_branch: str = "main"
    is_fork: bool = False
    is_archived: bool = False
    visibility: str = "public"
    primary_language: Optional[str] = None
    languages: Dict[str, int] = Field(default_factory=dict)
    topics: List[str] = Field(default_factory=list)
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    license: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    pushed_at: Optional[str] = None
    
    # Deterministic signals
    detected_technologies: List[TechnologyEvidence] = Field(default_factory=list)
    structure_signals: List[StructureEvidence] = Field(default_factory=list)
    recent_commits: List[RepositoryCommitMetadata] = Field(default_factory=list)
    readme_summary: Optional[str] = None
    
    # AI-Derived interpretation
    ai_insights: Optional[Dict[str, Any]] = None
    
    # State tracking & cache
    status: RepositoryAnalysisState = RepositoryAnalysisState.COMPLETED
    content_hash: Optional[str] = None
    last_synced_at: Optional[str] = None
    error_message: Optional[str] = None
    is_cached: bool = False
    is_stale: bool = False
    token_status: Optional[str] = None


# API Request/Response Models
class GitHubSyncRequest(BaseModel):
    username: Optional[str] = None
    force_refresh: bool = False


class GitHubTokenRequest(BaseModel):
    token: str = Field(..., min_length=4, description="GitHub Personal Access Token")


class GitHubImportRequest(BaseModel):
    repo_urls: List[str] = Field(..., min_length=1, description="Repository URLs to import as candidate projects")
    overwrite_curated: bool = Field(default=False, description="Strict safety guard; defaults to False to prevent overwriting manual edits")
