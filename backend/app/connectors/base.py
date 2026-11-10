import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional, Set
from sqlalchemy.orm import Session
from datetime import datetime

from backend.app.pipeline.normalizer import normalize_job_dict
from backend.app.pipeline.duplicate_detector import find_duplicate_opportunity, merge_duplicate_opportunity
from backend.app.pipeline.validity_checker import check_opportunity_validity
from backend.app.pipeline.internship_filter import is_valid_internship
from backend.app.services.verifier import verify_url_live
from backend.app.services.quality_scorer import calculate_internship_quality_score
from backend.app.ai.extractor import extract_job_requirements
from backend.app.ai.compatibility_scorer import evaluate_compatibility
from backend.app.ai.ollama_client import ollama_client
from backend.app.models.opportunity import Opportunity
from backend.app.models.candidate import CandidateProfile
from backend.app.models.preferences import UserPreferences
from backend.app.services.discovery_snapshot_manager import snapshot_manager

logger = logging.getLogger(__name__)

class BaseConnector(ABC):
    def __init__(
        self, 
        name: str, 
        source_type: str,
        health_status: str = "operational",
        rate_limit_delay: float = 0.5,
        max_retries: int = 3
    ):
        self.name = name
        self.source_type = source_type
        self.health_status = health_status
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.last_sync_timestamp: Optional[datetime] = None

    @abstractmethod
    async def fetch_jobs(self, **kwargs) -> List[Dict[str, Any]]:
        """Fetch raw listings from the source with error isolation, pagination, and rate limiting."""
        pass

    async def check_health(self) -> Dict[str, Any]:
        """Perform a lightweight health probe to verify source connectivity."""
        return {
            "source": self.name,
            "source_type": self.source_type,
            "status": self.health_status,
            "last_sync": self.last_sync_timestamp.isoformat() if self.last_sync_timestamp else None
        }

    def normalize_job(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Stage 2: Normalize listing to CareerOS standard structure."""
        return normalize_job_dict(raw)

    def validate_job(self, job_data: Dict[str, Any]) -> str:
        """Stage 4: Expiration & validity check."""
        return check_opportunity_validity(job_data)

    def reconcile_active_board_listings(
        self, 
        db: Session, 
        active_original_urls: List[str], 
        source_platform: Optional[str] = None,
        company_name: Optional[str] = None
    ) -> int:
        """
        Board Reconciliation:
        Identifies opportunities previously discovered from this source/board that are
        no longer returned in the active board payload. Transitions their status to
        'closed' / 'removed_from_source' and updates last_verified_at.
        """
        if not active_original_urls:
            return 0
        
        target_platform = (source_platform or self.name).lower()
        query = db.query(Opportunity).filter(
            Opportunity.source_platform.ilike(f"%{target_platform}%"),
            Opportunity.status.in_(["verified", "active_verified", "newly_discovered"])
        )
        if company_name:
            query = query.filter(Opportunity.company_name.ilike(company_name.strip()))
            
        existing_candidates = query.all()
        active_set = set(active_original_urls)
        closed_count = 0
        now = datetime.utcnow()
        
        for opp in existing_candidates:
            is_active = (opp.original_url in active_set) or any(
                link.get("url") in active_set for link in (opp.source_links or [])
            )
            if not is_active:
                opp.status = "closed"
                opp.last_verified_at = now
                closed_count += 1
                
        if closed_count > 0:
            db.commit()
            logger.info(f"Reconciled {closed_count} closed opportunities for {target_platform} / {company_name}")
        return closed_count

    async def process_and_save_jobs(
        self, 
        db: Session, 
        raw_jobs: List[Dict[str, Any]],
        verify_links: bool = True,
        reconcile_board: bool = False,
        reconcile_company: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Execute full 5-stage pipeline on incoming raw listings:
        1. Normalization
        2. Strict Internship Filter (reject full-time, senior roles, scams)
        3. Expiration / Active URL Verification Probe
        4. Multi-tier Duplicate detection & merging
        5. Quality Scoring & Candidate Profile matching
        6. Embedding generation & PostgreSQL storage
        7. Optional Board Reconciliation
        """
        stats = {
            "retrieved": len(raw_jobs),
            "new": 0,
            "updated": 0,
            "duplicate": 0,
            "expired": 0,
            "relevant": 0,
            "errors": 0,
            "reconciled_closed": 0
        }
        
        active_urls_seen: List[str] = []
        
        # Fetch candidate profile & preferences for scoring
        candidate = db.query(CandidateProfile).first()
        cand_dict = {
            "skills": candidate.skills if candidate else [],
            "projects": candidate.projects if candidate else [],
            "graduation_year": candidate.graduation_year if candidate else 2026,
            "degree": candidate.degree if candidate else "B.Tech CSE"
        }
        
        prefs = db.query(UserPreferences).first()
        pref_dict = {
            "paid_only": prefs.paid_only if prefs else True,
            "allow_unpaid": prefs.allow_unpaid if prefs else False,
            "min_stipend": prefs.min_stipend if prefs else 10000.0,
            "graduation_year": prefs.graduation_year if prefs else 2026,
            "excluded_companies": prefs.excluded_companies if prefs else [],
            "excluded_keywords": prefs.excluded_keywords if prefs else []
        }

        for raw in raw_jobs:
            try:
                # Stage 2: Normalization
                norm = self.normalize_job(raw)
                norm["source_platform"] = norm.get("source_platform") or self.name.lower()
                
                # Strict Internship Filtering
                valid, rejection_reason = is_valid_internship(
                    title=norm["title"],
                    description=norm["description"],
                    company_name=norm["company_name"],
                    url=norm["original_url"]
                )
                if not valid:
                    logger.debug(f"Rejected non-internship '{norm['title']}': {rejection_reason}")
                    continue

                # Stage 4: URL Verification & Expiration Probe
                verification = {}
                if verify_links:
                    verification = await verify_url_live(norm.get("application_url") or norm["original_url"])
                    norm["status"] = verification["listing_status"]
                    if norm["status"] == "expired":
                        stats["expired"] += 1
                else:
                    norm["status"] = self.validate_job(norm)

                # Stage 3: Duplicate Detection
                active_urls_seen.append(norm["original_url"])
                is_dup, existing = find_duplicate_opportunity(db, norm)
                if is_dup and existing:
                    merge_duplicate_opportunity(existing, norm)
                    db.commit()
                    snapshot_manager.invalidate_opportunity_snapshots(opportunity_id=existing.id, db=db)
                    stats["duplicate"] += 1
                    stats["updated"] += 1
                    continue

                # Calculate Explainable Quality Score
                quality_res = calculate_internship_quality_score(norm, query_context=norm.get("normalized_title", ""))
                norm["quality_score"] = quality_res["quality_score"]
                norm["quality_breakdown"] = quality_res["quality_breakdown"]
                    
                # Stage 5: AI-powered extraction and compatibility
                extracted = await extract_job_requirements(norm["title"], norm["description"])
                match_result = evaluate_compatibility(
                    extracted_data=extracted,
                    candidate_profile=cand_dict,
                    user_preferences=pref_dict,
                    job_location=norm["normalized_location"],
                    workplace_type=norm["workplace_type"],
                    is_paid=norm["is_paid"],
                    stipend_amount=norm["min_stipend"],
                    job_company=norm["company_name"]
                )
                
                # Semantic Embedding via BGE-M3
                embed_text = f"{norm['title']} at {norm['company_name']}. {norm['description'][:600]}"
                embedding = await ollama_client.get_embedding(embed_text)
                
                initial_source_link = [{
                    "source": norm["source_platform"],
                    "url": norm["original_url"],
                    "discovered_at": (norm.get("posted_at") or datetime.utcnow()).isoformat() if isinstance(norm.get("posted_at"), datetime) else str(norm.get("posted_at"))
                }]
                
                safe_raw = {}
                for k, v in (norm.get("raw_data") or {}).items():
                    if isinstance(v, datetime):
                        safe_raw[k] = v.isoformat()
                    else:
                        safe_raw[k] = v

                opp = Opportunity(
                    title=norm["title"],
                    normalized_title=norm["normalized_title"],
                    company_name=norm["company_name"],
                    company_website=norm.get("company_website", ""),
                    location=norm["location"],
                    normalized_location=norm["normalized_location"],
                    workplace_type=norm["workplace_type"],
                    internship_type=norm.get("internship_type", "in-office"),
                    internship_category=norm.get("internship_category", "software_engineering"),
                    work_mode=norm.get("work_mode", "full-time"),
                    employment_type="internship",
                    description=norm["description"],
                    required_skills=norm.get("required_skills") or extracted.get("mandatory_technical_skills", []),
                    preferred_skills=norm.get("preferred_skills") or extracted.get("preferred_skills", []),
                    eligibility=norm.get("eligibility") or extracted.get("degree_requirement") or None,
                    experience_required=norm.get("experience_required", "0-1 years / Fresher"),
                    stipend_text=norm["stipend_text"],
                    min_stipend=norm["min_stipend"],
                    max_stipend=norm["max_stipend"],
                    currency=norm["currency"],
                    stipend_period=norm["stipend_period"],
                    is_paid=norm["is_paid"],
                    compensation_type=norm.get("compensation_type", "undisclosed"),
                    duration_months=norm["duration_months"],
                    posted_at=norm.get("posted_at"),
                    deadline_at=norm.get("deadline_at"),
                    discovered_at=datetime.utcnow(),
                    last_fetched_at=datetime.utcnow(),
                    last_verified_at=datetime.utcnow(),
                    status=norm["status"],
                    original_url=norm["original_url"],
                    application_url=norm.get("application_url") or norm["original_url"],
                    source_url=norm.get("source_url") or norm["original_url"],
                    external_id=norm.get("external_id"),
                    source_platform=norm["source_platform"],
                    source_links=initial_source_link,
                    verification_details=verification,
                    quality_score=norm["quality_score"],
                    quality_breakdown=norm["quality_breakdown"],
                    raw_data=safe_raw,
                    embedding=embedding,
                    extracted_data=extracted,
                    match_analysis=match_result,
                    match_score=match_result["match_score"],
                    eligibility_status=match_result["eligibility_status"]
                )
                db.add(opp)
                db.commit()
                stats["new"] += 1
                if match_result["match_score"] >= 65 and match_result["eligibility_status"] != "disqualified":
                    stats["relevant"] += 1
            except Exception as e:
                logger.error(f"Error processing job in {self.name}: {e}", exc_info=True)
                db.rollback()
                stats["errors"] += 1

        # Execute board reconciliation if requested
        if reconcile_board and active_urls_seen:
            closed_cnt = self.reconcile_active_board_listings(
                db=db,
                active_original_urls=active_urls_seen,
                source_platform=self.name,
                company_name=reconcile_company
            )
            stats["reconciled_closed"] = closed_cnt

        return stats

