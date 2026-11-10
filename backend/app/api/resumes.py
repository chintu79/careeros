import os
import re
import math
import shutil
import logging
import asyncio
import tempfile
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import desc

from backend.app.database import get_db
from backend.app.core.auth import get_current_user_id
from backend.app.models.resume import ResumeDocument
from backend.app.models.resume_version import ResumeVersion
from backend.app.models.candidate import CandidateProfile
from backend.app.models.opportunity import Opportunity
from backend.app.models.application import ApplicationRecord
from backend.app.services.latex_compiler import (
    compile_latex,
    compile_in_temp_env,
    compile_and_validate_resume,
    atomic_promote_file,
    PDFPromotionTransaction,
    STORAGE_DIR
)
from backend.app.services.pdf_layout_validator import validate_pdf_layout, determine_target_page_count, determine_page_size
from backend.app.services.latex_templates import list_available_templates, build_latex_template
from backend.app.services.resume_tailorer import tailor_resume_for_opportunity
from backend.app.services.resume_intelligence_service import (
    audit_resume_quality,
    generate_resume_ai_optimization,
    compare_resumes
)
from backend.app.services.ai.service import ai_service, validate_tailoring_safety
from backend.app.services.ai.types import AIProviderError
from backend.app.schemas.structured_resume import (
    StructuredResumeContent,
    StructuredSectionUpdateRequest,
    CompileResumeRequest,
    SectionRegenerateRequest,
    SectionRegenerationProposal,
    profile_to_structured_resume,
    generate_stable_id,
    BulletPoint
)
from backend.app.services.section_regenerator import regenerate_resume_section
from backend.app.services.latex_parser import parse_latex_to_structured_content

logger = logging.getLogger(__name__)

def serialize_resume(r: ResumeDocument) -> Dict[str, Any]:
    if not r:
        return {}
    sc = dict(r.structured_content or {})
    # Protect against exposing stale layout metadata if resume was modified without recompilation
    if isinstance(sc.get("metadata"), dict) and "layout_metadata" in sc["metadata"]:
        is_stale = False
        if not r.pdf_path or not os.path.exists(r.pdf_path):
            is_stale = True
        elif r.pdf_generated_at and r.updated_at and (r.updated_at - r.pdf_generated_at).total_seconds() > 2.0:
            is_stale = True
        if is_stale and isinstance(sc["metadata"]["layout_metadata"], dict):
            sc["metadata"] = dict(sc["metadata"])
            sc["metadata"]["layout_metadata"] = dict(sc["metadata"]["layout_metadata"])
            sc["metadata"]["layout_metadata"]["is_stale"] = True

    return {
        "id": r.id,
        "user_id": r.user_id,
        "title": r.title,
        "template_id": r.template_id,
        "latex_content": r.latex_content,
        "structured_content": sc,
        "target_opportunity_id": r.target_opportunity_id,
        "target_company": r.target_company,
        "target_role": r.target_role,
        "is_master": r.is_master,
        "version": r.version,
        "tailored_insights": r.tailored_insights,
        "pdf_path": r.pdf_path,
        "pdf_generated_at": r.pdf_generated_at.isoformat() if r.pdf_generated_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None
    }

def serialize_version(v: ResumeVersion) -> Dict[str, Any]:
    return {
        "id": v.id,
        "resume_id": v.resume_id,
        "version_number": v.version_number,
        "title": v.title,
        "template_id": v.template_id,
        "latex_content": v.latex_content,
        "structured_content": v.structured_content or {},
        "pdf_path": v.pdf_path,
        "change_summary": v.change_summary,
        "created_at": v.created_at.isoformat() if v.created_at else None
    }

def get_or_initialize_structured_content(resume: ResumeDocument, db: Session, persist: bool = False) -> StructuredResumeContent:
    """
    Retrieves or synthesizes structured resume content for a resume document.
    Prioritizes existing structured_content.
    If missing, parses existing LaTeX content to preserve user customizations,
    bullets, and sections, using CandidateProfile only to fill absent information.
    If persist=True (e.g. during an explicit save/update), commits the model to DB.
    If persist=False (e.g. during GET), never mutates the database.
    """
    existing_meta = {}
    if resume.structured_content and isinstance(resume.structured_content, dict):
        if isinstance(resume.structured_content.get("metadata"), dict):
            existing_meta = dict(resume.structured_content["metadata"])

    if resume.structured_content and isinstance(resume.structured_content, dict) and resume.structured_content.get("personal_info"):
        try:
            structured = StructuredResumeContent(**resume.structured_content)
            if not isinstance(structured.metadata, dict):
                structured.metadata = {}
            if "page_size" not in structured.metadata or not structured.metadata["page_size"]:
                structured.metadata["page_size"] = determine_page_size(
                    structured_data=resume.structured_content,
                    latex_content=resume.latex_content
                )
            return structured
        except Exception:
            pass

    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == resume.user_id).first()
    cand_dict = {
        "name": cand.name if cand else "",
        "email": cand.email if cand else "",
        "phone": cand.phone if cand else "",
        "location": cand.location if cand else "",
        "degree": cand.degree if cand else "",
        "college": cand.college if cand else "",
        "graduation_year": cand.graduation_year if cand else None,
        "cgpa": cand.cgpa if cand else None,
        "github_url": cand.github_url if cand else "",
        "linkedin_url": cand.linkedin_url if cand else "",
        "portfolio_url": cand.portfolio_url if cand else "",
        "skills": cand.skills if cand else [],
        "projects": cand.projects if cand else [],
        "experience": cand.experience if cand else [],
        "certifications": cand.certifications if cand else [],
        "achievements": cand.achievements if cand else []
    }

    if resume.latex_content and resume.latex_content.strip():
        structured = parse_latex_to_structured_content(resume.latex_content, cand_dict)
    else:
        structured = profile_to_structured_resume(cand_dict)

    if not isinstance(structured.metadata, dict):
        structured.metadata = {}
    if existing_meta:
        for k, v in existing_meta.items():
            if k not in structured.metadata or not structured.metadata[k]:
                structured.metadata[k] = v

    if "page_size" not in structured.metadata or not structured.metadata["page_size"]:
        structured.metadata["page_size"] = determine_page_size(
            structured_data=structured.model_dump(),
            latex_content=resume.latex_content,
            profile_location=cand.location if cand else None
        )

    if persist:
        resume.structured_content = structured.model_dump()
        db.commit()

    return structured

