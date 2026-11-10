import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.app.connectors.internshala import InternshalaConnector
from backend.app.connectors.linkedin import LinkedInJobsConnector
from backend.app.connectors.greenhouse import GreenhouseConnector, DEFAULT_GREENHOUSE_BOARDS
from backend.app.connectors.ashby import AshbyConnector, DEFAULT_ASHBY_ORGS
from backend.app.connectors.lever import LeverConnector, DEFAULT_LEVER_SITES
from backend.app.connectors.smartrecruiters import SmartRecruitersConnector
from backend.app.connectors.remotive import RemotiveConnector
from backend.app.connectors.remoteok import RemoteOKConnector
from backend.app.connectors.adzuna import AdzunaConnector
from backend.app.connectors.india_platforms import INDIA_PLATFORMS

from backend.app.pipeline.normalizer import normalize_job_dict
from backend.app.pipeline.internship_filter import is_valid_internship
from backend.app.pipeline.duplicate_detector import find_duplicate_opportunity, merge_duplicate_opportunity
from backend.app.services.verifier import verify_url_live
from backend.app.services.quality_scorer import calculate_internship_quality_score
from backend.app.models.opportunity import Opportunity

logger = logging.getLogger(__name__)

SCENARIO_CONFIGS = {
    "Test A": {
        "name": "AI/ML Intern in India",
        "internshala_query": "ai",
        "internshala_loc": "India",
        "linkedin_query": "AI ML Intern",
        "linkedin_loc": "India",
        "keywords": ["ai", "machine learning", "ml", "deep learning", "artificial intelligence"]
    },
    "Test B": {
        "name": "Full Stack Developer Intern in Pune",
        "internshala_query": "full-stack",
        "internshala_loc": "pune",
        "linkedin_query": "Full Stack Developer Intern",
        "linkedin_loc": "Pune",
        "keywords": ["full stack", "fullstack", "web development", "react", "node"]
    },
    "Test C": {
        "name": "Remote Software Development Intern",
        "internshala_query": "software",
        "internshala_loc": "work-from-home",
        "linkedin_query": "Software Engineer Intern",
        "linkedin_loc": "Remote",
        "keywords": ["software", "developer", "backend", "frontend", "sde"]
    },
    "Test D": {
        "name": "Data Science Intern in India",
        "internshala_query": "data-science",
        "internshala_loc": "India",
        "linkedin_query": "Data Science Intern",
        "linkedin_loc": "India",
        "keywords": ["data science", "data scientist", "data analyst", "data engineering"]
    },
    "Test E": {
        "name": "Python Developer Intern in India",
        "internshala_query": "python",
        "internshala_loc": "India",
        "linkedin_query": "Python Developer Intern",
        "linkedin_loc": "India",
        "keywords": ["python", "django", "fastapi", "backend"]
    }
}

