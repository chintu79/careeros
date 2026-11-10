"""
Unified Candidate Evidence Model Builder for CareerOS Matching Intelligence.
Aggregates candidate evidence across manually verified skills, curated projects,
professional experience, verified GitHub intelligence, structural signals,
and AI-derived project interpretations.
Strictly preserves evidence provenance and never treats unverified repository
ownership or AI hallucinations as verified candidate achievements.
"""
import re
import json
import hashlib
import logging
from typing import Dict, Any, List, Optional

from backend.app.models.candidate import CandidateProfile
from backend.app.schemas.matching import (
    CandidateEvidenceItem,
    UnifiedCandidateEvidence,
    EvidenceProvenanceType
)
from backend.app.services.matching.taxonomy import canonicalize_tech_name

logger = logging.getLogger(__name__)


def compute_candidate_evidence_hash(candidate: CandidateProfile) -> str:
    """Computes a deterministic SHA-256 hash of all candidate evidence inputs."""
    payload = json.dumps({
        "user_id": candidate.user_id,
        "name": candidate.name or "",
        "degree": candidate.degree or "",
        "graduation_year": candidate.graduation_year,
        "college": candidate.college or "",
        "skills": candidate.skills or [],
        "projects": candidate.projects or [],
        "experience": candidate.experience or [],
        "certifications": candidate.certifications or [],
        "github_intelligence": (candidate.github_data or {}).get("intelligence", {})
    }, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_experience_duration_years(duration_str: Optional[str]) -> float:
    """Parses text duration (e.g. '3 months', '1 year', '1.5 yrs') into fractional years."""
    if not duration_str:
        return 0.25 # baseline credit for internships
    d_lower = duration_str.lower()
    
    # Months match
    m_match = re.search(r'(\d+)\s*(?:months?|mos?)', d_lower)
    if m_match:
        return round(int(m_match.group(1)) / 12.0, 2)
        
    # Years match
    y_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:years?|yrs?)', d_lower)
    if y_match:
        return float(y_match.group(1))
        
    return 0.25


