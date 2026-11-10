import logging
import httpx
from datetime import datetime
from typing import List, Dict, Any, Optional

from backend.app.connectors.base import BaseConnector
from backend.app.pipeline.internship_filter import is_valid_internship

logger = logging.getLogger(__name__)

DEFAULT_ASHBY_ORGS = [
    {"organization": "ramp", "company_name": "Ramp", "website": "https://ramp.com"},
    {"organization": "openai", "company_name": "OpenAI", "website": "https://openai.com"}
]

class AshbyConnector(BaseConnector):
    def __init__(self, organization: str = "ramp", company_name: str = "Ramp", website: str = ""):
        super().__init__(name="Ashby", source_type="ats")
        self.organization = organization
        self.company_name = company_name
        self.website = website or f"https://jobs.ashbyhq.com/{organization}"

    async def fetch_jobs(self, **kwargs) -> List[Dict[str, Any]]:
        orgs = kwargs.get("orgs")
        if not orgs:
            org = kwargs.get("organization", self.organization)
            comp = kwargs.get("company_name", self.company_name)
            orgs = [{"organization": org, "company_name": comp, "website": self.website}]

        results = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
            for o in orgs:
                org_id = o["organization"]
                comp_name = o["company_name"]
                comp_web = o.get("website", f"https://jobs.ashbyhq.com/{org_id}")
                url = f"https://api.ashbyhq.com/posting-api/job-board/{org_id}"

                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        data = resp.json()
                        jobs = data.get("jobs", [])
                        for j in jobs:
                            title = j.get("title", "")
                            location = j.get("locationName") or "Remote"
                            desc = j.get("descriptionPlain") or j.get("descriptionHtml", "")
                            app_url = j.get("jobUrl") or f"https://jobs.ashbyhq.com/{org_id}/{j.get('id')}"

                            valid, reason = is_valid_internship(
                                title=title,
                                description=desc,
                                company_name=comp_name,
                                url=app_url
                            )
                            if not valid:
                                continue

                            workplace = "remote" if j.get("isRemote") or "remote" in location.lower() else "onsite"
                            pub_at = j.get("publishedAt")
                            posted_dt = None
                            if pub_at:
                                try:
                                    posted_dt = datetime.fromisoformat(pub_at.replace("Z", "+00:00"))
                                except Exception:
                                    pass

                            results.append({
                                "title": title,
                                "company_name": comp_name,
                                "company_website": comp_web,
                                "location": location,
                                "workplace_type": workplace,
                                "internship_type": "remote" if workplace == "remote" else "in-office",
                                "work_mode": "full-time",
                                "employment_type": "internship",
                                "description": desc or title,
                                "stipend_text": "Stipend Undisclosed",
                                "duration_months": 6,
                                "duration": "3-6 months",
                                "original_url": app_url,
                                "application_url": app_url,
                                "source_url": url,
                                "source_name": f"Ashby - {comp_name}",
                                "external_id": f"ashby_{j.get('id')}",
                                "source_platform": "ashby",
                                "posted_at": posted_dt or datetime.utcnow()
                            })
                    else:
                        logger.warning(f"Ashby org {org_id} returned status {resp.status_code}")
                except Exception as e:
                    logger.error(f"Ashby fetch failed for {org_id}: {e}")

        return results
