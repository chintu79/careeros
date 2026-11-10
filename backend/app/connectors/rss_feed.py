import logging
import httpx
from datetime import datetime
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from backend.app.connectors.base import BaseConnector

logger = logging.getLogger(__name__)

class RSSFeedConnector(BaseConnector):
    def __init__(self, feed_url: str = None, company_name: str = "Feed Publisher"):
        super().__init__(name="RSS Feeds", source_type="rss")
        self.feed_url = feed_url
        self.company_name = company_name

    async def fetch_jobs(self, **kwargs) -> List[Dict[str, Any]]:
        url = kwargs.get("feed_url", self.feed_url)
        company = kwargs.get("company_name", self.company_name)
        
        if not url:
            return []
            
        results = []
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.content, "xml")
                    items = soup.find_all(["item", "entry"])
                    for item in items[:20]:
                        title = item.find("title").get_text() if item.find("title") else "Engineering Role"
                        link = item.find("link")
                        url_val = link.get_text() if link and link.get_text() else (link.get("href") if link else "")
                        
                        desc_elem = item.find(["description", "summary", "content"])
                        desc = ""
                        if desc_elem:
                            raw_desc = desc_elem.get_text()
                            desc = BeautifulSoup(raw_desc, "lxml").get_text(separator="\n").strip()
                            
                        pub_elem = item.find(["pubDate", "published", "updated"])
                        posted_dt = None
                        if pub_elem:
                            try:
                                posted_dt = datetime.strptime(pub_elem.get_text().strip(), "%a, %d %b %Y %H:%M:%S %z")
                            except Exception:
                                pass
                                
                        results.append({
                            "title": title,
                            "company_name": company,
                            "location": "Remote, India",
                            "workplace_type": "remote",
                            "employment_type": "internship" if "intern" in title.lower() else "entry_level",
                            "description": desc or title,
                            "stipend_text": "Competitive Stipend",
                            "duration_months": 6,
                            "original_url": url_val or url,
                            "external_id": f"rss_{hash(url_val or title)}",
                            "source_platform": "rss",
                            "posted_at": posted_dt
                        })
        except Exception as e:
            logger.error(f"RSS feed fetch failed for {url}: {e}")
            
        return results
