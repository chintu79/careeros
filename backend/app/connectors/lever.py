import logging
import httpx
from datetime import datetime
from typing import List, Dict, Any, Optional

from backend.app.connectors.base import BaseConnector
from backend.app.pipeline.internship_filter import is_valid_internship

logger = logging.getLogger(__name__)

DEFAULT_LEVER_SITES = [
    {"site": "palantir", "company_name": "Palantir", "website": "https://palantir.com"}
]

class LeverConnector(BaseConnector):
    def __init__(self, site: str = "palantir", company_name: str = "Palantir", website: str = ""):
        super().__init__(name="Lever", source_type="ats")
        self.site = site
        self.company_name = company_name
        self.website = website or f"https://jobs.lever.co/{site}"

    async def fetch_jobs(self, **kwargs) -> List[Dict[str, Any]]:
        sites = kwargs.get("sites")
        if not sites:
            s = kwargs.get("site", self.site)
            comp = kwargs.get("company_name", self.company_name)
            sites = [{"site": s, "company_name": comp, "website": self.website}]

        results = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
            for item in sites:
                site = item["site"]
                comp_name = item["company_name"]
                comp_web = item.get("website", f"https://jobs.lever.co/{site}")
                url = f"https://api.lever.co/v0/postings/{site}?mode=json"

                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        postings = resp.json()
                        for p in postings:
                            title = p.get("text", "")
                            cats = p.get("categories", {})
                            location = cats.get("location", "Remote")
                            desc = p.get("descriptionPlain") or p.get("description", "")
                            app_url = p.get("hostedUrl") or p.get("applyUrl", "")

                            valid, reason = is_valid_internship(
                                title=title,
                                description=desc,
                                company_name=comp_name,
                                url=app_url
                            )
                            if not valid:
                                continue

                            workplace = "remote" if "remote" in location.lower() or cats.get("workplaceType") == "remote" else "onsite"
                            created_at = p.get("createdAt")
                            posted_dt = None
                            if created_at:
                                try:
                                    posted_dt = datetime.utcfromtimestamp(created_at / 1000)
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
                                "source_name": f"Lever - {comp_name}",
                                "external_id": f"lever_{p.get('id')}",
                                "source_platform": "lever",
                                "posted_at": posted_dt or datetime.utcnow()
                            })
                    else:
                        logger.warning(f"Lever site {site} returned status {resp.status_code}")
                except Exception as e:
                    logger.error(f"Lever fetch failed for {site}: {e}")

        return results