def build_unified_candidate_evidence(candidate: CandidateProfile) -> UnifiedCandidateEvidence:
    """
    Constructs an authoritative, provenance-tracked UnifiedCandidateEvidence instance.
    - Manually verified skills: is_verified=True, provenance=MANUAL_SKILL.
    - Curated projects: is_verified=True, provenance=CURATED_PROJECT.
    - Professional experience: is_verified=True, provenance=EXPERIENCE.
    - GitHub manifest tech: is_verified=True ONLY if candidate contribution is verified.
    - AI-derived project claims: is_verified=False, provenance=AI_DERIVED_PROJECT.
    """
    evidence_items: List[CandidateEvidenceItem] = []
    seen_evidence_keys = set() # (canonical_name, provenance, source_identifier)

    def _add_evidence(item: CandidateEvidenceItem):
        key = (item.canonical_name.lower(), item.provenance.value, item.source_identifier)
        if key not in seen_evidence_keys:
            seen_evidence_keys.add(key)
            evidence_items.append(item)

    # 1. Manually Verified Profile Skills
    for s in (candidate.skills or []):
        if isinstance(s, dict):
            s_name = s.get("name", "").strip()
            level = s.get("level")
            ev_text = s.get("evidence", "Verified in candidate profile")
        elif isinstance(s, str):
            s_name = s.strip()
            level = None
            ev_text = "Verified in candidate profile"
        else:
            continue

        if not s_name:
            continue

        canon = canonicalize_tech_name(s_name)
        _add_evidence(CandidateEvidenceItem(
            name=s_name,
            canonical_name=canon,
            provenance=EvidenceProvenanceType.MANUAL_SKILL,
            source_identifier="profile:skills",
            evidence_text=ev_text,
            is_verified=True,
            proficiency=level
        ))

    # 2. Curated Projects
    for proj in (candidate.projects or []):
        p_title = proj.get("title", "Project")
        p_desc = proj.get("description", "")
        p_id = proj.get("id") or p_title
        p_techs = proj.get("tech_stack") or []

        for t in p_techs:
            if not t or not str(t).strip():
                continue
            t_str = str(t).strip()
            canon = canonicalize_tech_name(t_str)
            _add_evidence(CandidateEvidenceItem(
                name=t_str,
                canonical_name=canon,
                provenance=EvidenceProvenanceType.CURATED_PROJECT,
                source_identifier=f"project:{p_id}",
                evidence_text=f"Demonstrated in curated project '{p_title}': {p_desc[:120]}",
                is_verified=True
            ))

    # 3. Professional Experience
    total_exp_years = 0.0
    for exp in (candidate.experience or []):
        c_name = exp.get("company", "Company")
        e_title = exp.get("title", "Role")
        e_dur = exp.get("duration")
        total_exp_years += parse_experience_duration_years(e_dur)

        e_desc = exp.get("description", "")
        # Scan experience description for mentioned canonical tech
        words = re.findall(r'\b[A-Za-z0-9#\+\.-]+\b', e_desc)
        for w in words:
            canon = canonicalize_tech_name(w)
            # Only add if recognized canonical tech
            if canon.lower() != w.lower() or canon.lower() in [
                "python", "javascript", "typescript", "c++", "c#", "go", "rust",
                "java", "sql", "react", "fastapi", "flask", "django", "docker",
                "kubernetes", "aws", "gcp", "postgresql", "mongodb", "redis"
            ]:
                _add_evidence(CandidateEvidenceItem(
                    name=w,
                    canonical_name=canon,
                    provenance=EvidenceProvenanceType.EXPERIENCE,
                    source_identifier=f"experience:{c_name}",
                    evidence_text=f"Applied in professional role '{e_title}' at {c_name}: {e_desc[:120]}",
                    is_verified=True
                ))

    # 4. GitHub Project Intelligence
    github_data = candidate.github_data or {}
    intel_map = github_data.get("intelligence", {})

    for full_name, repo_data in intel_map.items():
        if not isinstance(repo_data, dict):
            continue

        is_contrib_verified = repo_data.get("candidate_contribution_verified", False)
        repo_name = repo_data.get("repo_name", full_name)

        # 4A. Deterministic Manifest Technologies
        for t in repo_data.get("detected_technologies", []):
            t_name = t.get("name") if isinstance(t, dict) else str(t)
            t_src = t.get("source_file", "manifest") if isinstance(t, dict) else "manifest"
            if not t_name:
                continue

            canon = canonicalize_tech_name(t_name)
            if is_contrib_verified:
                # Verified candidate contribution
                _add_evidence(CandidateEvidenceItem(
                    name=t_name,
                    canonical_name=canon,
                    provenance=EvidenceProvenanceType.GITHUB_MANIFEST,
                    source_identifier=f"github:{full_name}:{t_src}",
                    evidence_text=f"Direct dependency in verified candidate repository {full_name} ({t_src})",
                    is_verified=True
                ))
            else:
                # Candidate contribution unverified: record as unverified evidence
                _add_evidence(CandidateEvidenceItem(
                    name=t_name,
                    canonical_name=canon,
                    provenance=EvidenceProvenanceType.GITHUB_MANIFEST,
                    source_identifier=f"github:{full_name}:{t_src}",
                    evidence_text=f"Repository {full_name} dependency; unverified candidate commit authorship",
                    is_verified=False
                ))

        # 4B. Structural Topology Signals
        for s in repo_data.get("structure_signals", []):
            s_name = s.get("signal_name") if isinstance(s, dict) else str(s)
            if s_name and is_contrib_verified:
                _add_evidence(CandidateEvidenceItem(
                    name=s_name,
                    canonical_name=s_name,
                    provenance=EvidenceProvenanceType.GITHUB_TOPOLOGY,
                    source_identifier=f"github:{full_name}:topology",
                    evidence_text=f"Structural architecture in {full_name}",
                    is_verified=True
                ))

        # 4C. AI-Derived Insights (Clearly labeled, never verified alone)
        ai_insights = repo_data.get("ai_insights") or {}
        for ai_tech in ai_insights.get("technology_stack", []):
            canon = canonicalize_tech_name(ai_tech)
            _add_evidence(CandidateEvidenceItem(
                name=ai_tech,
                canonical_name=canon,
                provenance=EvidenceProvenanceType.AI_DERIVED_PROJECT,
                source_identifier=f"github:{full_name}:ai_insight",
                evidence_text=f"AI-derived interpretation for {full_name} (unverified without manifest proof)",
                is_verified=False
            ))

    # 5. Education Package
    edu_dict = {
        "degree": candidate.degree or "",
        "graduation_year": candidate.graduation_year or 2026,
        "college": candidate.college or "",
        "cgpa": candidate.cgpa
    }

    # 6. Certifications
    certs = list(candidate.certifications or [])
    for cert in certs:
        c_str = cert if isinstance(cert, str) else cert.get("name", str(cert))
        _add_evidence(CandidateEvidenceItem(
            name=c_str,
            canonical_name=canonicalize_tech_name(c_str),
            provenance=EvidenceProvenanceType.CERTIFICATION,
            source_identifier="profile:certifications",
            evidence_text=f"Candidate certified credential: {c_str}",
            is_verified=True
        ))

    content_hash = compute_candidate_evidence_hash(candidate)

    return UnifiedCandidateEvidence(
        candidate_id=candidate.id,
        user_id=candidate.user_id,
        evidence_items=evidence_items,
        education=edu_dict,
        experience_years=round(total_exp_years, 2),
        certifications=certs,
        content_hash=content_hash
    )
