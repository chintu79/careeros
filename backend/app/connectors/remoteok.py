import logging
import httpx
from datetime import datetime
from bs4 import BeautifulSoup
from typing import List, Dict, Any

from backend.app.connectors.base import BaseConnector
from backend.app.pipeline.internship_filter import is_valid_internship

logger = logging.getLogger(__name__)

class RemoteOKConnector(BaseConnector):
    def __init__(self):
        super().__init__(name="Remote OK", source_type="api")

    async def fetch_jobs(self, **kwargs) -> List[Dict[str, Any]]:
        url = "https://remoteok.com/api"
        results = []
        headers = {
            "User-Agent": "CareerOS-Interniq-Discovery/1.0"
        }
        try:
            async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    postings = [p for p in data if isinstance(p, dict) and p.get("id")]
                    for p in postings:
                        title = p.get("position", "")
                        comp_name = p.get("company", "Remote Employer")
                        raw_desc = p.get("description", "")
                        soup = BeautifulSoup(raw_desc, "lxml")
                        clean_desc = soup.get_text(separator="\n").strip()
                        app_url = p.get("url") or f"https://remoteok.com/remote-jobs/{p.get('id')}"

                        # Strict filter (rejects "internal", "international", "internet"!)
                        valid, reason = is_valid_internship(
                            title=title,
                            description=clean_desc,
                            company_name=comp_name,
                            url=app_url
                        )
                        if not valid:
                            continue

                        location = p.get("location") or "Worldwide Remote"
                        pub_epoch = p.get("epoch")
                        posted_dt = None
                        if pub_epoch:
                            try:
                                posted_dt = datetime.utcfromtimestamp(pub_epoch)
                            except Exception:
                                pass
                                
                        salary = ""
                        if p.get("salary_min") and p.get("salary_max"):
                            salary = f"${p.get('salary_min')} - ${p.get('salary_max')} / year"
                        elif p.get("salary"):
                            salary = str(p.get("salary"))
                        else:
                            salary = "Stipend Undisclosed"
                            
                        results.append({
                            "title": title,
                            "company_name": comp_name,
                            "company_website": "https://remoteok.com",
                            "location": f"Remote, {location}",
                            "workplace_type": "remote",
                            "internship_type": "remote",
                            "work_mode": "full-time",
                            "employment_type": "internship",
                            "description": clean_desc or title,
                            "stipend_text": salary,
                            "duration_months": 6,
                            "duration": "6 months",
                            "original_url": app_url,
                            "application_url": app_url,
                            "source_url": url,
                            "source_name": "Remote OK",
                            "external_id": f"remoteok_{p.get('id')}",
                            "source_platform": "remoteok",
                            "posted_at": posted_dt or datetime.utcnow()
                        })
                else:
                    logger.warning(f"RemoteOK API returned status {resp.status_code}")
        except Exception as e:
            logger.error(f"RemoteOK fetch failed: {e}")
            
        return results
