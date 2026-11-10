import re
import logging
import asyncio
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Any, Optional

from backend.app.connectors.base import BaseConnector
from backend.app.pipeline.internship_filter import is_valid_internship

logger = logging.getLogger(__name__)

CATEGORY_SLUG_MAP = {
    "ai": "artificial-intelligence-ai-internship",
    "ml": "machine-learning-internship",
    "ai/ml": "artificial-intelligence-ai-internship",
    "data science": "data-science-internship",
    "full stack": "full-stack-development-internship",
    "full-stack": "full-stack-development-internship",
    "software": "computer-science-internship",
    "python": "python-django-internship",
    "web": "web-development-internship"
}

class InternshalaConnector(BaseConnector):
    def __init__(self):
        super().__init__(name="Internshala", source_type="portal", health_status="operational")

    async def fetch_jobs(
        self, 
        query: str = "computer-science", 
        location: str = "", 
        limit: int = 20,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Fetch real, live, verified internship listings from Internshala public listings.
        Supports multi-page pagination (page=1..N).
        """
        # Determine URL
        q_lower = query.lower()
        slug = "computer-science-internship"
        for key, s in CATEGORY_SLUG_MAP.items():
            if key in q_lower:
                slug = s
                break

        # Check if remote or specific city
        loc_slug = ""
        if "remote" in location.lower() or "work from home" in q_lower:
            loc_slug = "work-from-home-"
        elif location.strip():
            city_clean = re.sub(r'[^a-zA-Z0-9]', '-', location.strip().lower()).strip('-')
            loc_slug = f"-in-{city_clean}"

        if loc_slug.startswith("work-from-home"):
            base_url = f"https://internshala.com/internships/{loc_slug}{slug}"
        elif loc_slug.startswith("-in-"):
            base_url = f"https://internshala.com/internships/{slug}{loc_slug}"
        else:
            base_url = f"https://internshala.com/internships/{slug}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        }

        max_pages = kwargs.get("max_pages", 1)
        if limit > 20 and max_pages == 1:
            max_pages = min(3, (limit + 19) // 20)

        results = []
        try:
            async with httpx.AsyncClient(timeout=20.0, headers=headers, follow_redirects=True) as client:
                for page in range(1, max_pages + 1):
                    page_url = f"{base_url}/page-{page}" if page > 1 else base_url
                    resp = await client.get(page_url)
                    if resp.status_code != 200:
                        logger.warning(f"Internshala returned status {resp.status_code} for {page_url}")
                        break

                    soup = BeautifulSoup(resp.text, "lxml")
                    cards = soup.find_all("div", class_="individual_internship")
                    if not cards:
                        cards = soup.find_all("div", attrs={"internship_id": True})

                    for card in cards:
                        if len(results) >= limit:
                            break
                        try:
                            # Extract title and application link
                            link_tag = card.find("a", class_="job-title-href") or card.find("a", href=True)
                            if not link_tag:
                                continue
                            
                            raw_title = link_tag.text.strip()
                            href = link_tag.get("href", "")
                            app_url = f"https://internshala.com{href}" if href.startswith("/") else href

                            # Ensure title contains role or add category
                            clean_title = raw_title
                            if not any(k in clean_title.lower() for k in ["intern", "internship"]):
                                clean_title = f"{raw_title} Intern"

                            # Extract company name
                            company_elem = card.find("p", class_="company-name") or card.find("div", class_="company_name")
                            company_name = company_elem.text.strip() if company_elem else "Hiring Company"

                            # Extract location
                            loc_elem = card.find("div", class_="row-1-item locations") or card.find("a", class_="location_link")
                            loc_text = loc_elem.text.strip() if loc_elem else ("Remote, India" if "work from home" in card.text.lower() else "India")

                            # Extract stipend
                            stipend_elem = card.find("span", class_="stipend")
                            stipend_text = stipend_elem.text.strip() if stipend_elem else "Stipend Undisclosed"

                            # Extract duration
                            duration_text = ""
                            for item in card.find_all("div", class_="row-1-item"):
                                txt = item.text.strip()
                                if "month" in txt.lower() or "week" in txt.lower():
                                    duration_text = txt
                                    break

                            # Strict validation
                            valid, reason = is_valid_internship(
                                title=clean_title,
                                description=f"Internship at {company_name}. Location: {loc_text}. Stipend: {stipend_text}",
                                company_name=company_name,
                                url=app_url
                            )
                            if not valid:
                                continue

                            wp_type = "remote" if "work from home" in loc_text.lower() or "remote" in loc_text.lower() else "onsite"
                            dur_months = 6
                            dur_match = re.search(r'(\d+)\s*month', duration_text, re.IGNORECASE)
                            if dur_match:
                                dur_months = int(dur_match.group(1))

                            internship_id = card.get("internship_id") or card.get("id") or href.split("-")[-1]

                            results.append({
                                "title": clean_title,
                                "company_name": company_name,
                                "company_website": "https://internshala.com",
                                "location": loc_text,
                                "workplace_type": wp_type,
                                "internship_type": "remote" if wp_type == "remote" else "in-office",
                                "work_mode": "full-time",
                                "employment_type": "internship",
                                "description": f"Verified live internship at {company_name}. Location: {loc_text}. Stipend: {stipend_text}. Duration: {duration_text or 'Flexible'}.",
                                "stipend_text": stipend_text,
                                "duration_months": dur_months,
                                "duration": duration_text or f"{dur_months} months",
                                "original_url": app_url,
                                "application_url": app_url,
                                "source_url": str(resp.url),
                                "source_name": "Internshala",
                                "external_id": f"ish_{internship_id}",
                                "source_platform": "internshala",
                                "posted_at": datetime.utcnow()
                            })
                        except Exception as err:
                            logger.debug(f"Error parsing Internshala card: {err}")

                    if len(results) >= limit:
                        break
                    await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Internshala fetch failed for {base_url}: {e}")

        return results
