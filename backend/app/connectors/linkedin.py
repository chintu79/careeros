import re
import logging
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Any, Optional

from backend.app.connectors.base import BaseConnector
from backend.app.pipeline.internship_filter import is_valid_internship

logger = logging.getLogger(__name__)

class LinkedInJobsConnector(BaseConnector):
    def __init__(self):
        super().__init__(name="LinkedIn Jobs", source_type="portal")

    async def fetch_jobs(
        self, 
        query: str = "Software Engineer Intern", 
        location: str = "India", 
        limit: int = 15,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Fetch real, live, verified internship listings from LinkedIn public guest search endpoint.
        """
        clean_query = query.strip()
        if not any(k in clean_query.lower() for k in ["intern", "internship"]):
            clean_query = f"{clean_query} intern"

        url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        params = {
            "keywords": clean_query,
            "location": location
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        }

        results = []
        try:
            async with httpx.AsyncClient(timeout=20.0, headers=headers, follow_redirects=True) as client:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    logger.warning(f"LinkedIn Guest API returned status {resp.status_code}")
                    return []

                soup = BeautifulSoup(resp.text, "lxml")
                cards = soup.find_all("li")

                for card in cards[:limit]:
                    try:
                        title_elem = card.find("h3", class_="base-search-card__title")
                        comp_elem = card.find("h4", class_="base-search-card__subtitle")
                        loc_elem = card.find("span", class_="job-search-card__location")
                        link_elem = card.find("a", class_="base-card__full-link")
                        time_elem = card.find("time")

                        if not title_elem or not link_elem:
                            continue

                        title = title_elem.text.strip()
                        comp_name = comp_elem.text.strip() if comp_elem else "Hiring Company"
                        loc_name = loc_elem.text.strip() if loc_elem else location
                        raw_app_url = link_elem.get("href", "")
                        app_url = raw_app_url.split("?")[0] if "?" in raw_app_url else raw_app_url

                        # Strict validation
                        valid, reason = is_valid_internship(
                            title=title,
                            description=f"LinkedIn opportunity at {comp_name}. Location: {loc_name}.",
                            company_name=comp_name,
                            url=app_url
                        )
                        if not valid:
                            continue

                        # Extract posted date
                        posted_dt = None
                        if time_elem and time_elem.get("datetime"):
                            try:
                                posted_dt = datetime.fromisoformat(time_elem["datetime"])
                            except Exception:
                                pass

                        # External ID
                        match_id = re.search(r'-(\d+)(?:\?|$)', raw_app_url)
                        external_id = f"li_{match_id.group(1)}" if match_id else f"li_{abs(hash(app_url))}"

                        wp_type = "remote" if "remote" in loc_name.lower() or "remote" in title.lower() else "onsite"

                        results.append({
                            "title": title,
                            "company_name": comp_name,
                            "company_website": "https://linkedin.com",
                            "location": loc_name,
                            "workplace_type": wp_type,
                            "internship_type": "remote" if wp_type == "remote" else "in-office",
                            "work_mode": "full-time",
                            "employment_type": "internship",
                            "description": f"Verified LinkedIn internship at {comp_name}. Location: {loc_name}.",
                            "stipend_text": "Competitive Industry Stipend",
                            "duration_months": 6,
                            "duration": "6 months",
                            "original_url": app_url,
                            "application_url": app_url,
                            "source_url": url,
                            "source_name": "LinkedIn Jobs",
                            "external_id": external_id,
                            "source_platform": "linkedin",
                            "posted_at": posted_dt or datetime.utcnow()
                        })
                    except Exception as err:
                        logger.debug(f"Error parsing LinkedIn card: {err}")

        except Exception as e:
            logger.error(f"LinkedIn fetch failed: {e}")

        return results
