import logging
import httpx
from datetime import datetime
from bs4 import BeautifulSoup
from typing import List, Dict, Any

from backend.app.connectors.base import BaseConnector
from backend.app.pipeline.internship_filter import is_valid_internship

logger = logging.getLogger(__name__)

class RemotiveConnector(BaseConnector):
    def __init__(self):
        super().__init__(name="Remotive", source_type="api")

    async def fetch_jobs(self, **kwargs) -> List[Dict[str, Any]]:
        url = "https://remotive.com/api/remote-jobs?search=intern"
        results = []
        headers = {
            "User-Agent": "CareerOS-Discovery/1.0"
        }
        try:
            async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    jobs = data.get("jobs", [])
                    for j in jobs:
                        title = j.get("title", "")
                        candidate_loc = j.get("candidate_required_location", "Worldwide")
                        raw_desc = j.get("description", "")
                        soup = BeautifulSoup(raw_desc, "lxml")
                        clean_desc = soup.get_text(separator="\n").strip()
                        app_url = j.get("url", "")
                        comp_name = j.get("company_name", "Remote Employer")

                        # Strict filter
                        valid, reason = is_valid_internship(
                            title=title,
                            description=clean_desc,
                            company_name=comp_name,
                            url=app_url
                        )
                        if not valid:
                            continue

                        pub_date = j.get("publication_date")
                        posted_dt = None
                        if pub_date:
                            try:
                                posted_dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                            except Exception:
                                pass
                                
                        salary = j.get("salary") or "Stipend Undisclosed"

                        results.append({
                            "title": title,
                            "company_name": comp_name,
                            "company_website": "https://remotive.com",
                            "location": f"Remote ({candidate_loc})",
                            "workplace_type": "remote",
                            "internship_type": "remote",
                            "work_mode": "full-time",
                            "employment_type": "internship",
                            "description": clean_desc,
                            "stipend_text": salary,
                            "duration_months": 6,
                            "duration": "6 months",
                            "original_url": app_url,
                            "application_url": app_url,
                            "source_url": url,
                            "source_name": "Remotive",
                            "external_id": f"remotive_{j.get('id')}",
                            "source_platform": "remotive",
                            "posted_at": posted_dt or datetime.utcnow()
                        })
                else:
                    logger.warning(f"Remotive API returned status {resp.status_code}")
        except Exception as e:
            logger.error(f"Remotive fetch failed: {e}")
            
        return results
