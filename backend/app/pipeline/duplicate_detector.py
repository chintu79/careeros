import urllib.parse
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List
from sqlalchemy.orm import Session
from backend.app.models.opportunity import Opportunity

TRACKING_QUERY_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "gh_src", "lever-origin", "source", "fbclid", "gclid",
    "referral", "tracking_id", "trk", "campaign", "s", "mkt_tok"
}

def normalize_canonical_url(url: str) -> str:
    """
    Normalizes a job or application URL into a canonical format:
    1. Removes all tracking / referral query parameters (utm_*, gh_src, lever-origin, etc.).
    2. Strips trailing slashes.
    3. Normalizes scheme to https.
    4. Removes 'www.' prefix from hostname.
    5. Strips URL fragments (#...).
    """
    if not url or not url.strip():
        return ""
    
    url = url.strip()
    if url.startswith("urn:"):
        return url
        
    try:
        parsed = urllib.parse.urlsplit(url)
        if not parsed.netloc:
            return url.rstrip("/")
            
        scheme = "https" if parsed.scheme in ["http", "https"] else (parsed.scheme or "https")
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        if ":" in netloc:
            host, port = netloc.split(":", 1)
            if (scheme == "https" and port == "443") or (scheme == "http" and port == "80"):
                netloc = host

        query_params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
        clean_params = [
            (k, v) for k, v in query_params 
            if k.lower() not in TRACKING_QUERY_PARAMS and not k.lower().startswith("utm_")
        ]
        clean_params.sort(key=lambda x: x[0])
        clean_query = urllib.parse.urlencode(clean_params)
        
        path = parsed.path.rstrip("/")
        
        return urllib.parse.urlunsplit((scheme, netloc, path, clean_query, ""))
    except Exception:
        return url.rstrip("/")

def find_duplicate_opportunity(
    db: Session, 
    job_data: Dict[str, Any]
) -> Tuple[bool, Optional[Opportunity]]:
    """
    Stage 3 Multi-Tier Duplicate Detection:
    - Tier 1: Check external_id + source_platform
    - Tier 2: Check normalized canonical application_url or original_url
    - Tier 3: Check company_name + normalized_title + location (fuzzy match)
    """
    # Tier 1: External ID + Source Platform
    ext_id = job_data.get("external_id")
    platform = job_data.get("source_platform")
    if ext_id and platform:
        existing = db.query(Opportunity).filter(
            Opportunity.external_id == str(ext_id),
            Opportunity.source_platform == platform
        ).first()
        if existing:
            return True, existing

    # Tier 2: Canonical URL Match
    new_url = job_data.get("application_url") or job_data.get("original_url")
    if new_url:
        canon_new = normalize_canonical_url(new_url)
        if canon_new and not canon_new.startswith("urn:"):
            # Check exact original_url
            existing = db.query(Opportunity).filter(
                Opportunity.original_url == new_url
            ).first()
            if existing:
                return True, existing

            # Scan recent opportunities for matching canonical application_url or original_url
            candidates = db.query(Opportunity).order_by(Opportunity.id.desc()).limit(300).all()
            for cand in candidates:
                cand_canon_app = normalize_canonical_url(cand.application_url or "")
                cand_canon_orig = normalize_canonical_url(cand.original_url or "")
                if canon_new in (cand_canon_app, cand_canon_orig):
                    return True, cand
            
    # Tier 3: High-confidence Title + Company + Location match
    company_name = job_data.get("company_name", "").strip().lower()
    norm_title = job_data.get("normalized_title", "").strip().lower()
    norm_loc = (job_data.get("normalized_location") or job_data.get("location") or "").strip().lower()
    
    if company_name and norm_title:
        candidates = db.query(Opportunity).filter(
            Opportunity.company_name.ilike(company_name)
        ).all()
        for cand in candidates:
            if cand.normalized_title.lower() == norm_title:
                # Compare locations if both present
                cand_loc = (cand.normalized_location or cand.location or "").lower()
                if not norm_loc or not cand_loc or "remote" in norm_loc or "remote" in cand_loc or norm_loc == cand_loc:
                    return True, cand
                
    return False, None

def merge_duplicate_opportunity(
    existing: Opportunity, 
    new_data: Dict[str, Any]
) -> Opportunity:
    """
    Merge newly discovered duplicate source info into the existing opportunity record.
    Never deletes or overwrites existing source history.
    Preserves best application URL and enriches missing fields.
    """
    existing_links = list(existing.source_links or [])
    new_source = new_data.get("source_platform", "unknown")
    new_url = new_data.get("original_url", "")
    
    # Check if this exact source URL is already tracked
    already_tracked = any(link.get("url") == new_url for link in existing_links)
    if not already_tracked and new_url:
        existing_links.append({
            "source": new_source,
            "url": new_url,
            "discovered_at": datetime.utcnow().isoformat()
        })
        existing.source_links = existing_links
        
    # Update last verified and fetched timestamps
    existing.last_verified_at = datetime.utcnow()
    existing.last_fetched_at = datetime.utcnow()
    
    modified_content = False

    # Lifecycle: if it was stale or unverified, seeing it again promotes it to verified
    if existing.status in ["stale", "unverified"]:
        existing.status = "verified"
        modified_content = True
    
    # Better direct application URL: if new source is direct ATS and existing was aggregator, upgrade application_url
    new_app_url = new_data.get("application_url")
    if new_app_url and any(ats in new_app_url.lower() for ats in ["greenhouse.io", "lever.co", "ashbyhq.com", "smartrecruiters.com"]):
        existing.application_url = new_app_url
        
    if not existing.internship_category and new_data.get("internship_category"):
        existing.internship_category = new_data.get("internship_category")
        modified_content = True
        
    # Enrich missing description, deadline, or compensation
    if (not existing.description or len(existing.description) < 100) and new_data.get("description"):
        existing.description = new_data.get("description")
        modified_content = True
        
    if not existing.deadline_at and new_data.get("deadline_at"):
        existing.deadline_at = new_data.get("deadline_at")
        modified_content = True
        
    if (not existing.stipend_text or "Unspecified" in existing.stipend_text or "Undisclosed" in existing.stipend_text) and new_data.get("stipend_text"):
        if new_data.get("min_stipend") is not None:
            existing.stipend_text = new_data.get("stipend_text")
            existing.min_stipend = new_data.get("min_stipend")
            existing.max_stipend = new_data.get("max_stipend")
            existing.compensation_type = new_data.get("compensation_type", existing.compensation_type)
            modified_content = True

    if modified_content:
        existing.content_version = (existing.content_version or 1) + 1
        
    return existing
