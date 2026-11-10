from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import os
from fastapi import APIRouter, Depends, HTTPException, Body, File, UploadFile, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from backend.app.database import get_db
from backend.app.services.rate_limit import rate_limited
from backend.app.models.candidate import CandidateProfile
from backend.app.services.discovery_snapshot_manager import snapshot_manager
from backend.app.services.integration_service import (
    fetch_github_profile_data, 
    fetch_portfolio_data,
    parse_resume_file
)

from backend.app.services.profile_completion_service import assess_candidate_profile_completeness
from backend.app.services.matching.taxonomy import canonicalize_tech_name, CANONICAL_ALIASES

from backend.app.core.auth import get_current_user_id

router = APIRouter(prefix="/candidate", tags=["Master Candidate Profile"])

class CandidateUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = None
    degree: Optional[str] = None
    graduation_year: Optional[int] = None
    college: Optional[str] = None
    cgpa: Optional[float] = None
    github_url: Optional[str] = None
    github_username: Optional[str] = None
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    website_url: Optional[str] = None
    skills: Optional[List[Dict[str, Any]]] = None
    projects: Optional[List[Dict[str, Any]]] = None
    experience: Optional[List[Dict[str, Any]]] = None
    certifications: Optional[List[Dict[str, Any]]] = None
    achievements: Optional[List[Dict[str, Any]]] = None
    extracurriculars: Optional[List[Dict[str, Any]]] = None
    preferred_locations: Optional[List[str]] = None
    work_authorization: Optional[str] = None
    onboarding_status: Optional[str] = None
    onboarding_step: Optional[int] = None
    career_goals: Optional[Dict[str, Any]] = None

class OnboardingProgressRequest(BaseModel):
    step: int
    status: Optional[str] = "in_progress"
    career_goals: Optional[Dict[str, Any]] = None
    profile_data: Optional[Dict[str, Any]] = None

class SkillCreateRequest(BaseModel):
    name: str
    category: Optional[str] = "General"
    level: Optional[str] = "intermediate"
    evidence: Optional[str] = ""

class ProjectCreateRequest(BaseModel):
    title: str
    description: str
    tech_stack: Optional[List[str]] = None
    url: Optional[str] = ""
    stars: Optional[int] = 0
    index: Optional[int] = None

import re
import logging
from backend.app.schemas.github_intelligence import (
    GitHubSyncRequest,
    GitHubTokenRequest,
    GitHubImportRequest
)
from backend.app.services.github import (
    github_intelligence_service,
    save_github_token_for_user,
    delete_github_token_for_user,
    get_github_token_for_user,
    GitHubApiClient,
    GitHubTokenRevokedError
)

logger = logging.getLogger(__name__)


def sanitize_error_message(err_str: str) -> str:
    """Removes tokens, passwords, or credentials from error messages."""
    return re.sub(
        r'(ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{82}|Bearer\s+[a-zA-Z0-9_\-\.]+|token\s+[a-zA-Z0-9_\-\.]+)',
        '[REDACTED_TOKEN]',
        str(err_str)
    )

class PortfolioSyncRequest(BaseModel):
    url: str

class LinkedInImportRequest(BaseModel):
    profile_url: Optional[str] = None
    headline: Optional[str] = None
    skills: Optional[List[str]] = None
    experience: Optional[List[Dict[str, Any]]] = None
    education: Optional[str] = None

class ApproveIntegrationsRequest(BaseModel):
    approved_skills: Optional[List[Dict[str, Any]]] = None
    approved_projects: Optional[List[Dict[str, Any]]] = None
    candidate_updates: Optional[Dict[str, Any]] = None


