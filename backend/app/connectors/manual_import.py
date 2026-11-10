import json
import logging
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict, Any, Optional
from backend.app.connectors.base import BaseConnector

logger = logging.getLogger(__name__)

class ManualImportConnector(BaseConnector):
    def __init__(self):
        super().__init__(name="Manual Import", source_type="manual")

    async def fetch_jobs(self, **kwargs):
        return []

    async def extract_from_url(self, url: str) -> Dict[str, Any]:
        """Fetch and extract job details from a public career URL with SSRF protection."""
        clean_url = (url or "").strip()
        from backend.app.services.verifier import is_safe_external_url
        is_safe, ssrf_err = is_safe_external_url(clean_url)
        if not is_safe:
            raise ValueError(f"Cannot import from target URL: {ssrf_err}")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(timeout=25.0, headers=headers, follow_redirects=True) as client:
            resp = await client.get(clean_url)
            if resp.status_code != 200:
                raise ValueError(f"Target URL returned HTTP status {resp.status_code}")
                
            soup = BeautifulSoup(resp.content, "lxml")
            
            # 1. Try schema.org JSON-LD
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        data = data[0]
                    if data.get("@type") == "JobPosting":
                        title = data.get("title", "")
                        comp_name = data.get("hiringOrganization", {}).get("name", "")
                        desc = BeautifulSoup(data.get("description", ""), "lxml").get_text(separator="\n").strip()
                        loc_obj = data.get("jobLocation", {})
                        location = ""
                        if isinstance(loc_obj, dict):
                            addr = loc_obj.get("address", {})
                            if isinstance(addr, dict):
                                location = f"{addr.get('addressLocality', '')}, {addr.get('addressCountry', '')}".strip(", ")
                        return {
                            "title": title,
                            "company_name": comp_name,
                            "location": location or "India",
                            "workplace_type": "remote" if "remote" in location.lower() else "onsite",
                            "internship_type": "remote" if "remote" in location.lower() else "in-office",
                            "work_mode": "full-time",
                            "employment_type": "internship",
                            "description": desc,
                            "stipend_text": "Stipend Undisclosed",
                            "duration_months": None,
                            "original_url": clean_url,
                            "application_url": clean_url,
                            "source_url": clean_url,
                            "external_id": f"url_{abs(hash(clean_url))}",
                            "source_platform": "direct_url"
                        }
                except Exception:
                    continue
                    
            # 2. Fallback to OpenGraph and meta tags
            og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "twitter:title"})
            title = og_title.get("content", "").strip() if og_title else ""
            if not title and soup.title:
                title = soup.title.get_text().strip()
                
            # Clean title
            if " - " in title:
                title = title.split(" - ")[0]
            elif " | " in title:
                title = title.split(" | ")[0]
                
            og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
            desc = og_desc.get("content", "").strip() if og_desc else ""
            
            # If description in meta tag is short, grab main text
            if len(desc) < 200:
                main_elem = soup.find("main") or soup.find("article") or soup.body
                if main_elem:
                    desc = main_elem.get_text(separator="\n").strip()[:3500]
                    
            comp_name = ""
            # Try deriving company name from URL domain
            try:
                from urllib.parse import urlparse
                domain = urlparse(clean_url).netloc.replace("www.", "")
                comp_name = domain.split(".")[0].capitalize()
            except Exception:
                pass

            return {
                "title": title,
                "company_name": comp_name,
                "location": "India",
                "workplace_type": "remote" if "remote" in (title + desc).lower() else "onsite",
                "internship_type": "remote" if "remote" in (title + desc).lower() else "in-office",
                "work_mode": "full-time",
                "employment_type": "internship",
                "description": desc or f"Opportunity imported from {clean_url}",
                "stipend_text": "Stipend Undisclosed",
                "duration_months": None,
                "original_url": clean_url,
                "application_url": clean_url,
                "source_url": clean_url,
                "external_id": f"url_{abs(hash(clean_url))}",
                "source_platform": "direct_url"
            }

    def parse_pasted_text(
        self, 
        title: str, 
        company_name: str, 
        location: str, 
        description: str,
        stipend_text: str = "",
        original_url: str = ""
    ) -> Dict[str, Any]:
        """Convert pasted job description into standard structure without inventing data."""
        clean_url = original_url.strip()
        urn_id = f"urn:careeros:manual:{abs(hash((title or '') + (company_name or '') + str(datetime.utcnow().date())))}"
        canonical_url = clean_url if clean_url else urn_id
        
        return {
            "title": title.strip(),
            "company_name": company_name.strip(),
            "location": location.strip() or "India",
            "workplace_type": "remote" if "remote" in (location + description).lower() else "onsite",
            "internship_type": "remote" if "remote" in (location + description).lower() else "in-office",
            "work_mode": "full-time",
            "employment_type": "internship",
            "description": description.strip(),
            "stipend_text": stipend_text.strip() or "Stipend Undisclosed",
            "duration_months": None,
            "original_url": canonical_url,
            "application_url": clean_url if clean_url else None,
            "source_url": clean_url if clean_url else None,
            "external_id": f"manual_{abs(hash(canonical_url))}",
            "source_platform": "manual_paste"
        }
