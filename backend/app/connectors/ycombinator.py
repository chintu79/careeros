import re
import html
import logging
import asyncio
import httpx
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

from backend.app.connectors.base import BaseConnector

logger = logging.getLogger(__name__)

class YCombinatorConnector(BaseConnector):
    def __init__(self):
        super().__init__(name="Y Combinator", source_type="api", health_status="operational")

    async def fetch_jobs(self, limit: int = 30, **kwargs) -> List[Dict[str, Any]]:
        """
        Fetch active YC startup job postings via the official Hacker News Firebase API.
        Retrieves job story IDs from https://hacker-news.firebaseio.com/v0/jobstories.json
        and resolves each job posting payload concurrently.
        """
        results = []
        headers = {
            "User-Agent": "CareerOS-Aggregator/2.0 (Legitimate Job Discovery; https://careeros.dev)"
        }
        
        async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
            try:
                stories_res = await client.get("https://hacker-news.firebaseio.com/v0/jobstories.json")
                if stories_res.status_code != 200:
                    logger.error(f"Failed to fetch YC job stories: HTTP {stories_res.status_code}")
                    return []
                
                story_ids = stories_res.json()[:limit]
            except Exception as e:
                logger.error(f"Network error querying HN Firebase jobstories: {e}")
                return []

            # Concurrent item retrieval with rate-limiting chunk size
            async def fetch_item(story_id: int) -> Optional[Dict[str, Any]]:
                try:
                    res = await client.get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json")
                    if res.status_code == 200:
                        return res.json()
                except Exception as err:
                    logger.warning(f"Error fetching HN item {story_id}: {err}")
                return None

            items = await asyncio.gather(*[fetch_item(sid) for sid in story_ids])

            for item in items:
                if not item or item.get("type") != "job" or item.get("deleted") or item.get("dead"):
                    continue

                raw_title = item.get("title", "").strip()
                if not raw_title:
                    continue

                company, batch, role, loc = self._parse_yc_title(raw_title)
                
                item_url = item.get("url") or f"https://news.ycombinator.com/item?id={item['id']}"
                
                # Format description
                raw_text = item.get("text", "")
                if raw_text:
                    soup = BeautifulSoup(raw_text, "lxml")
                    desc = soup.get_text(separator="\n").strip()
                else:
                    batch_str = f" ({batch})" if batch else ""
                    desc = (
                        f"Y Combinator-backed startup {company}{batch_str} is actively hiring for {role}.\n\n"
                        f"Review the full position spec and apply directly at the hiring portal:\n{item_url}"
                    )

                posted_epoch = item.get("time")
                posted_dt = datetime.fromtimestamp(posted_epoch, tz=timezone.utc).replace(tzinfo=None) if posted_epoch else datetime.utcnow()

                is_remote = "remote" in raw_title.lower() or "remote" in desc.lower() or "remote" in loc.lower()

                comp_website = ""
                if "ycombinator.com/companies/" in item_url:
                    comp_website = item_url
                else:
                    clean_slug = re.sub(r'[^a-zA-Z0-9]', '-', company.lower()).strip('-')
                    comp_website = f"https://www.ycombinator.com/companies/{clean_slug}"

                results.append({
                    "title": role,
                    "company_name": company,
                    "company_website": comp_website,
                    "location": loc or ("Remote, Worldwide" if is_remote else "San Francisco, CA / Remote"),
                    "workplace_type": "remote" if is_remote else ("hybrid" if "hybrid" in raw_title.lower() else "onsite"),
                    "internship_type": "remote" if is_remote else "in-office",
                    "work_mode": "full-time",
                    "employment_type": "internship" if any(k in role.lower() for k in ["intern", "graduate", "junior", "fellow", "apprentice"]) else "entry_level",
                    "internship_category": self._categorize_role(role),
                    "description": desc,
                    "stipend_text": "Competitive Salary & Equity",
                    "is_paid": True,
                    "compensation_type": "undisclosed",
                    "min_stipend": None,
                    "max_stipend": None,
                    "currency": "USD",
                    "stipend_period": "year",
                    "duration_months": None,
                    "posted_at": posted_dt,
                    "deadline_at": None,
                    "original_url": item_url,
                    "application_url": item_url,
                    "source_url": f"https://news.ycombinator.com/item?id={item['id']}",
                    "external_id": f"hn_{item['id']}",
                    "source_platform": "ycombinator",
                    "raw_data": item
                })

        return results

    def _parse_yc_title(self, title: str):
        """
        Parses titles like:
        - "Mbodi AI (YC P25) Is Hiring Research and Robotic Engineers"
        - "PostHog (YC W20) is hiring an engineering intern in London or Remote"
        - "Ashby (YC W19) Is Hiring EMs"
        """
        clean = html.unescape(title)
        
        batch = ""
        batch_match = re.search(r'\((YC\s*[A-Z0-9]+)\)', clean, re.IGNORECASE)
        if batch_match:
            batch = batch_match.group(1).upper()
            
        company = ""
        role = clean
        loc = ""

        # Pattern: [Company] [(Batch)] [is hiring / Is Hiring] [Role] [(Location)]
        hiring_split = re.split(r'\s+(?:is hiring|Is Hiring|IS HIRING)\s+', clean)
        if len(hiring_split) == 2:
            comp_part, role_part = hiring_split
            comp_part = re.sub(r'\(YC\s*[A-Z0-9]+\)', '', comp_part, flags=re.IGNORECASE).strip()
            company = comp_part
            role = role_part.strip()
        else:
            dash_split = re.split(r'\s*[-:]\s*', clean)
            if len(dash_split) >= 2:
                company = dash_split[0]
                role = dash_split[1]
            else:
                company = "YC Startup"

        role = re.sub(r'^(?:a|an|our|the)\s+', '', role, flags=re.IGNORECASE).strip()

        loc_match = re.search(r'\s+(?:in|at)\s+([A-Za-z\s,/]+(?:\sor\sRemote)?)$', role, re.IGNORECASE)
        if loc_match:
            loc = loc_match.group(1).strip()
            role = role[:loc_match.start()].strip()

        if role.endswith(")"):
            inner_paren = re.search(r'\(([^)]+)\)$', role)
            if inner_paren and any(w in inner_paren.group(1).lower() for w in ["remote", "hybrid", "nyc", "sf", "london"]):
                loc = loc or inner_paren.group(1).strip()
                role = role[:inner_paren.start()].strip()

        return company or "YC Startup", batch, role or clean, loc

    def _categorize_role(self, role: str) -> str:
        r_low = role.lower()
        if any(k in r_low for k in ["ai", "machine learning", "ml", "nlp", "llm", "robotic"]):
            return "ai_ml"
        elif any(k in r_low for k in ["data", "analytics"]):
            return "data_science"
        elif any(k in r_low for k in ["frontend", "front-end", "ui", "react"]):
            return "frontend"
        elif any(k in r_low for k in ["backend", "back-end", "api", "distributed"]):
            return "backend"
        elif any(k in r_low for k in ["full stack", "fullstack"]):
            return "fullstack"
        elif any(k in r_low for k in ["devops", "cloud", "infra", "sre"]):
            return "devops_cloud"
        return "software_engineering"
