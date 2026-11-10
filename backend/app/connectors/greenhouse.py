import logging
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Any, Optional

from backend.app.connectors.base import BaseConnector
from backend.app.pipeline.internship_filter import is_valid_internship

logger = logging.getLogger(__name__)

DEFAULT_GREENHOUSE_BOARDS = [
    {"board_id": "databricks", "company_name": "Databricks", "website": "https://databricks.com"},
    {"board_id": "stripe", "company_name": "Stripe", "website": "https://stripe.com"},
    {"board_id": "figma", "company_name": "Figma", "website": "https://figma.com"},
    {"board_id": "cloudflare", "company_name": "Cloudflare", "website": "https://cloudflare.com"}
]

class GreenhouseConnector(BaseConnector):
    def __init__(self, board_id: str = "databricks", company_name: str = "Databricks", website: str = ""):
        super().__init__(name="Greenhouse", source_type="ats")
        self.board_id = board_id
        self.company_name = company_name
        self.website = website or f"https://boards.greenhouse.io/{board_id}"

    async def fetch_jobs(self, **kwargs) -> List[Dict[str, Any]]:
        boards = kwargs.get("boards")
        if not boards:
            board = kwargs.get("board_id", self.board_id)
            comp = kwargs.get("company_name", self.company_name)
            boards = [{"board_id": board, "company_name": comp, "website": self.website}]

        results = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
            for b in boards:
                board_id = b["board_id"]
                comp_name = b["company_name"]
                comp_web = b.get("website", f"https://boards.greenhouse.io/{board_id}")
                url = f"https://boards-api.greenhouse.io/v1/boards/{board_id}/jobs?content=true"

                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        data = resp.json()
                        jobs = data.get("jobs", [])
                        for j in jobs:
                            title = j.get("title", "")
                            raw_content = j.get("content", "")
                            soup = BeautifulSoup(raw_content, "lxml")
                            desc = soup.get_text(separator="\n").strip()
                            app_url = j.get("absolute_url") or f"https://boards.greenhouse.io/{board_id}/jobs/{j.get('id')}"

                            # Strict internship filter
                            valid, reason = is_valid_internship(
                                title=title,
                                description=desc,
                                company_name=comp_name,
                                url=app_url
                            )
                            if not valid:
                                continue

                            location_name = j.get("location", {}).get("name", "Remote")
                            workplace = "remote" if "remote" in location_name.lower() else ("hybrid" if "hybrid" in location_name.lower() else "onsite")

                            updated_at = j.get("updated_at")
                            posted_dt = None
                            if updated_at:
                                try:
                                    posted_dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                                except Exception:
                                    pass

                            results.append({
                                "title": title,
                                "company_name": comp_name,
                                "company_website": comp_web,
                                "location": location_name,
                                "workplace_type": workplace,
                                "internship_type": "remote" if workplace == "remote" else ("hybrid" if workplace == "hybrid" else "in-office"),
                                "work_mode": "full-time",
                                "employment_type": "internship",
                                "description": desc or title,
                                "stipend_text": "Stipend Undisclosed",
                                "duration_months": 6,
                                "duration": "3-6 months",
                                "original_url": app_url,
                                "application_url": app_url,
                                "source_url": url,
                                "source_name": f"Greenhouse - {comp_name}",
                                "external_id": f"gh_{j.get('id')}",
                                "source_platform": "greenhouse",
                                "posted_at": posted_dt or datetime.utcnow()
                            })
                    else:
                        logger.warning(f"Greenhouse board {board_id} returned status {resp.status_code}")
                except Exception as e:
                    logger.error(f"Greenhouse fetch failed for {board_id}: {e}")

        return results
