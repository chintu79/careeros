from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON, ForeignKey, Index
from pgvector.sqlalchemy import VECTOR
from backend.app.database import Base


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Opportunity(Base):
    __tablename__ = "opportunities"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    title = Column(String(300), nullable=False, index=True)
    normalized_title = Column(String(300), nullable=False, index=True)
    company_name = Column(String(255), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    company_website = Column(String(1000), nullable=True)
    
    location = Column(String(255), nullable=True)
    normalized_location = Column(String(255), nullable=True, index=True)
    workplace_type = Column(String(50), default="onsite", index=True) # remote, hybrid, onsite
    internship_type = Column(String(50), default="in-office", index=True) # in-office, remote, hybrid
    work_mode = Column(String(50), default="full-time", index=True) # full-time, part-time
    employment_type = Column(String(50), default="internship", index=True) # internship, entry_level, full_time
    internship_category = Column(String(100), nullable=True, index=True) # software_engineering, ai_ml, data_science, frontend, backend, fullstack, devops_cloud, other
    
    description = Column(Text, nullable=True)
    required_skills = Column(JSON, default=list)
    preferred_skills = Column(JSON, default=list)
    eligibility = Column(Text, nullable=True)
    experience_required = Column(String(255), default="0-1 years / Fresher")
    
    # Stipend & Compensation
    stipend_text = Column(String(150), nullable=True)
    min_stipend = Column(Float, nullable=True)
    max_stipend = Column(Float, nullable=True)
    currency = Column(String(20), default="INR")
    stipend_period = Column(String(30), default="month") # month, year, lump_sum, hour
    is_paid = Column(Boolean, default=True, index=True)
    compensation_type = Column(String(50), default="undisclosed", index=True) # paid, unpaid, undisclosed
    duration_months = Column(Integer, nullable=True)
    
    # Dates
    posted_at = Column(DateTime, nullable=True, index=True)
    deadline_at = Column(DateTime, nullable=True, index=True)
    discovered_at = Column(DateTime, default=utc_now, index=True)
    last_fetched_at = Column(DateTime, default=utc_now, index=True)
    last_verified_at = Column(DateTime, default=utc_now)
    
    # Source & Verification
    status = Column(String(50), default="verified", index=True) # verified, unverified, expired, closed, stale, failed_verification
    original_url = Column(String(1000), nullable=False, unique=True, index=True)
    application_url = Column(String(1000), nullable=True)
    source_url = Column(String(1000), nullable=True)
    external_id = Column(String(255), nullable=True, index=True)
    source_platform = Column(String(50), nullable=False, index=True)
    verification_details = Column(JSON, default=dict)
    
    # Quality Scorer
    quality_score = Column(Float, default=0.0, index=True)
    quality_breakdown = Column(JSON, default=dict)
    
    # Duplicate merging: preserve all source references
    source_links = Column(JSON, default=list) # [{"source": "...", "url": "...", "discovered_at": "..."}]
    raw_data = Column(JSON, default=dict)
    
    # 1024-dimensional semantic embedding via BGE-M3
    embedding = Column(VECTOR(1024), nullable=True)
    
    # Extracted structured requirements from local Ollama LLM
    extracted_data = Column(JSON, default=dict)
    
    # Transparent candidate matching details
    match_analysis = Column(JSON, default=dict)
    match_score = Column(Float, default=0.0, index=True)
    eligibility_status = Column(String(50), default="eligible", index=True) # eligible, flagged, disqualified
    
    # User interaction states
    is_saved = Column(Boolean, default=False, index=True)
    is_dismissed = Column(Boolean, default=False, index=True)
    is_applied = Column(Boolean, default=False, index=True)
    user_notes = Column(Text, nullable=True)
    recommendation_impressions = Column(Integer, default=0, index=True)
    
    content_version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    def to_standard_record(self) -> dict:
        """Convert Opportunity instance into the strict 24-field standardized schema required by Section 4."""
        dur_str = f"{self.duration_months} months" if self.duration_months else "Flexible / Not specified"
        
        # Determine clean internship type
        itype = self.internship_type or "in-office"
        if self.workplace_type == "remote" or "remote" in (self.location or "").lower():
            itype = "remote"
        elif self.workplace_type == "hybrid" or "hybrid" in (self.location or "").lower():
            itype = "hybrid"

        req_skills = self.required_skills or []
        pref_skills = self.preferred_skills or []
        if not req_skills and self.extracted_data:
            req_skills = self.extracted_data.get("mandatory_technical_skills", [])
        if not pref_skills and self.extracted_data:
            pref_skills = self.extracted_data.get("preferred_skills", [])

        # Format dates
        deadline_str = self.deadline_at.isoformat() if self.deadline_at else None
        posted_str = self.posted_at.isoformat() if self.posted_at else None
        verified_str = self.last_verified_at.isoformat() if self.last_verified_at else None
        fetched_str = self.last_fetched_at.isoformat() if self.last_fetched_at else None

        app_url = self.application_url or self.original_url
        src_url = self.source_url or self.original_url

        # Clean status taxonomy: verified, unverified, expired, closed, stale, failed_verification
        l_status = self.status or "verified"
        if l_status in ["active"]:
            l_status = "verified"
        elif l_status in ["possibly_expired"]:
            l_status = "expired"

        return {
            "job_id": str(self.id),
            "internship_title": self.title,
            "company_name": self.company_name,
            "company_website": self.company_website or "",
            "job_description": self.description or "",
            "required_skills": req_skills,
            "preferred_skills": pref_skills,
            "internship_type": itype,
            "internship_category": self.internship_category or "software_engineering",
            "work_mode": self.work_mode or "full-time",
            "location": self.location or "India",
            "stipend_min": self.min_stipend,
            "stipend_max": self.max_stipend,
            "stipend_currency": self.currency or "INR",
            "duration": dur_str,
            "eligibility": self.eligibility or (self.extracted_data or {}).get("degree_requirement") or None,
            "experience_required": self.experience_required or "0-1 years / Fresher",
            "application_deadline": deadline_str,
            "posted_date": posted_str,
            "first_discovered_at": self.discovered_at.isoformat() if self.discovered_at else None,
            "last_fetched_at": fetched_str,
            "application_url": app_url,
            "source_name": self.source_platform,
            "source_url": src_url,
            "source_job_id": self.external_id or f"local_{self.id}",
            "last_verified_at": verified_str,
            "listing_status": l_status,
            "quality_score": round(self.quality_score, 1) if self.quality_score else 0.0,
            "quality_breakdown": self.quality_breakdown or {}
        }

Index("idx_opportunity_feed", Opportunity.status, Opportunity.is_dismissed, Opportunity.match_score.desc())
