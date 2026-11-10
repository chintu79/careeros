import logging
import httpx
from datetime import datetime
from typing import List, Dict, Any
from backend.app.connectors.base import BaseConnector
from backend.app.pipeline.internship_filter import is_valid_internship

logger = logging.getLogger(__name__)

class SmartRecruitersConnector(BaseConnector):
    def __init__(self, company_identifier: str = "visa", company_name: str = "Visa"):
        super().__init__(name="SmartRecruiters", source_type="ats")
        self.company_identifier = company_identifier
        self.company_name = company_name

    async def fetch_jobs(self, **kwargs) -> List[Dict[str, Any]]:
        comp_id = kwargs.get("company_identifier", self.company_identifier)
        company = kwargs.get("company_name", self.company_name)
        url = f"https://api.smartrecruiters.com/v1/companies/{comp_id}/postings"
        
        results = []
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    postings = data.get("content", [])
                    for p in postings:
                        title = p.get("name", "")
                        loc_obj = p.get("location", {})
                        city = loc_obj.get("city", "")
                        country = loc_obj.get("country", "")
                        location = f"{city}, {country}".strip(", ") or "Remote"
                        workplace = "remote" if loc_obj.get("remote") else "onsite"
                        app_url = f"https://jobs.smartrecruiters.com/{comp_id}/{p.get('id')}"

                        # Strict validation
                        valid, reason = is_valid_internship(
                            title=title,
                            description=f"Role at {company}: {title}. Location: {location}.",
                            company_name=company,
                            url=app_url
                        )
                        if not valid:
                            continue
                        
                        rel_date = p.get("releasedDate")
                        posted_dt = None
                        if rel_date:
                            try:
                                posted_dt = datetime.fromisoformat(rel_date.replace("Z", "+00:00"))
                            except Exception:
                                pass
                                
                        results.append({
                            "title": title,
                            "company_name": company,
                            "company_website": f"https://jobs.smartrecruiters.com/{comp_id}",
                            "location": location,
                            "workplace_type": workplace,
                            "internship_type": "remote" if workplace == "remote" else "in-office",
                            "work_mode": "full-time",
                            "employment_type": "internship",
                            "description": f"Role at {company}: {title}. Location: {location}.",
                            "stipend_text": "Stipend Undisclosed",
                            "duration_months": None,
                            "original_url": app_url,
                            "application_url": app_url,
                            "source_url": url,
                            "source_name": f"SmartRecruiters - {company}",
                            "external_id": f"sr_{p.get('id')}",
                            "source_platform": "smartrecruiters",
                            "posted_at": posted_dt or datetime.utcnow()
                        })
                else:
                    logger.warning(f"SmartRecruiters returned status {resp.status_code} for {comp_id}")
        except Exception as e:
            logger.error(f"SmartRecruiters fetch failed for {comp_id}: {e}")
            
        return results