@router.get("")
def get_candidate_profile(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Fetch the centralized Master Candidate Profile scoped to the authenticated user."""
    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    if not cand:
        cand = CandidateProfile(user_id=user_id)
        db.add(cand)
        db.commit()
        db.refresh(cand)
    return cand

@router.put("")
def update_candidate_profile(data: CandidateUpdate, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Update Master Candidate Profile fields and collections for the authenticated user."""
    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    if not cand:
        cand = CandidateProfile(user_id=user_id)
        db.add(cand)
        
    for field, val in data.model_dump(exclude_unset=True).items():
        if val is not None:
            setattr(cand, field, val)
            
    cand.evidence_version = (cand.evidence_version or 1) + 1
    cand.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    snapshot_manager.invalidate_candidate_snapshots(user_id=cand.user_id, db=db)
    db.refresh(cand)
    return cand

@router.get("/completeness")
def get_candidate_completeness(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Evaluates candidate profile completeness and evidence readiness using persisted records.
    Distinguishes verified evidence from unverified self-reported claims.
    """
    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    return assess_candidate_profile_completeness(cand, db)

@router.put("/onboarding-progress")
def save_onboarding_progress(
    req: OnboardingProgressRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Saves progressive candidate onboarding steps, career goals, and form field inputs.
    Allows incomplete onboarding journeys to be resumed smoothly.
    """
    if req.step < 1 or req.step > 6:
        raise HTTPException(status_code=400, detail="Onboarding step must be between 1 and 6.")

    if req.status and req.status not in ("not_started", "in_progress", "completed"):
        raise HTTPException(status_code=400, detail="Invalid onboarding status.")

    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    if not cand:
        cand = CandidateProfile(user_id=user_id)
        db.add(cand)

    cand.onboarding_step = req.step
    if req.status:
        cand.onboarding_status = req.status
    if req.career_goals is not None:
        cand.career_goals = req.career_goals

    if req.profile_data:
        allowed_fields = [
            "name", "email", "phone", "location", "bio", "degree",
            "graduation_year", "college", "cgpa", "github_url", "github_username",
            "linkedin_url", "portfolio_url", "website_url", "skills", "projects",
            "experience", "certifications", "achievements", "preferred_locations",
            "work_authorization"
        ]
        for field in allowed_fields:
            if field in req.profile_data and req.profile_data[field] is not None:
                setattr(cand, field, req.profile_data[field])
                if field in ["career_goals", "skills", "projects", "experience", "certifications", "achievements"]:
                    flag_modified(cand, field)

    if req.career_goals is not None:
        flag_modified(cand, "career_goals")

    cand.evidence_version = (cand.evidence_version or 1) + 1
    cand.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    snapshot_manager.invalidate_candidate_snapshots(user_id=cand.user_id, db=db)
    db.refresh(cand)
    return {
        "status": "success",
        "onboarding_step": cand.onboarding_step,
        "onboarding_status": cand.onboarding_status,
        "candidate": cand
    }

@router.post("/complete-onboarding")
def complete_candidate_onboarding(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Finalizes candidate onboarding, activates profile, advances evidence version,
    and invalidates stale discovery ranking snapshots so fresh evidence takes effect immediately.
    """
    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    if not cand:
        cand = CandidateProfile(user_id=user_id)
        db.add(cand)

    was_completed = (cand.onboarding_status == "completed" and cand.onboarding_step == 6)
    cand.onboarding_status = "completed"
    cand.onboarding_step = 6

    if not was_completed:
        cand.evidence_version = (cand.evidence_version or 1) + 1
        cand.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        snapshot_manager.invalidate_candidate_snapshots(user_id=cand.user_id, db=db)
        db.refresh(cand)
    else:
        db.commit()
        db.refresh(cand)

    readiness = assess_candidate_profile_completeness(cand, db)
    return {
        "status": "completed",
        "message": "Candidate profile successfully activated for personalized opportunity discovery.",
        "evidence_version": cand.evidence_version,
        "readiness": readiness
    }

@router.get("/skills/taxonomy")
def get_skills_taxonomy():
    """
    Returns canonical technology taxonomy, categories, and aliases for autocomplete.
    Ensures consistent canonical naming without duplicating database tables.
    """
    categories = {
        "Languages": ["Python", "JavaScript", "TypeScript", "Go", "Rust", "Java", "C++", "C", "C#", "Kotlin", "Swift", "SQL"],
        "Frameworks": ["React", "Next.js", "Vue.js", "Angular", "Node.js", "Express", "FastAPI", "Django", "Flask", "Spring Boot", "NestJS", "Tailwind CSS"],
        "Databases": ["PostgreSQL", "MySQL", "MongoDB", "Redis", "SQLite"],
        "Cloud & DevOps": ["Docker", "Kubernetes", "AWS", "GCP", "Azure", "CI/CD", "GitHub Actions", "Terraform", "Linux"],
        "Architecture & APIs": ["REST API", "GraphQL", "Kafka"],
        "AI & Machine Learning": ["PyTorch", "TensorFlow", "Scikit-Learn", "Pandas", "NumPy"]
    }
    return {
        "categories": categories,
        "canonical_aliases": CANONICAL_ALIASES
    }

@router.post("/skills")
def add_or_update_candidate_skill(
    req: SkillCreateRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Adds or updates a canonical technical skill with category and evidence linkage.
    """
    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    if not cand:
        cand = CandidateProfile(user_id=user_id)
        db.add(cand)

    canon_name = canonicalize_tech_name(req.name)
    if not canon_name:
        raise HTTPException(status_code=400, detail="Skill name cannot be empty")

    curr_skills = list(cand.skills or [])
    updated = False
    for s in curr_skills:
        if isinstance(s, dict) and canonicalize_tech_name(s.get("name", "")).lower() == canon_name.lower():
            s["name"] = canon_name
            s["category"] = req.category or s.get("category", "General")
            s["level"] = req.level or s.get("level", "intermediate")
            if req.evidence:
                s["evidence"] = req.evidence
            updated = True
            break

    if not updated:
        curr_skills.append({
            "name": canon_name,
            "category": req.category or "General",
            "level": req.level or "intermediate",
            "evidence": req.evidence or ""
        })

    cand.skills = curr_skills
    flag_modified(cand, "skills")
    cand.evidence_version = (cand.evidence_version or 1) + 1
    cand.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    snapshot_manager.invalidate_candidate_snapshots(user_id=cand.user_id, db=db)
    db.refresh(cand)
    return cand

@router.delete("/skills/{skill_name}")
def delete_candidate_skill(
    skill_name: str,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Deletes a skill from the candidate profile and invalidates active snapshots.
    """
    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate profile not found")

    target_clean = canonicalize_tech_name(skill_name).lower()
    curr_skills = [
        s for s in (cand.skills or [])
        if isinstance(s, dict) and canonicalize_tech_name(s.get("name", "")).lower() != target_clean
    ]
    cand.skills = curr_skills
    flag_modified(cand, "skills")
    cand.evidence_version = (cand.evidence_version or 1) + 1
    cand.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    snapshot_manager.invalidate_candidate_snapshots(user_id=cand.user_id, db=db)
    db.refresh(cand)
    return cand

@router.post("/projects")
def add_or_update_candidate_project(
    req: ProjectCreateRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Adds or updates a candidate project with validated tech stack tags.
    Preserves all existing projects and their relationships.
    """
    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    if not cand:
        cand = CandidateProfile(user_id=user_id)
        db.add(cand)

    if not req.title.strip():
        raise HTTPException(status_code=400, detail="Project title cannot be empty")

    curr_projects = list(cand.projects or [])
    normalized_tech = [canonicalize_tech_name(t) for t in (req.tech_stack or []) if t.strip()]

    project_obj = {
        "title": req.title.strip(),
        "description": req.description.strip(),
        "tech_stack": normalized_tech,
        "url": (req.url or "").strip(),
        "stars": req.stars or 0
    }

    if req.index is not None and 0 <= req.index < len(curr_projects):
        curr_projects[req.index] = project_obj
    else:
        existing_idx = None
        clean_title = req.title.strip().lower()
        for i, p in enumerate(curr_projects):
            if isinstance(p, dict) and p.get("title", "").strip().lower() == clean_title:
                existing_idx = i
                break
        if existing_idx is not None:
            curr_projects[existing_idx] = project_obj
        else:
            curr_projects.append(project_obj)

    cand.projects = curr_projects
    flag_modified(cand, "projects")
    cand.evidence_version = (cand.evidence_version or 1) + 1
    cand.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    snapshot_manager.invalidate_candidate_snapshots(user_id=cand.user_id, db=db)
    db.refresh(cand)
    return cand

@router.delete("/projects/{project_index}")
def delete_candidate_project(
    project_index: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Removes a project by index and advances evidence version.
    """
    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate profile not found")

    curr_projects = list(cand.projects or [])
    if project_index < 0 or project_index >= len(curr_projects):
        raise HTTPException(status_code=404, detail=f"Project index {project_index} out of range")

    curr_projects.pop(project_index)
    cand.projects = curr_projects
    flag_modified(cand, "projects")
    cand.evidence_version = (cand.evidence_version or 1) + 1
    cand.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    snapshot_manager.invalidate_candidate_snapshots(user_id=cand.user_id, db=db)
    db.refresh(cand)
    return cand

@router.post("/integrations/github")
async def sync_github_profile(req: GitHubSyncRequest, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Retrieve public repositories and technical languages via GitHub API."""
    try:
        data = await fetch_github_profile_data(req.username)
        cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
        if cand:
            cand.github_username = req.username
            cand.github_url = f"https://github.com/{req.username}"
            cand.github_data = data
            cand.evidence_version = (cand.evidence_version or 1) + 1
            cand.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
            snapshot_manager.invalidate_candidate_snapshots(user_id=cand.user_id, db=db)
            db.refresh(cand)
        return data
    except ValueError as e:
        # SSRF / URL-validation rejections are intentional and safe to surface.
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("GitHub sync failed")
        raise HTTPException(status_code=400, detail="Portfolio import failed.")

@router.post("/integrations/github/sync")
async def sync_github_repositories(
    req: Optional[GitHubSyncRequest] = None,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Triggers deep GitHub repository intelligence analysis for the candidate's public repositories.
    Extracts deterministic manifest dependencies, topological signals, and Groq cloud architecture reasoning.
    """
    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate profile not found")

    username = (req.username if req and req.username else None) or cand.github_username
    if not username and cand.github_url:
        username = cand.github_url.rstrip("/").split("/")[-1]

    if not username:
        raise HTTPException(
            status_code=400,
            detail="GitHub username is required. Please provide username in request or save it in your profile."
        )

    force_refresh = req.force_refresh if req else False
    try:
        results = await github_intelligence_service.sync_candidate_repositories(
            user_id=user_id,
            username=username,
            db=db,
            force_refresh=force_refresh
        )
        return {
            "status": "completed",
            "username": username,
            "repositories_analyzed": len(results),
            "repositories": results
        }
    except GitHubTokenRevokedError as tre:
        logger.warning(f"GitHub token revoked for user {user_id}: {tre}")
        raise HTTPException(
            status_code=401,
            detail={"status": "reconnect_required", "message": "GitHub access token has been revoked or expired. Please reconnect."}
        )
    except Exception as e:
        logger.error(f"GitHub repository sync failed for user {user_id}: {sanitize_error_message(str(e))}")
        raise HTTPException(status_code=500, detail=sanitize_error_message(str(e)))

@router.get("/integrations/github/repositories")
def get_candidate_github_repositories(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Lists analyzed repositories and engineering intelligence summaries for the candidate.
    """
    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate profile not found")

    github_data = cand.github_data or {}
    intel_map = github_data.get("intelligence", {})
    repositories = list(intel_map.values())
    has_token = bool(get_github_token_for_user(user_id, db))

    return {
        "username": cand.github_username,
        "github_url": cand.github_url,
        "last_synced_at": github_data.get("last_synced_at"),
        "has_custom_token": has_token,
        "rate_limit": github_data.get("rate_limit"),
        "token_status": github_data.get("token_status"),
        "repositories_count": len(repositories),
        "repositories": repositories
    }

@router.get("/integrations/github/repositories/{owner}/{repo}")
async def get_repository_intelligence(
    owner: str,
    repo: str,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Returns deep technical intelligence and engineering evidence for a specific repository.
    """
    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate profile not found")

    full_name = f"{owner}/{repo}".lower()
    github_data = cand.github_data or {}
    intel_map = github_data.get("intelligence", {})
    
    for fname, item in intel_map.items():
        if fname.lower() == full_name:
            return item

    try:
        token = get_github_token_for_user(user_id, db)
        client = GitHubApiClient(token=token)
        intel = await github_intelligence_service.collect_repository_intelligence(
            owner=owner,
            repo=repo,
            client=client,
            candidate_name=cand.name
        )
        return intel
    except GitHubTokenRevokedError as tre:
        logger.warning(f"GitHub token revoked for user {user_id}: {tre}")
        raise HTTPException(
            status_code=401,
            detail={"status": "reconnect_required", "message": "GitHub access token has been revoked or expired. Please reconnect."}
        )
    except Exception as e:
        logger.error(f"Failed to fetch repository intelligence for {owner}/{repo}: {sanitize_error_message(str(e))}")
        raise HTTPException(status_code=404, detail=f"Repository {owner}/{repo} not found or inaccessible: {sanitize_error_message(str(e))}")

@router.post("/integrations/github/repositories/{owner}/{repo}/refresh")
async def refresh_repository_intelligence(
    owner: str,
    repo: str,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Forces a fresh analysis of a specific repository, bypassing cached results.
    """
    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate profile not found")

    try:
        token = get_github_token_for_user(user_id, db)
        client = GitHubApiClient(token=token)
        intel = await github_intelligence_service.collect_repository_intelligence(
            owner=owner,
            repo=repo,
            client=client,
            candidate_name=cand.name,
            force_refresh=True
        )
        github_data = dict(cand.github_data or {})
        intel_map = dict(github_data.get("intelligence", {}))
        intel_map[intel.full_name] = intel.model_dump()
        github_data["intelligence"] = intel_map
        github_data["last_synced_at"] = datetime.now(timezone.utc).isoformat()
        cand.github_data = github_data
        cand.evidence_version = (cand.evidence_version or 1) + 1
        cand.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        snapshot_manager.invalidate_candidate_snapshots(user_id=cand.user_id, db=db)
        db.refresh(cand)
        return intel
    except GitHubTokenRevokedError as tre:
        logger.warning(f"GitHub token revoked for user {user_id}: {tre}")
        raise HTTPException(
            status_code=401,
            detail={"status": "reconnect_required", "message": "GitHub access token has been revoked or expired. Please reconnect."}
        )
    except Exception as e:
        logger.error(f"Failed to refresh repository intelligence for {owner}/{repo}: {sanitize_error_message(str(e))}")
        raise HTTPException(status_code=500, detail=sanitize_error_message(str(e)))

@router.post("/integrations/github/import-to-profile")
def import_repositories_to_profile(
    req: GitHubImportRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Imports analyzed GitHub repositories into the candidate's Master Profile projects.
    Strictly preserves curated descriptions, bullets, and project IDs unless overwrite_curated=True.
    """
    try:
        imported_count, projects = github_intelligence_service.import_repository_to_candidate_profile(
            user_id=user_id,
            repo_urls=req.repo_urls,
            db=db,
            overwrite_curated=req.overwrite_curated
        )
        return {
            "status": "success",
            "imported_count": imported_count,
            "projects_count": len(projects),
            "projects": projects
        }
    except Exception as e:
        logger.error(f"Failed to import repositories to profile for user {user_id}: {sanitize_error_message(str(e))}")
        raise HTTPException(status_code=500, detail=sanitize_error_message(str(e)))

@router.post("/integrations/github/token")
def set_github_token(
    req: GitHubTokenRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Securely stores an encrypted personal access token for GitHub integration.
    Plaintext tokens are never stored, logged, or returned in API responses.
    """
    if not req.token or len(req.token.strip()) < 4:
        raise HTTPException(status_code=400, detail="Invalid GitHub token provided")

    try:
        save_github_token_for_user(user_id=user_id, token=req.token, db=db)
        return {
            "status": "connected",
            "message": "GitHub Personal Access Token securely encrypted and stored."
        }
    except Exception as e:
        logger.error(f"Failed to store GitHub token: {sanitize_error_message(str(e))}")
        raise HTTPException(status_code=500, detail="Failed to securely store token")

@router.delete("/integrations/github/token")
def remove_github_token(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Removes candidate's stored GitHub Personal Access Token.
    """
    try:
        delete_github_token_for_user(user_id=user_id, db=db)
        return {
            "status": "disconnected",
            "message": "GitHub token successfully removed."
        }
    except Exception as e:
        logger.error(f"Failed to remove GitHub token: {sanitize_error_message(str(e))}")
        raise HTTPException(status_code=500, detail="Failed to securely remove token")

@router.post("/integrations/portfolio")
async def sync_portfolio(req: PortfolioSyncRequest, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Extract project information and skills from public developer portfolio with SSRF protection."""
    try:
        data = await fetch_portfolio_data(req.url)
        cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
        if cand:
            cand.portfolio_url = req.url
            cand.portfolio_data = data
            cand.evidence_version = (cand.evidence_version or 1) + 1
            cand.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
            snapshot_manager.invalidate_candidate_snapshots(user_id=cand.user_id, db=db)
            db.refresh(cand)
        return data
    except ValueError as e:
        # SSRF / URL-validation rejections are intentional and safe to surface.
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Portfolio sync failed")
        raise HTTPException(status_code=400, detail="Portfolio import failed.")

@router.post("/integrations/linkedin")
def import_linkedin_data(req: LinkedInImportRequest, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """
    Import user-provided or exported LinkedIn profile data.
    Does not scrape private LinkedIn pages or bypass authentication.
    """
    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    if not cand:
        cand = CandidateProfile(user_id=user_id)
        db.add(cand)
        
    if req.profile_url:
        cand.linkedin_url = req.profile_url
        
    cand.linkedin_data = {
        "profile_url": req.profile_url,
        "headline": req.headline,
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "is_oauth_connected": False, # Never falsely claim OAuth connected
        "skills_count": len(req.skills or []),
        "experience_count": len(req.experience or [])
    }
    
    # Merge non-duplicate skills if user provided
    if req.skills:
        existing_names = {s.get("name", "").lower() for s in (cand.skills or [])}
        new_skills = list(cand.skills or [])
        for s in req.skills:
            if s.lower() not in existing_names:
                new_skills.append({
                    "name": s,
                    "level": "intermediate",
                    "category": "imported",
                    "evidence": "LinkedIn Profile Import"
                })
                existing_names.add(s.lower())
        cand.skills = new_skills
        
    cand.evidence_version = (cand.evidence_version or 1) + 1
    cand.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    snapshot_manager.invalidate_candidate_snapshots(user_id=cand.user_id, db=db)
    db.refresh(cand)
    return cand

@router.post("/integrations/parse-resume", dependencies=[Depends(rate_limited("upload"))])
async def parse_candidate_resume(file: UploadFile = File(...), user_id: int = Depends(get_current_user_id)):
    """
    Extracts candidate draft info, technical skills, and projects from uploaded resume (PDF or plaintext)
    with safe sandboxing and returns structured preview for candidate review and approval.
    Does not commit changes directly to the database.
    """
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")

    max_upload = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
    filename = (file.filename or "resume.pdf").strip()

    # Reject path traversal / unsafe filenames outright.
    safe_name_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if (".." in filename) or any(ch not in safe_name_chars for ch in filename):
        raise HTTPException(status_code=400, detail="Unsupported file name.")

    allowed_extensions = (".pdf", ".txt", ".md")
    if not any(filename.lower().endswith(ext) for ext in allowed_extensions):
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload a PDF or text file.")

    # Stream the body with an early size cap rather than trusting Content-Length.
    chunks = []
    total = 0
    while True:
        chunk = await file.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > max_upload:
            raise HTTPException(status_code=413, detail="Uploaded file exceeds size limit.")
        chunks.append(chunk)

    content = b"".join(chunks)
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Magic-byte verification: every .pdf must start with %PDF-. Text/markdown must decode as UTF-8/Latin-1.
    if filename.lower().endswith(".pdf"):
        if not content.startswith(b"%PDF-"):
            raise HTTPException(status_code=422, detail="Uploaded file content does not match PDF format.")
    else:
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=422, detail="Uploaded text file is not decodable as UTF-8.")

    try:
        result = parse_resume_file(content, filename=filename)
        return result
    except ValueError:
        raise HTTPException(status_code=422, detail="Could not parse the uploaded resume content.")
    except Exception:
        logger.exception("Resume parsing failed for user_id=%s filename=%s", user_id, filename)
        raise HTTPException(status_code=500, detail="Resume parsing failed.")

@router.post("/integrations/approve")
def approve_and_merge_integrations(req: ApproveIntegrationsRequest, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Merge user-reviewed projects and skills from external integrations into Master Profile."""
    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate profile not found")
        
    # Merge candidate fields if provided
    if req.candidate_updates:
        allowed_fields = [
            "name", "email", "phone", "location", "bio", "degree",
            "graduation_year", "college", "cgpa", "github_url",
            "linkedin_url", "portfolio_url", "work_authorization"
        ]
        for field in allowed_fields:
            val = req.candidate_updates.get(field)
            if val is not None and val != "":
                setattr(cand, field, val)

    # Merge projects
    if req.approved_projects:
        existing_titles = {p.get("title", "").lower() for p in (cand.projects or [])}
        curr_projects = list(cand.projects or [])
        for p in req.approved_projects:
            if p.get("title", "").lower() not in existing_titles:
                curr_projects.append(p)
                existing_titles.add(p.get("title", "").lower())
        cand.projects = curr_projects
        flag_modified(cand, "projects")

    # Merge skills
    if req.approved_skills:
        existing_skills = {s.get("name", "").lower() for s in (cand.skills or [])}
        curr_skills = list(cand.skills or [])
        for s in req.approved_skills:
            if s.get("name", "").lower() not in existing_skills:
                curr_skills.append(s)
                existing_skills.add(s.get("name", "").lower())
        cand.skills = curr_skills
        flag_modified(cand, "skills")
        
    cand.evidence_version = (cand.evidence_version or 1) + 1
    cand.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    snapshot_manager.invalidate_candidate_snapshots(user_id=cand.user_id, db=db)
    db.refresh(cand)
    return cand

