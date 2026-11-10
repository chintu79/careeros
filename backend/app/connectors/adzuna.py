import logging
import httpx
from datetime import datetime
from typing import List, Dict, Any, Optional

from backend.app.connectors.base import BaseConnector
from backend.app.pipeline.internship_filter import is_valid_internship
from backend.app.config import settings

logger = logging.getLogger(__name__)

class AdzunaConnector(BaseConnector):
    def __init__(self, app_id: Optional[str] = None, app_key: Optional[str] = None):
        super().__init__(name="Adzuna", source_type="api")
        self.app_id = app_id if app_id is not None else settings.ADZUNA_APP_ID
        self.app_key = app_key if app_key is not None else settings.ADZUNA_APP_KEY

    async def fetch_jobs(self, **kwargs) -> List[Dict[str, Any]]:
        app_id = kwargs.get("app_id", self.app_id)
        app_key = kwargs.get("app_key", self.app_key)
        
        if not app_id or not app_key:
            logger.info("Adzuna API credentials (ADZUNA_APP_ID, ADZUNA_APP_KEY) not configured in environment. Returning 0 results.")
            return []
            
        url = f"https://api.adzuna.com/v1/api/jobs/in/search/1?app_id={app_id}&app_key={app_key}&results_per_page=20&what=internship"
        results = []
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    jobs = data.get("results", [])
                    for j in jobs:
                        title = j.get("title", "")
                        comp_name = j.get("company", {}).get("display_name", "Technology Employer")
                        loc_name = j.get("location", {}).get("display_name", "India")
                        desc = j.get("description", "")
                        app_url = j.get("redirect_url", "")

                        valid, reason = is_valid_internship(
                            title=title,
                            description=desc,
                            company_name=comp_name,
                            url=app_url
                        )
                        if not valid:
                            continue

                        created = j.get("created")
                        posted_dt = None
                        if created:
                            try:
                                posted_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                            except Exception:
                                pass
                                
                        sal_min = j.get("salary_min")
                        sal_max = j.get("salary_max")
                        sal_text = f"₹{sal_min} - ₹{sal_max} / year" if sal_min and sal_max else "Stipend Undisclosed"
                        wp_type = "remote" if "remote" in loc_name.lower() else "onsite"

                        results.append({
                            "title": title,
                            "company_name": comp_name,
                            "company_website": "https://adzuna.in",
                            "location": loc_name,
                            "workplace_type": wp_type,
                            "internship_type": "remote" if wp_type == "remote" else "in-office",
                            "work_mode": "full-time",
                            "employment_type": "internship",
                            "description": desc,
                            "stipend_text": sal_text,
                            "duration_months": 6,
                            "duration": "6 months",
                            "original_url": app_url,
                            "application_url": app_url,
                            "source_url": url,
                            "source_name": "Adzuna",
                            "external_id": f"adzuna_{j.get('id')}",
                            "source_platform": "adzuna",
                            "posted_at": posted_dt or datetime.utcnow()
                        })
                else:
                    logger.warning(f"Adzuna returned status {resp.status_code}")
        except Exception as e:
            logger.error(f"Adzuna fetch failed: {e}")
            
        return results