def validate_and_merge_bullets(
    entry_title: str,
    existing_entry_bullets: List[Dict[str, Any]],
    incoming_bullets: List[Any],
    is_existing_entry: bool = True
) -> List[Dict[str, Any]]:
    """
    Validates and merges bullet points preserving stable IDs.
    Rejects unknown bullet IDs if caller attempts an in-place update on non-existent IDs.
    Supports adding (new/omitted ID), editing, deleting (omitted), and reordering.
    """
    existing_id_map = {b["id"]: b for b in existing_entry_bullets if isinstance(b, dict) and "id" in b}
    merged_bullets = []

    for b in incoming_bullets:
        b_dict = b.model_dump() if hasattr(b, "model_dump") else (b if isinstance(b, dict) else {"text": str(b)})
        b_id = b_dict.get("id")

        if b_id:
            if b_id in existing_id_map:
                # Update existing bullet
                orig_b = existing_id_map[b_id]
                updated_b = dict(orig_b)
                updated_b.update({k: v for k, v in b_dict.items() if v is not None})
                merged_bullets.append(updated_b)
            elif is_existing_entry and not str(b_id).startswith("new_") and not str(b_id).startswith("bullet_new"):
                # Unknown bullet ID rejected for an existing entry
                raise HTTPException(
                    status_code=422,
                    detail=f"Unknown bullet ID '{b_id}' for entry '{entry_title}'. Use new ID or omit ID to create a new bullet."
                )
            else:
                # New bullet with assigned/client-provided ID
                merged_bullets.append(b_dict)
        else:
            b_dict["id"] = generate_stable_id("bullet")
            merged_bullets.append(b_dict)

    return merged_bullets

router = APIRouter(prefix="/resumes", tags=["LaTeX Resume Studio"])

class ResumeCreate(BaseModel):
    title: str
    template_id: Optional[str] = "minimal_professional"
    latex_content: Optional[str] = None
    target_opportunity_id: Optional[int] = None
    target_company: Optional[str] = None
    target_role: Optional[str] = None
    is_master: Optional[bool] = False

class ResumeUpdate(BaseModel):
    title: Optional[str] = None
    template_id: Optional[str] = None
    latex_content: Optional[str] = None
    change_summary: Optional[str] = "Content updated in editor"

class ResumeRename(BaseModel):
    title: str

class ResumeCompareRequest(BaseModel):
    target_version_id: Optional[int] = None
    compare_with_master: Optional[bool] = False

class ResumeOptimizeRequest(BaseModel):
    opportunity_id: int

class ApplyOptimizationRequest(BaseModel):
    latex_content: str
    change_summary: Optional[str] = "Applied user-approved AI optimizations"

class VersionSnapshotCreate(BaseModel):
    change_summary: Optional[str] = "Manual checkpoint snapshot"

class TailorRequest(BaseModel):
    opportunity_id: int
    template_id: Optional[str] = "minimal_professional"

@router.get("/templates")
def get_templates():
    """Returns the list of 6 ATS-friendly LaTeX templates with metadata."""
    return list_available_templates()

@router.get("")
def list_resumes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    is_master: Optional[bool] = None,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """List all master and tailored resume documents for the authenticated user with server-side pagination."""
    query = db.query(ResumeDocument).filter(ResumeDocument.user_id == user_id)
    if is_master is not None:
        query = query.filter(ResumeDocument.is_master == is_master)
        
    total = query.count()
    total_pages = max(1, math.ceil(total / page_size))
    items = query.order_by(desc(ResumeDocument.updated_at)).offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        "items": [serialize_resume(r) for r in items],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages
    }