async def execute_scenario(
    scenario_key: str, 
    db: Session,
    max_records: int = 15
) -> Dict[str, Any]:
    """
    Execute a specific test scenario across all available sources,
    applying strict internship filtering, active URL verification, and quality scoring.
    """
    cfg = SCENARIO_CONFIGS.get(scenario_key)
    if not cfg:
        raise ValueError(f"Unknown scenario key: {scenario_key}")

    scenario_name = cfg["name"]
    sources_queried = []
    sources_failed = []
    raw_collected: List[Dict[str, Any]] = []

    # 1. Internshala
    try:
        sources_queried.append("Internshala")
        c_ish = InternshalaConnector()
        jobs_ish = await c_ish.fetch_jobs(
            query=cfg["internshala_query"],
            location=cfg["internshala_loc"],
            limit=max_records
        )
        raw_collected.extend(jobs_ish)
    except Exception as e:
        sources_failed.append({"source": "Internshala", "reason": str(e)})

    # 2. LinkedIn Guest Search
    try:
        sources_queried.append("LinkedIn Jobs")
        c_li = LinkedInJobsConnector()
        jobs_li = await c_li.fetch_jobs(
            query=cfg["linkedin_query"],
            location=cfg["linkedin_loc"],
            limit=max_records
        )
        raw_collected.extend(jobs_li)
    except Exception as e:
        sources_failed.append({"source": "LinkedIn Jobs", "reason": str(e)})

    # 3. Greenhouse ATS
    try:
        sources_queried.append("Greenhouse ATS")
        c_gh = GreenhouseConnector()
        jobs_gh = await c_gh.fetch_jobs(boards=DEFAULT_GREENHOUSE_BOARDS)
        # Filter matching scenario keywords
        matching_gh = [
            j for j in jobs_gh 
            if any(k in j.get("title", "").lower() for k in cfg["keywords"])
        ]
        raw_collected.extend(matching_gh)
    except Exception as e:
        sources_failed.append({"source": "Greenhouse ATS", "reason": str(e)})

    # 4. Ashby ATS
    try:
        sources_queried.append("Ashby ATS")
        c_ash = AshbyConnector()
        jobs_ash = await c_ash.fetch_jobs(orgs=DEFAULT_ASHBY_ORGS)
        matching_ash = [
            j for j in jobs_ash 
            if any(k in j.get("title", "").lower() for k in cfg["keywords"])
        ]
        raw_collected.extend(matching_ash)
    except Exception as e:
        sources_failed.append({"source": "Ashby ATS", "reason": str(e)})

    # 5. Lever ATS
    try:
        sources_queried.append("Lever ATS")
        c_lev = LeverConnector()
        jobs_lev = await c_lev.fetch_jobs(sites=DEFAULT_LEVER_SITES)
        matching_lev = [
            j for j in jobs_lev 
            if any(k in j.get("title", "").lower() for k in cfg["keywords"])
        ]
        raw_collected.extend(matching_lev)
    except Exception as e:
        sources_failed.append({"source": "Lever ATS", "reason": str(e)})

    # 6. SmartRecruiters ATS
    try:
        sources_queried.append("SmartRecruiters ATS")
        c_sr = SmartRecruitersConnector()
        jobs_sr = await c_sr.fetch_jobs()
        raw_collected.extend(jobs_sr)
    except Exception as e:
        sources_failed.append({"source": "SmartRecruiters ATS", "reason": str(e)})

    # 7. Remotive API
    try:
        sources_queried.append("Remotive API")
        c_rem = RemotiveConnector()
        jobs_rem = await c_rem.fetch_jobs()
        matching_rem = [
            j for j in jobs_rem 
            if any(k in j.get("title", "").lower() for k in cfg["keywords"])
        ]
        raw_collected.extend(matching_rem)
    except Exception as e:
        sources_failed.append({"source": "Remotive API", "reason": str(e)})

    # 8. RemoteOK API
    try:
        sources_queried.append("Remote OK API")
        c_rok = RemoteOKConnector()
        jobs_rok = await c_rok.fetch_jobs()
        matching_rok = [
            j for j in jobs_rok 
            if any(k in j.get("title", "").lower() for k in cfg["keywords"])
        ]
        raw_collected.extend(matching_rok)
    except Exception as e:
        sources_failed.append({"source": "Remote OK API", "reason": str(e)})

    # 9. Adzuna API
    try:
        sources_queried.append("Adzuna API")
        c_adz = AdzunaConnector()
        jobs_adz = await c_adz.fetch_jobs()
        if not jobs_adz:
            sources_failed.append({
                "source": "Adzuna API",
                "reason": "API credentials (ADZUNA_APP_ID, ADZUNA_APP_KEY) not configured in environment"
            })
        raw_collected.extend(jobs_adz)
    except Exception as e:
        sources_failed.append({"source": "Adzuna API", "reason": str(e)})

    # 10. Document India Portal Statuses
    for p_key, p_info in INDIA_PLATFORMS.items():
        if p_key in ["internshala", "linkedin"]:
            continue
        sources_queried.append(p_info["name"])
        sources_failed.append({
            "source": p_info["name"],
            "reason": p_info.get("failure_reason", "Automated sync requires session credentials or is blocked by Cloudflare firewall. Manual URL import active.")
        })

    # Metrics trackers
    retrieved_count = len(raw_collected)
    duplicates_removed_count = 0
    expired_count = 0
    missing_app_urls = 0
    missing_src_urls = 0
    seen_urls = set()
    unique_records: List[Dict[str, Any]] = []

    # Process and verify collected records
    for raw in raw_collected:
        norm = normalize_job_dict(raw)
        app_url = norm.get("application_url") or norm.get("original_url") or ""
        src_url = norm.get("source_url") or norm.get("original_url") or ""

        if not app_url:
            missing_app_urls += 1
            continue
        if not src_url:
            missing_src_urls += 1

        # Deduplication check by canonical application URL
        clean_key = app_url.split("?")[0].rstrip("/")
        if clean_key in seen_urls:
            duplicates_removed_count += 1
            continue
        seen_urls.add(clean_key)

        # Strict validation
        is_valid, reject_reason = is_valid_internship(
            title=norm["title"],
            description=norm["description"],
            company_name=norm["company_name"],
            url=app_url
        )
        if not is_valid:
            continue

        # Active HTTP Probe for verification
        verif = await verify_url_live(app_url, timeout=6.0)
        listing_status = verif["listing_status"]
        if listing_status == "expired":
            expired_count += 1

        norm["status"] = listing_status
        norm["listing_status"] = listing_status
        norm["verification_details"] = verif

        # Calculate Quality Score
        q_eval = calculate_internship_quality_score(norm, query_context=cfg["name"])
        norm["quality_score"] = q_eval["quality_score"]
        norm["quality_breakdown"] = q_eval["quality_breakdown"]

        # Ensure raw_data is safely JSON serializable
        safe_raw = {}
        for k, v in (norm.get("raw_data") or {}).items():
            if isinstance(v, datetime):
                safe_raw[k] = v.isoformat()
            else:
                safe_raw[k] = v

        # Persist or update in database
        existing = db.query(Opportunity).filter(Opportunity.original_url == norm["original_url"]).first()
        if not existing:
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
                required_skills=norm.get("required_skills", []),
                preferred_skills=norm.get("preferred_skills", []),
                eligibility=norm.get("eligibility") or None,
                experience_required=norm.get("experience_required", "0-1 years / Fresher"),
                stipend_text=norm["stipend_text"],
                min_stipend=norm["min_stipend"],
                max_stipend=norm["max_stipend"],
                currency=norm["currency"],
                stipend_period=norm["stipend_period"],
                is_paid=norm["is_paid"],
                compensation_type=norm.get("compensation_type", "undisclosed"),
                duration_months=norm["duration_months"],
                posted_at=norm.get("posted_at") or datetime.utcnow(),
                deadline_at=norm.get("deadline_at"),
                discovered_at=datetime.utcnow(),
                last_fetched_at=datetime.utcnow(),
                last_verified_at=datetime.utcnow(),
                status=listing_status,
                original_url=norm["original_url"],
                application_url=app_url,
                source_url=src_url,
                external_id=norm.get("external_id"),
                source_platform=norm["source_platform"],
                source_links=[{"source": norm["source_platform"], "url": app_url, "discovered_at": datetime.utcnow().isoformat()}],
                verification_details=verif,
                quality_score=norm["quality_score"],
                quality_breakdown=norm["quality_breakdown"],
                raw_data=safe_raw
            )
            db.add(opp)
            db.commit()
            db.refresh(opp)
            standard_record = opp.to_standard_record()
        else:
            existing.last_verified_at = datetime.utcnow()
            existing.status = listing_status
            existing.quality_score = norm["quality_score"]
            existing.quality_breakdown = norm["quality_breakdown"]
            db.commit()
            standard_record = existing.to_standard_record()

        unique_records.append(standard_record)

    verified_live_count = sum(1 for r in unique_records if r["listing_status"] == "active")

    return {
        "scenario": scenario_key,
        "scenario_name": scenario_name,
        "retrieved_count": retrieved_count,
        "unique_count": len(unique_records),
        "verified_live_count": verified_live_count,
        "expired_count": expired_count,
        "duplicates_removed_count": duplicates_removed_count,
        "missing_application_urls_count": missing_app_urls,
        "missing_source_urls_count": missing_src_urls,
        "sources_queried": sources_queried,
        "sources_failed": sources_failed,
        "records": unique_records[:10] # Top 10 records for scenario report
    }

async def execute_all_scenarios(db: Session) -> Dict[str, Any]:
    """Execute all 5 scenarios and compile aggregate testing report data."""
    results = {}
    for key in ["Test A", "Test B", "Test C", "Test D", "Test E"]:
        res = await execute_scenario(key, db)
        results[key] = res
    return results
