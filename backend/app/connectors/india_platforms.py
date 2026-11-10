import re
from typing import Dict, Any, Optional

INDIA_PLATFORMS = {
    "internshala": {
        "name": "Internshala",
        "integration_type": "automated_feed_and_url",
        "status": "operational",
        "description": "India's premier student internship platform. Supports direct category search scraping, verified listing detail extraction, and manual URL imports.",
        "url_pattern": r'internshala\.com/internship/detail/.*'
    },
    "linkedin": {
        "name": "LinkedIn Jobs",
        "integration_type": "guest_api_and_url",
        "status": "operational",
        "description": "Public LinkedIn Guest Job Search endpoint. Discovers live, verified internships in India with direct application links without requiring credentials.",
        "url_pattern": r'linkedin\.com/jobs/view/.*'
    },
    "naukri": {
        "name": "Naukri",
        "integration_type": "manual_and_url",
        "status": "unsupported",
        "description": "Leading Indian job portal. Automated scraping is protected by bot-detection firewalls; supports manual job description paste and public posting URL imports.",
        "url_pattern": r'naukri\.com/job-listings-.*',
        "failure_reason": "Protected by Cloudflare/Akamai bot management and session authentication. Manual URL import active. Email alert parsing supported."
    },
    "wellfound": {
        "name": "Wellfound (AngelList)",
        "integration_type": "manual_and_url",
        "status": "unsupported",
        "description": "High-growth AI startups and tech ventures. Automated scraping requires Cloudflare Turnstile token; import via startup job URLs or pasted job specs.",
        "url_pattern": r'wellfound\.com/jobs/.*',
        "failure_reason": "Protected by Cloudflare Turnstile JavaScript challenge. Manual URL import active."
    },
    "indeed": {
        "name": "Indeed India",
        "integration_type": "manual_and_url",
        "status": "unsupported",
        "description": "Global and India-focused listings. Public automated scraping returns HTTP 403 Forbidden due to Cloudflare Bot Management. Direct application link import active.",
        "url_pattern": r'indeed\.com/(?:viewjob|rc/clk).*',
        "failure_reason": "HTTP 403 Forbidden - Cloudflare Bot Management blocks headless automated requests without browser challenge resolution. Manual URL import active."
    },
    "aicte": {
        "name": "AICTE Internship Portal",
        "integration_type": "portal_and_url",
        "status": "unsupported",
        "description": "Government of India AICTE National Internship Portal. Serves university student internships across public and private sector initiatives.",
        "url_pattern": r'internship\.aicte-india\.org/.*',
        "failure_reason": "Portal listings render via dynamic ASP.NET stateful sessions. Manual URL import active."
    }
}

def parse_job_alert_email(email_text: str, platform_hint: str = "internshala") -> Dict[str, Any]:
    """Parse forwarded or pasted job alert email notification text."""
    lines = [line.strip() for line in email_text.split("\n") if line.strip()]
    
    title = "Software Engineer Intern"
    company = "Hiring Company"
    stipend = "Stipend Undisclosed"
    location = "Remote, India"
    
    for line in lines[:15]:
        if any(kw in line.lower() for kw in ["intern", "engineer", "developer", "data science"]):
            title = line
        elif "company:" in line.lower() or "at " in line.lower():
            company = line.replace("Company:", "").replace("at ", "").strip()
        elif "stipend:" in line.lower() or "₹" in line:
            stipend = line
        elif "location:" in line.lower():
            location = line.replace("Location:", "").strip()
            
    urn_id = f"urn:careeros:email-alert:{platform_hint}:{abs(hash(email_text[:120]))}"
    return {
        "title": title,
        "company_name": company,
        "company_website": "",
        "location": location,
        "workplace_type": "remote" if "remote" in location.lower() else "onsite",
        "internship_type": "remote" if "remote" in location.lower() else "in-office",
        "work_mode": "full-time",
        "employment_type": "internship",
        "description": email_text,
        "stipend_text": stipend,
        "duration_months": None,
        "original_url": urn_id,
        "application_url": None,
        "source_url": None,
        "source_name": f"Email Alert - {platform_hint.capitalize()}",
        "external_id": f"email_{abs(hash(email_text[:80]))}",
        "source_platform": platform_hint
    }