@router.get("/master")
def get_or_create_master_resume(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Fetch the active master resume for the authenticated user, or initialize one directly from their Candidate Profile."""
    master = db.query(ResumeDocument).filter(
        ResumeDocument.user_id == user_id,
        ResumeDocument.is_master == True
    ).first()
    if not master:
        cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
        cand_dict = {
            "name": cand.name if cand else "",
            "email": cand.email if cand else "",
            "phone": cand.phone if cand else "",
            "location": cand.location if cand else "",
            "degree": cand.degree if cand else "",
            "college": cand.college if cand else "",
            "graduation_year": cand.graduation_year if cand else None,
            "cgpa": cand.cgpa if cand else None,
            "github_url": cand.github_url if cand else "",
            "linkedin_url": cand.linkedin_url if cand else "",
            "portfolio_url": cand.portfolio_url if cand else "",
            "skills": cand.skills if cand else [],
            "projects": cand.projects if cand else [],
            "experience": cand.experience if cand else [],
            "certifications": cand.certifications if cand else [],
            "achievements": cand.achievements if cand else []
        }
        latex_code = build_latex_template(cand_dict, template_id="minimal_professional")
        master = ResumeDocument(
            user_id=user_id,
            title="Master Candidate Resume",
            template_id="minimal_professional",
            latex_content=latex_code,
            is_master=True,
            version=1
        )
        db.add(master)
        db.commit()
        db.refresh(master)
        
        # Initialize structured_content
        master_structured = get_or_initialize_structured_content(master, db, persist=False)
        master.structured_content = master_structured.model_dump()
        flag_modified(master, "structured_content")
        db.commit()
        db.refresh(master)

        # Save initial version 1 snapshot
        v1 = ResumeVersion(
            resume_id=master.id,
            version_number=1,
            title=master.title,
            template_id=master.template_id,
            latex_content=master.latex_content,
            structured_content=master.structured_content,
            change_summary="Initial master resume created from profile"
        )
        db.add(v1)
        db.commit()

    return serialize_resume(master)

@router.get("/{id}")
def get_resume(id: int, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Retrieve full resume details and LaTeX source by ID."""
    resume = db.query(ResumeDocument).filter(ResumeDocument.id == id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume document not found")
    if resume.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this resume")
    return serialize_resume(resume)

@router.post("")
def create_resume(data: ResumeCreate, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Create a new custom resume."""
    latex = data.latex_content
    template_id = data.template_id or "minimal_professional"
    if not latex:
        cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
        cand_dict = {
            "name": cand.name if cand else "",
            "email": cand.email if cand else "",
            "phone": cand.phone if cand else "",
            "location": cand.location if cand else "",
            "degree": cand.degree if cand else "",
            "college": cand.college if cand else "",
            "graduation_year": cand.graduation_year if cand else None,
            "cgpa": cand.cgpa if cand else None,
            "github_url": cand.github_url if cand else "",
            "linkedin_url": cand.linkedin_url if cand else "",
            "portfolio_url": cand.portfolio_url if cand else "",
            "skills": cand.skills if cand else [],
            "projects": cand.projects if cand else [],
            "experience": cand.experience if cand else [],
            "certifications": cand.certifications if cand else [],
            "achievements": cand.achievements if cand else []
        }
        latex = build_latex_template(cand_dict, template_id=template_id)
        
    resume = ResumeDocument(
        user_id=user_id,
        title=data.title,
        template_id=template_id,
        latex_content=latex,
        target_opportunity_id=data.target_opportunity_id,
        target_company=data.target_company,
        target_role=data.target_role,
        is_master=data.is_master or False,
        version=1
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    
    # Initialize structured content
    init_structured = get_or_initialize_structured_content(resume, db, persist=False)
    resume.structured_content = init_structured.model_dump()
    flag_modified(resume, "structured_content")
    db.commit()
    db.refresh(resume)

    # Save initial version 1 snapshot
    v1 = ResumeVersion(
        resume_id=resume.id,
        version_number=1,
        title=resume.title,
        template_id=resume.template_id,
        latex_content=resume.latex_content,
        structured_content=resume.structured_content,
        change_summary="Initial document creation"
    )
    db.add(v1)
    db.commit()

    return serialize_resume(resume)

@router.get("/{id}/sections")
def get_resume_sections(
    id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Retrieves full structured representation of resume sections."""
    resume = db.query(ResumeDocument).filter(ResumeDocument.id == id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume document not found")
    if resume.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this resume")

    structured = get_or_initialize_structured_content(resume, db, persist=False)
    return {
        "resume_id": resume.id,
        "version": resume.version,
        "template_id": resume.template_id,
        "structured_content": structured.model_dump()
    }

@router.put("/{id}/sections")
def update_resume_sections(
    id: int,
    req: StructuredSectionUpdateRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Updates individual resume sections while strictly preserving unedited sections and template.
    - Authenticates user and verifies resume ownership.
    - Enforces atomic optimistic concurrency with with_for_update() row lock (409 on mismatch).
    - Validates bullet IDs (rejects unknown bullet IDs for existing entries).
    - Preserves unchanged sections (e.g. Certifications, Honors, Education).
    - Regenerates and strictly pre-compiles LaTeX before committing changes.
    - On compilation or validation failure, rolls back and preserves existing resume state.
    - Creates a new version snapshot upon successful compilation and update.
    """
    resume = (
        db.query(ResumeDocument)
        .filter(ResumeDocument.id == id)
        .with_for_update()
        .first()
    )
    if not resume:
        raise HTTPException(status_code=404, detail="Resume document not found")
    if resume.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this resume")

    # Optimistic Concurrency Control evaluated under exclusive row lock
    if req.expected_version is not None and req.expected_version != resume.version:
        raise HTTPException(
            status_code=409,
            detail=f"Conflict: Current resume version is {resume.version}, but expected {req.expected_version}."
        )

    current_structured = get_or_initialize_structured_content(resume, db, persist=False)
    current_dict = current_structured.model_dump()

    # Extract update payload excluding metadata fields
    raw_updates = req.model_dump(exclude_unset=True)
    raw_updates.pop("expected_version", None)
    req_target_page_count = raw_updates.pop("target_page_count", None) or req.target_page_count
    req_page_size = raw_updates.pop("page_size", None) or req.page_size
    change_summary = raw_updates.pop("change_summary", None) or f"Updated structured sections (v{resume.version + 1})"

    # Process section-specific validations and merges
    for sec_name, sec_val in raw_updates.items():
        if sec_val is None:
            continue

        if sec_name == "projects":
            existing_projects = current_dict.get("projects", [])
            existing_proj_map = {p["id"]: p for p in existing_projects if "id" in p}
            new_projects = []

            for p_item in sec_val:
                p_id = p_item.get("id")
                is_existing_entry = bool(p_id and p_id in existing_proj_map)
                existing_entry = existing_proj_map.get(p_id, {})
                existing_bullets = existing_entry.get("bullets", [])

                incoming_bullets = p_item.get("bullets", [])
                merged_bullets = validate_and_merge_bullets(
                    entry_title=p_item.get("title", "Project"),
                    existing_entry_bullets=existing_bullets,
                    incoming_bullets=incoming_bullets,
                    is_existing_entry=is_existing_entry
                )
                p_entry_dict = dict(p_item)
                p_entry_dict["bullets"] = merged_bullets
                if not p_entry_dict.get("id"):
                    p_entry_dict["id"] = generate_stable_id("proj")
                new_projects.append(p_entry_dict)

            current_dict["projects"] = new_projects

        elif sec_name == "experience":
            existing_exp = current_dict.get("experience", [])
            existing_exp_map = {e["id"]: e for e in existing_exp if "id" in e}
            new_exp = []

            for e_item in sec_val:
                e_id = e_item.get("id")
                is_existing_entry = bool(e_id and e_id in existing_exp_map)
                existing_entry = existing_exp_map.get(e_id, {})
                existing_bullets = existing_entry.get("bullets", [])

                incoming_bullets = e_item.get("bullets", [])
                merged_bullets = validate_and_merge_bullets(
                    entry_title=e_item.get("title", "Experience"),
                    existing_entry_bullets=existing_bullets,
                    incoming_bullets=incoming_bullets,
                    is_existing_entry=is_existing_entry
                )
                e_entry_dict = dict(e_item)
                e_entry_dict["bullets"] = merged_bullets
                if not e_entry_dict.get("id"):
                    e_entry_dict["id"] = generate_stable_id("exp")
                new_exp.append(e_entry_dict)

            current_dict["experience"] = new_exp

        else:
            # Overwrite only the specified section, preserving all other keys
            current_dict[sec_name] = sec_val

    # Re-validate complete structured content model
    try:
        updated_structured = StructuredResumeContent(**current_dict)
    except Exception as e:
        raise HTTPException(status_code=422, detail="Database commit failed")

    if not isinstance(updated_structured.metadata, dict):
        updated_structured.metadata = {}

    resolved_page_size = determine_page_size(
        explicit_page_size=req_page_size,
        structured_data=updated_structured.model_dump(),
        latex_content=resume.latex_content
    )
    updated_structured.metadata["page_size"] = resolved_page_size

    # Regenerate LaTeX using active template with resolved page_size
    new_latex = build_latex_template(
        updated_structured.model_dump(),
        template_id=resume.template_id,
        page_size=resolved_page_size
    )

    # Pre-validate LaTeX compilation before committing
    next_version = resume.version + 1
    base_name = f"resume_{resume.id}_v{next_version}"
    target_pdf_path = os.path.join(STORAGE_DIR, f"{base_name}.pdf")
    target_tex_path = os.path.join(STORAGE_DIR, f"{base_name}.tex")
    tx = PDFPromotionTransaction(target_pdf_path, target_tex_path)

    resolved_target = determine_target_page_count(
        template_id=resume.template_id,
        structured_data=updated_structured.model_dump(),
        explicit_target=req_target_page_count
    )

    with tempfile.TemporaryDirectory(prefix="interniq_stage_") as stage_dir:
        # Step 1: Compilation into staging directory
        ok, staged_pdf_or_err, compiler = compile_latex(
            new_latex,
            base_name,
            strict=True,
            page_size=resolved_page_size,
            output_dir=stage_dir
        )
        if not ok:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail="Cannot apply section update: LaTeX compilation failed. Your original resume was preserved unchanged."
            )

        # Step 2: PDF Layout Validation BEFORE promotion
        page_analysis = validate_pdf_layout(
            pdf_path=staged_pdf_or_err,
            target_page_count=resolved_target,
            structured_data=updated_structured.model_dump(),
            target_page_size=resolved_page_size
        )
        if page_analysis.get("validation_status") == "failed":
            db.rollback()
            err_msg = "; ".join(page_analysis.get("errors", [])) if page_analysis.get("errors") else "Layout validation failed"
            raise HTTPException(
                status_code=400,
                detail="Cannot apply section update: LaTeX compilation failed. Your original resume was preserved unchanged."
            )

        # Step 3: Atomic file promotion under reversible transaction
        staged_tex = os.path.join(stage_dir, f"{base_name}.tex")
        tx.stage_and_promote(staged_pdf_or_err, staged_tex if os.path.exists(staged_tex) else None)

    # Attach layout metadata to structured_content
    saved_structured = updated_structured.model_dump()
    if not isinstance(saved_structured.get("metadata"), dict):
        saved_structured["metadata"] = {}
    saved_structured["metadata"]["layout_metadata"] = page_analysis
    saved_structured["metadata"]["page_size"] = resolved_page_size
    if req_target_page_count:
        saved_structured["metadata"]["target_page_count"] = req_target_page_count

    # Step 4: Database updates
    resume.structured_content = saved_structured
    resume.latex_content = new_latex
    resume.version = next_version
    resume.pdf_path = target_pdf_path
    resume.pdf_generated_at = datetime.utcnow()
    resume.updated_at = datetime.utcnow()
    flag_modified(resume, "structured_content")

    # Snapshot version
    snapshot = ResumeVersion(
        resume_id=resume.id,
        version_number=resume.version,
        title=resume.title,
        template_id=resume.template_id,
        latex_content=resume.latex_content,
        structured_content=resume.structured_content,
        pdf_path=resume.pdf_path,
        change_summary=change_summary
    )
    db.add(snapshot)

    # Step 5 & 6: Database commit and transactional cleanup/recovery
    try:
        db.commit()
        db.refresh(resume)
        tx.commit()
    except Exception as e:
        tx.rollback()
        db.rollback()
        logger.error(f"Database commit failed during section update: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Database commit failed"
        )

    return {
        "status": "success",
        "resume": serialize_resume(resume),
        "structured_content": resume.structured_content,
        "version": resume.version,
        "page_analysis": page_analysis
    }

@router.post("/{id}/sections/regenerate")
async def regenerate_section(
    id: int,
    req: SectionRegenerateRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Regenerates an individual resume section using Groq reasoning.
    Returns proposal only — does NOT overwrite saved resume or increment version.
    """
    resume = db.query(ResumeDocument).filter(ResumeDocument.id == id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume document not found")
    if resume.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this resume")

    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate profile not found")

    opp_dict = None
    if req.opportunity_id:
        opp = db.query(Opportunity).filter(Opportunity.id == req.opportunity_id).first()
        if not opp:
            raise HTTPException(status_code=404, detail="Target opportunity not found")
        if opp.user_id is not None and opp.user_id != user_id:
            raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this opportunity")
        opp_dict = {
            "id": opp.id,
            "title": opp.title,
            "company_name": opp.company_name,
            "required_skills": opp.required_skills or [],
            "preferred_skills": opp.preferred_skills or []
        }

    cand_dict = {
        "id": cand.id,
        "name": cand.name or "",
        "email": cand.email or "",
        "degree": cand.degree or "",
        "college": cand.college or "",
        "skills": cand.skills or [],
        "projects": cand.projects or [],
        "experience": cand.experience or [],
        "certifications": cand.certifications or [],
        "achievements": cand.achievements or []
    }

    structured = get_or_initialize_structured_content(resume, db)

    try:
        proposal = await regenerate_resume_section(
            section=req.section,
            resume_content=structured,
            candidate_profile_data=cand_dict,
            opportunity_data=opp_dict,
            entry_id=req.entry_id,
            user_instructions=req.user_instructions
        )
        return proposal
    except ValueError as ve:
        raise HTTPException(status_code=422, detail='Invalid request content')
    except AIProviderError as aie:
        raise HTTPException(
            status_code=503,
            detail="AI Section Regeneration unavailable: The AI provider could not complete the request. Original section preserved."
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail="Database commit failed"
        )

@router.put("/{id}")
def update_resume(id: int, data: ResumeUpdate, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Update resume title, template, or LaTeX content, auto-creating a version snapshot."""
    resume = db.query(ResumeDocument).filter(ResumeDocument.id == id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume document not found")
    if resume.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this resume")
        
    for field, val in data.model_dump(exclude_unset=True).items():
        if field != "change_summary" and val is not None:
            setattr(resume, field, val)
            
    resume.version += 1
    resume.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(resume)
    
    # Archive version snapshot
    snapshot = ResumeVersion(
        resume_id=resume.id,
        version_number=resume.version,
        title=resume.title,
        template_id=resume.template_id,
        latex_content=resume.latex_content,
        structured_content=resume.structured_content,
        pdf_path=resume.pdf_path,
        change_summary=data.change_summary or f"Version {resume.version} saved"
    )
    db.add(snapshot)
    db.commit()
    
    return serialize_resume(resume)

@router.post("/{id}/rename")
def rename_resume(id: int, req: ResumeRename, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Rename resume document title."""
    clean_title = req.title.strip()
    if not clean_title:
        raise HTTPException(status_code=400, detail="Title cannot be empty")
        
    resume = db.query(ResumeDocument).filter(ResumeDocument.id == id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume document not found")
    if resume.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this resume")
        
    resume.title = clean_title
    resume.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(resume)
    return serialize_resume(resume)

@router.post("/{id}/duplicate")
def duplicate_resume(id: int, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Duplicate an existing resume into a new editable document."""
    orig = db.query(ResumeDocument).filter(ResumeDocument.id == id).first()
    if not orig:
        raise HTTPException(status_code=404, detail="Source resume not found")
    if orig.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this resume")
        
    dup = ResumeDocument(
        user_id=user_id,
        title=f"Copy of {orig.title}",
        template_id=orig.template_id,
        latex_content=orig.latex_content,
        target_opportunity_id=orig.target_opportunity_id,
        target_company=orig.target_company,
        target_role=orig.target_role,
        is_master=False,  # Duplicates are never master
        version=1,
        tailored_insights=orig.tailored_insights or {}
    )
    db.add(dup)
    db.commit()
    db.refresh(dup)
    
    # Version snapshot
    v1 = ResumeVersion(
        resume_id=dup.id,
        version_number=1,
        title=dup.title,
        template_id=dup.template_id,
        latex_content=dup.latex_content,
        change_summary=f"Cloned from resume #{orig.id} ('{orig.title}')"
    )
    db.add(v1)
    db.commit()
    
    return serialize_resume(dup)

@router.delete("/{id}")
def delete_resume(id: int, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Delete a resume document with strict Master Resume deletion protection."""
    resume = db.query(ResumeDocument).filter(ResumeDocument.id == id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume document not found")
    if resume.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this resume")
        
    if resume.is_master:
        raise HTTPException(
            status_code=400,
            detail="The Master Candidate Resume is protected and cannot be deleted. You can edit it or create tailored versions."
        )
        
    # Unlink any application records referencing this resume
    db.query(ApplicationRecord).filter(ApplicationRecord.resume_id == id).update({"resume_id": None})
    
    db.delete(resume)
    db.commit()
    return {"message": "Resume deleted successfully", "id": id}

@router.get("/{id}/versions")
def list_resume_versions(id: int, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Retrieve full version snapshot history for a resume."""
    resume = db.query(ResumeDocument).filter(ResumeDocument.id == id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume document not found")
    if resume.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this resume")
        
    versions = db.query(ResumeVersion).filter(ResumeVersion.resume_id == id).order_by(desc(ResumeVersion.version_number)).all()
    return [serialize_version(v) for v in versions]

@router.post("/{id}/versions")
def create_version_snapshot(id: int, req: VersionSnapshotCreate, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Explicitly checkpoint a version snapshot."""
    resume = db.query(ResumeDocument).filter(ResumeDocument.id == id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume document not found")
    if resume.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this resume")
        
    new_version_num = resume.version + 1
    resume.version = new_version_num
    resume.updated_at = datetime.utcnow()
    
    snapshot = ResumeVersion(
        resume_id=resume.id,
        version_number=new_version_num,
        title=resume.title,
        template_id=resume.template_id,
        latex_content=resume.latex_content,
        structured_content=resume.structured_content,
        pdf_path=resume.pdf_path,
        change_summary=req.change_summary or f"Manual checkpoint v{new_version_num}"
    )
    db.add(snapshot)
    db.commit()
    db.refresh(resume)
    return serialize_resume(resume)

@router.post("/{id}/versions/{version_id}/restore")
def restore_resume_version(id: int, version_id: int, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Restore a prior version snapshot into the active resume document."""
    resume = db.query(ResumeDocument).filter(ResumeDocument.id == id).with_for_update().first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume document not found")
    if resume.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this resume")
        
    version = db.query(ResumeVersion).filter(ResumeVersion.id == version_id, ResumeVersion.resume_id == id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Version snapshot not found")
        
    next_version = resume.version + 1
    new_pdf_path = None
    if version.pdf_path and os.path.exists(version.pdf_path):
        new_pdf_path = os.path.join(STORAGE_DIR, f"resume_{resume.id}_v{next_version}.pdf")
        try:
            shutil.copyfile(version.pdf_path, new_pdf_path)
        except Exception:
            new_pdf_path = version.pdf_path

    resume.latex_content = version.latex_content
    resume.template_id = version.template_id
    resume.structured_content = version.structured_content
    resume.pdf_path = new_pdf_path or version.pdf_path
    resume.pdf_generated_at = datetime.utcnow() if (new_pdf_path or version.pdf_path) else None
    resume.version = next_version
    resume.updated_at = datetime.utcnow()
    flag_modified(resume, "structured_content")
    db.commit()
    db.refresh(resume)
    
    # Save restore audit snapshot with all fields synchronized
    restore_snapshot = ResumeVersion(
        resume_id=resume.id,
        version_number=resume.version,
        title=resume.title,
        template_id=resume.template_id,
        latex_content=resume.latex_content,
        structured_content=resume.structured_content,
        pdf_path=resume.pdf_path,
        change_summary=f"Restored from version snapshot v{version.version_number}"
    )
    db.add(restore_snapshot)
    db.commit()
    
    return serialize_resume(resume)

@router.post("/{id}/compare")
def compare_resume_versions(id: int, req: ResumeCompareRequest, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """
    Compare current resume LaTeX against Master Resume or a historical version snapshot.
    Returns line diffs, section additions/removals/reorderings, and change rationales.
    """
    resume = db.query(ResumeDocument).filter(ResumeDocument.id == id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume document not found")
    if resume.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this resume")
        
    if req.compare_with_master:
        master = db.query(ResumeDocument).filter(
            ResumeDocument.user_id == user_id,
            ResumeDocument.is_master == True
        ).first()
        if not master:
            raise HTTPException(status_code=404, detail="Master resume not found for comparison")
        return compare_resumes(
            base_latex=master.latex_content,
            target_latex=resume.latex_content,
            base_label=f"Master: {master.title}",
            target_label=f"Active: {resume.title} (v{resume.version})"
        )
    elif req.target_version_id:
        v = db.query(ResumeVersion).filter(ResumeVersion.id == req.target_version_id, ResumeVersion.resume_id == id).first()
        if not v:
            raise HTTPException(status_code=404, detail="Target version snapshot not found")
        return compare_resumes(
            base_latex=v.latex_content,
            target_latex=resume.latex_content,
            base_label=f"Version v{v.version_number} ({v.change_summary or 'Checkpoint'})",
            target_label=f"Active Resume (v{resume.version})"
        )
    else:
        # Compare current with initial version 1 if available
        first_v = db.query(ResumeVersion).filter(ResumeVersion.resume_id == id).order_by(ResumeVersion.version_number.asc()).first()
        base_tex = first_v.latex_content if first_v else resume.latex_content
        base_label = f"Initial v1" if first_v else "Initial State"
        return compare_resumes(
            base_latex=base_tex,
            target_latex=resume.latex_content,
            base_label=base_label,
            target_label=f"Current v{resume.version}"
        )

@router.post("/{id}/quality-check")
def run_quality_check(id: int, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """
    Runs the 6-factor ATS Pre-Flight Quality Check:
      1. ATS Readability
      2. Formatting & Syntax Validation
      3. Grammar & Action Verbs
      4. Keyword Coverage
      5. Section Completeness
      6. Date & Chronological Consistency
    Returns overall score (0-100), letter grade, and actionable remediation findings.
    """
    resume = db.query(ResumeDocument).filter(ResumeDocument.id == id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume document not found")
    if resume.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this resume")
        
    opp = None
    if resume.target_opportunity_id:
        opp = db.query(Opportunity).filter(Opportunity.id == resume.target_opportunity_id).first()
        
    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    
    report = audit_resume_quality(
        latex_content=resume.latex_content,
        target_opportunity=opp,
        candidate_profile=cand
    )
    return report

@router.post("/{id}/optimize")
async def request_ai_optimization(
    id: int,
    req: ResumeOptimizeRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Generates AI optimization suggestions using Groq for explicit user review:
      - Skill gap & matching analysis strictly grounded in candidate profile
      - Highlighting candidate evidence (projects & experience)
      - Optimal section order
      - Action-verb STAR bullet improvements
      - Trimmable irrelevant content
    Strict Zero-Fabrication: Uses only verified facts from candidate profile.
    Preserves original resume if AI reasoning service is unavailable (HTTP 503).
    """
    resume = db.query(ResumeDocument).filter(ResumeDocument.id == id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume document not found")
    if resume.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this resume")
        
    opp = db.query(Opportunity).filter(Opportunity.id == req.opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Target opportunity not found")
    if opp.user_id is not None and opp.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this opportunity")
        
    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate profile not found")

    cand_dict = {
        "id": cand.id,
        "name": cand.name or "",
        "email": cand.email or "",
        "phone": cand.phone or "",
        "location": cand.location or "",
        "degree": cand.degree or "",
        "college": cand.college or "",
        "graduation_year": cand.graduation_year,
        "cgpa": cand.cgpa,
        "github_url": cand.github_url or "",
        "linkedin_url": cand.linkedin_url or "",
        "portfolio_url": cand.portfolio_url or "",
        "skills": cand.skills or [],
        "projects": cand.projects or [],
        "experience": cand.experience or [],
        "certifications": cand.certifications or [],
        "achievements": cand.achievements or []
    }
    opp_dict = {
        "id": opp.id,
        "title": opp.title,
        "company_name": opp.company_name,
        "description": opp.description or "",
        "extracted_data": opp.extracted_data or {},
        "required_skills": opp.required_skills or [],
        "preferred_skills": opp.preferred_skills or []
    }

    # Call Centralized AI Service (Groq)
    ai_res = await ai_service.tailor_resume(
        resume_latex=resume.latex_content,
        opportunity_data=opp_dict,
        profile_data=cand_dict
    )
    if not ai_res.get("success"):
        error_msg = ai_res.get("error", "AI reasoning service unavailable")
        raise HTTPException(
            status_code=503,
            detail="AI Optimization service unavailable. Original resume preserved."
        )

    safe_ai_data = validate_tailoring_safety(
        tailoring_data=ai_res.get("data", {}),
        candidate_skills=cand.skills,
        candidate_projects=cand.projects,
        candidate_experience=cand.experience
    )
        
    proposal = generate_resume_ai_optimization(
        resume=resume,
        opportunity=opp,
        profile=cand,
        db=db,
        ai_tailoring=safe_ai_data
    )
    return proposal

@router.post("/{id}/apply-optimization")
def apply_ai_optimization(
    id: int,
    req: ApplyOptimizationRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Commits user-approved optimization suggestions to the resume.
    Pre-validates that LaTeX compiles successfully before committing any changes.
    If compilation fails, rejects with HTTP 400 and preserves original resume without version increment.
    """
    resume = db.query(ResumeDocument).filter(ResumeDocument.id == id).with_for_update().first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume document not found")
    if resume.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this resume")
        
    next_version = resume.version + 1
    base_name = f"resume_{resume.id}_v{next_version}"
    target_pdf_path = os.path.join(STORAGE_DIR, f"{base_name}.pdf")
    target_tex_path = os.path.join(STORAGE_DIR, f"{base_name}.tex")
    tx = PDFPromotionTransaction(target_pdf_path, target_tex_path)

    # 1. Pre-validate compilation and layout BEFORE committing changes to the resume document
    resolved_page_size = determine_page_size(
        structured_data=resume.structured_content,
        latex_content=req.latex_content
    )
    resolved_target = determine_target_page_count(
        template_id=resume.template_id,
        structured_data=resume.structured_content or {},
        explicit_target=None
    )

    with tempfile.TemporaryDirectory(prefix="interniq_stage_") as stage_dir:
        # Step 1: Compilation into staging directory
        ok, staged_pdf_or_err, compiler = compile_latex(
            req.latex_content,
            base_name,
            strict=True,
            page_size=resolved_page_size,
            output_dir=stage_dir
        )
        if not ok:
            raise HTTPException(
                status_code=400,
                detail="Cannot apply optimization: LaTeX compilation failed. Your original resume was preserved unchanged."
            )

        # Step 2: PDF Layout Validation BEFORE promotion
        page_analysis = validate_pdf_layout(
            pdf_path=staged_pdf_or_err,
            target_page_count=resolved_target,
            structured_data=resume.structured_content,
            target_page_size=resolved_page_size
        )
        if page_analysis.get("validation_status") == "failed":
            err_msg = "; ".join(page_analysis.get("errors", [])) if page_analysis.get("errors") else "Layout validation failed"
            raise HTTPException(
                status_code=400,
                detail="Cannot apply optimization: LaTeX compilation failed. Your original resume was preserved unchanged."
            )

        # Step 3: Atomic file promotion under reversible transaction
        staged_tex = os.path.join(stage_dir, f"{base_name}.tex")
        tx.stage_and_promote(staged_pdf_or_err, staged_tex if os.path.exists(staged_tex) else None)

    # Step 4: Commit changes
    resume.latex_content = req.latex_content
    resume.version = next_version
    resume.pdf_path = target_pdf_path
    resume.pdf_generated_at = datetime.utcnow()
    resume.updated_at = datetime.utcnow()
    
    # Store layout metadata in structured_content if available
    if isinstance(resume.structured_content, dict):
        if not isinstance(resume.structured_content.get("metadata"), dict):
            resume.structured_content["metadata"] = {}
        resume.structured_content["metadata"]["layout_metadata"] = page_analysis
        resume.structured_content["metadata"]["page_size"] = resolved_page_size
        flag_modified(resume, "structured_content")
    
    # Create version snapshot
    snapshot = ResumeVersion(
        resume_id=resume.id,
        version_number=resume.version,
        title=resume.title,
        template_id=resume.template_id,
        latex_content=resume.latex_content,
        structured_content=resume.structured_content,
        pdf_path=resume.pdf_path,
        change_summary=req.change_summary or "Applied user-approved AI optimizations"
    )
    db.add(snapshot)

    # Step 5 & 6: Database commit and transactional cleanup/recovery
    try:
        db.commit()
        db.refresh(resume)
        tx.commit()
    except Exception as e:
        tx.rollback()
        db.rollback()
        logger.error(f"Database commit failed after optimization: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database commit failed after optimization")
    
    return serialize_resume(resume)

@router.post("/{id}/compile")
def compile_resume_pdf(
    id: int,
    req: Optional[CompileResumeRequest] = None,
    target_page_count: Optional[int] = Query(None),
    page_size: Optional[str] = Query(None),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Compile LaTeX source into ATS PDF via Tectonic with ReportLab fallback and validate layout budgeting."""
    resume = db.query(ResumeDocument).filter(ResumeDocument.id == id).with_for_update().first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume document not found")
    if resume.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this resume")
        
    explicit_target = req.target_page_count if req and req.target_page_count is not None else target_page_count
    explicit_page_size = req.page_size if req and req.page_size else page_size

    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    resolved_page_size = determine_page_size(
        explicit_page_size=explicit_page_size,
        structured_data=resume.structured_content,
        latex_content=resume.latex_content,
        profile_location=cand.location if cand else None
    )

    latex_content = resume.latex_content or ""
    if resolved_page_size == "a4" and "letterpaper" in latex_content:
        latex_content = re.sub(r'(\\documentclass\[[^\]]*)letterpaper([^\]]*\])', r'\1a4paper\2', latex_content)
        resume.latex_content = latex_content
    elif resolved_page_size == "letter" and "a4paper" in latex_content:
        latex_content = re.sub(r'(\\documentclass\[[^\]]*)a4paper([^\]]*\])', r'\1letterpaper\2', latex_content)
        resume.latex_content = latex_content

    base_name = f"resume_{resume.id}_v{resume.version}"
    target_pdf_path = os.path.join(STORAGE_DIR, f"{base_name}.pdf")
    target_tex_path = os.path.join(STORAGE_DIR, f"{base_name}.tex")
    tx = PDFPromotionTransaction(target_pdf_path, target_tex_path)

    resolved_target = determine_target_page_count(
        template_id=resume.template_id,
        structured_data=resume.structured_content or {},
        explicit_target=explicit_target
    )

    with tempfile.TemporaryDirectory(prefix="interniq_stage_") as stage_dir:
        # Step 1: Compilation into staging directory
        ok, staged_pdf_or_err, compiler = compile_latex(
            latex_content,
            base_name,
            page_size=resolved_page_size,
            output_dir=stage_dir
        )
        if not ok:
            raise HTTPException(status_code=500, detail="PDF compilation failed: LaTeX compilation error. Check the LaTeX diagnostics panel.")

        # Step 2: PDF Layout Validation BEFORE promotion
        page_analysis = validate_pdf_layout(
            pdf_path=staged_pdf_or_err,
            target_page_count=resolved_target,
            structured_data=resume.structured_content,
            target_page_size=resolved_page_size
        )
        if page_analysis.get("validation_status") == "failed":
            err_msg = "; ".join(page_analysis.get("errors", [])) if page_analysis.get("errors") else "Layout validation failed"
            raise HTTPException(status_code=500, detail="PDF compilation failed: LaTeX compilation error. Check the LaTeX diagnostics panel.")

        # Step 3: Atomic file promotion under reversible transaction
        staged_tex = os.path.join(stage_dir, f"{base_name}.tex")
        tx.stage_and_promote(staged_pdf_or_err, staged_tex if os.path.exists(staged_tex) else None)

    # Step 4: Database updates
    resume.pdf_path = target_pdf_path
    resume.pdf_generated_at = datetime.utcnow()
    
    # Store layout metadata in structured_content
    if isinstance(resume.structured_content, dict) and resume.structured_content.get("personal_info"):
        sc = resume.structured_content
    else:
        sc = get_or_initialize_structured_content(resume, db, persist=False).model_dump()

    if not isinstance(sc.get("metadata"), dict):
        sc["metadata"] = {}
    sc["metadata"]["layout_metadata"] = page_analysis
    sc["metadata"]["page_size"] = resolved_page_size
    if explicit_target:
        sc["metadata"]["target_page_count"] = explicit_target
    resume.structured_content = sc
    flag_modified(resume, "structured_content")
    
    # Step 5 & 6: Database commit and transactional cleanup/recovery
    try:
        db.commit()
        db.refresh(resume)
        tx.commit()
    except Exception as e:
        tx.rollback()
        db.rollback()
        logger.error(f"Failed to commit compilation metadata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database commit failed after compilation")
    
    return {
        "status": "compiled",
        "compiler_used": compiler,
        "pdf_url": f"/api/resumes/{resume.id}/pdf",
        "generated_at": resume.pdf_generated_at.isoformat(),
        "page_analysis": page_analysis
    }

@router.get("/{id}/pdf")
@router.get("/{id}/download")
def download_resume_pdf(id: int, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Download or preview the compiled PDF."""
    resume = db.query(ResumeDocument).filter(ResumeDocument.id == id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    if resume.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this resume")
        
    if not resume.pdf_path or not os.path.exists(resume.pdf_path):
        resume = db.query(ResumeDocument).filter(ResumeDocument.id == id).with_for_update().first()
        if not resume.pdf_path or not os.path.exists(resume.pdf_path):
            base_name = f"resume_{resume.id}_v{resume.version}"
            target_pdf_path = os.path.join(STORAGE_DIR, f"{base_name}.pdf")
            target_tex_path = os.path.join(STORAGE_DIR, f"{base_name}.tex")
            tx = PDFPromotionTransaction(target_pdf_path, target_tex_path)
            with tempfile.TemporaryDirectory(prefix="interniq_stage_") as stage_dir:
                ok, staged_pdf_or_err, _ = compile_latex(
                    resume.latex_content,
                    base_name,
                    output_dir=stage_dir
                )
                if not ok:
                    raise HTTPException(status_code=500, detail="Could not compile PDF: LaTeX compilation error.")
                staged_tex = os.path.join(stage_dir, f"{base_name}.tex")
                tx.stage_and_promote(staged_pdf_or_err, staged_tex if os.path.exists(staged_tex) else None)
            
            resume.pdf_path = target_pdf_path
            resume.pdf_generated_at = datetime.utcnow()
            try:
                db.commit()
                tx.commit()
            except Exception as e:
                tx.rollback()
                db.rollback()
                raise HTTPException(status_code=500, detail="Database commit failed after PDF generation")
        
    filename = f"{resume.title.replace(' ', '_').replace('/', '_')}.pdf"
    return FileResponse(
        resume.pdf_path,
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f'inline; filename="{filename}"'}
    )

@router.post("/tailor")
async def create_tailored_resume(
    req: TailorRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Generate a job-specific tailored LaTeX resume strictly grounded in candidate profile evidence using Groq.
    Preserves existing resume if Groq AI service is unavailable (HTTP 503).
    Does not automatically overwrite master resume.
    """
    opp = db.query(Opportunity).filter(Opportunity.id == req.opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    if opp.user_id is not None and opp.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this opportunity")
        
    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate profile not found")
        
    cand_dict = {
        "id": cand.id,
        "name": cand.name or "",
        "email": cand.email or "",
        "phone": cand.phone or "",
        "location": cand.location or "",
        "degree": cand.degree or "",
        "college": cand.college or "",
        "graduation_year": cand.graduation_year,
        "cgpa": cand.cgpa,
        "github_url": cand.github_url or "",
        "linkedin_url": cand.linkedin_url or "",
        "portfolio_url": cand.portfolio_url or "",
        "skills": cand.skills or [],
        "projects": cand.projects or [],
        "experience": cand.experience or [],
        "certifications": cand.certifications or [],
        "achievements": cand.achievements or []
    }
    
    opp_dict = {
        "id": opp.id,
        "title": opp.title,
        "company_name": opp.company_name,
        "description": opp.description or "",
        "extracted_data": opp.extracted_data or {},
        "required_skills": opp.required_skills or [],
        "preferred_skills": opp.preferred_skills or []
    }

    # Retrieve master resume or baseline template for user
    master = db.query(ResumeDocument).filter(
        ResumeDocument.user_id == user_id,
        ResumeDocument.is_master == True
    ).first()
    base_latex = master.latex_content if master else build_latex_template(cand_dict, template_id=req.template_id or "minimal_professional")

    # Call Centralized AI Service (Groq)
    ai_res = await ai_service.tailor_resume(
        resume_latex=base_latex,
        opportunity_data=opp_dict,
        profile_data=cand_dict
    )
    if not ai_res.get("success"):
        error_msg = ai_res.get("error", "AI reasoning service unavailable")
        raise HTTPException(
            status_code=503,
            detail="AI Tailoring service unavailable. Original resume preserved."
        )

    safe_ai_data = validate_tailoring_safety(
        tailoring_data=ai_res.get("data", {}),
        candidate_skills=cand.skills,
        candidate_projects=cand.projects,
        candidate_experience=cand.experience
    )
    
    tailored = tailor_resume_for_opportunity(
        candidate_profile_data=cand_dict,
        opportunity_data=opp_dict,
        template_id=req.template_id or "minimal_professional",
        ai_tailoring=safe_ai_data
    )
    
    resume = ResumeDocument(
        user_id=user_id,
        title=tailored["title"],
        template_id=tailored["template_id"],
        latex_content=tailored["latex_content"],
        target_opportunity_id=opp.id,
        target_company=opp.company_name,
        target_role=opp.title,
        is_master=False,
        version=1,
        tailored_insights=tailored["tailored_insights"]
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    
    # Save initial version snapshot
    v1 = ResumeVersion(
        resume_id=resume.id,
        version_number=1,
        title=resume.title,
        template_id=resume.template_id,
        latex_content=resume.latex_content,
        change_summary=f"Tailored specifically for {opp.company_name} - {opp.title} using Groq"
    )
    db.add(v1)
    db.commit()
    
    # Pre-compile PDF for instant preview (offloaded to thread to avoid blocking event loop)
    base_name = f"resume_{resume.id}_v1"
    ok, pdf_path, compiler = await asyncio.to_thread(compile_latex, resume.latex_content, base_name)
    if ok:
        resume.pdf_path = pdf_path
        resume.pdf_generated_at = datetime.utcnow()
        v1.pdf_path = pdf_path
        db.commit()
        db.refresh(resume)
        
    app_record = db.query(ApplicationRecord).filter(ApplicationRecord.opportunity_id == opp.id).first()
    if app_record:
        app_record.resume_id = resume.id
        app_record.resume_version_number = 1
        db.commit()
        
    return serialize_resume(resume)
