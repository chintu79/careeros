import re
from typing import Dict, Any, Tuple

# Title normalization mappings
TITLE_CANONICAL_MAP = [
    (r'(?i)\b(ai|artificial intelligence)\s+(eng|engineer|researcher|scientist)?\s*(intern|internship)?\b', "AI Engineer Intern"),
    (r'(?i)\b(ml|machine learning)\s*(eng|engineer)?\s*(intern|internship)?\b', "Machine Learning Intern"),
    (r'(?i)\b(data sci|data science)\s*(intern|internship)?\b', "Data Science Intern"),
    (r'(?i)\b(generative ai|genai|llm)\s*(engineer|developer|intern|internship)?\b', "Generative AI Intern"),
    (r'(?i)\b(full\s*stack|sde\s*full\s*stack)\s*(developer|engineer)?\s*(intern|internship)?\b', "Full Stack Developer Intern"),
    (r'(?i)\b(frontend|front-end|ui)\s*(developer|engineer)?\s*(intern|internship)?\b', "Frontend Developer Intern"),
    (r'(?i)\b(backend|back-end|api)\s*(developer|engineer)?\s*(intern|internship)?\b', "Backend Developer Intern"),
    (r'(?i)\b(software\s*engineer(?:ing)?|software\s*eng\b|software\s*developer|sde)\s*(intern|internship|i|1)?\b', "Software Engineer Intern"),
    (r'(?i)\b(python)\s*(developer|engineer)?\s*(intern|internship)?\b', "Python Developer Intern"),
    (r'(?i)\b(devops|cloud)\s*(engineer)?\s*(intern|internship)?\b', "DevOps & Cloud Intern")
]

CITY_MAP = {
    "pune": "Pune, India",
    "bengaluru": "Bengaluru, India",
    "bangalore": "Bengaluru, India",
    "mumbai": "Mumbai, India",
    "hyderabad": "Hyderabad, India",
    "chennai": "Chennai, India",
    "delhi": "Delhi NCR, India",
    "gurugram": "Delhi NCR, India",
    "noida": "Delhi NCR, India"
}

def normalize_title(title: str) -> str:
    """Normalize raw title into standard CareerOS role classification."""
    clean = title.strip()
    for pattern, canonical in TITLE_CANONICAL_MAP:
        if re.search(pattern, clean):
            return canonical
    # If no mapping matched, retain capitalized clean title
    return clean

def normalize_location(location: str, workplace_type: str = "") -> Tuple[str, str]:
    """Normalize raw location and workplace type."""
    loc_clean = (location or "").strip()
    loc_lower = loc_clean.lower()
    
    determined_workplace = workplace_type or "onsite"
    if "remote" in loc_lower or "anywhere" in loc_lower or "work from home" in loc_lower:
        determined_workplace = "remote"
        if "india" in loc_lower:
            return "Remote, India", "remote"
        return "Remote, Worldwide", "remote"
    elif "hybrid" in loc_lower:
        determined_workplace = "hybrid"
        
    for city_key, city_val in CITY_MAP.items():
        if city_key in loc_lower:
            return city_val, determined_workplace
            
    return loc_clean or "India", determined_workplace

def normalize_stipend(stipend_raw: str) -> Dict[str, Any]:
    """
    Parse raw stipend text strictly without inventing synthetic numbers.
    Distinguishes:
      - 'paid': explicit numeric stipend or salary range
      - 'unpaid': explicitly labeled unpaid
      - 'undisclosed': unmentioned or competitive without numbers (min/max=None)
    """
    if not stipend_raw or not stipend_raw.strip():
        return {
            "text": "Stipend Undisclosed",
            "is_paid": True,
            "compensation_type": "undisclosed",
            "min_val": None,
            "max_val": None,
            "currency": "INR",
            "period": "month"
        }
    
    text = stipend_raw.strip()
    lower = text.lower()
    
    if "unpaid" in lower or "free" in lower:
        return {
            "text": "Unpaid",
            "is_paid": False,
            "compensation_type": "unpaid",
            "min_val": 0.0,
            "max_val": 0.0,
            "currency": "INR",
            "period": "month"
        }
        
    currency = "INR"
    if "$" in text or "usd" in lower:
        currency = "USD"
    elif "€" in text or "eur" in lower:
        currency = "EUR"
    elif "£" in text or "gbp" in lower:
        currency = "GBP"
        
    # Extract numbers
    numbers = [float(n.replace(",", "")) for n in re.findall(r'\b\d+(?:,\d{3})*(?:\.\d+)?\b', text)]
    if not numbers:
        return {
            "text": text if ("competitive" in lower or "standard" in lower) else "Stipend Undisclosed",
            "is_paid": True,
            "compensation_type": "undisclosed",
            "min_val": None,
            "max_val": None,
            "currency": currency,
            "period": "month"
        }

    period = "month"
    if "year" in lower or "annum" in lower or "lpa" in lower:
        period = "year"
    elif "week" in lower:
        period = "week"
    elif "hour" in lower:
        period = "hour"
        
    min_val = 0.0
    max_val = 0.0
    if len(numbers) >= 2:
        min_val = min(numbers[0], numbers[1])
        max_val = max(numbers[0], numbers[1])
    elif len(numbers) == 1:
        min_val = numbers[0]
        max_val = numbers[0]
        
    # If in LPA (Lakhs Per Annum), convert to monthly INR
    if "lpa" in lower or "lakh" in lower:
        min_val = (min_val * 100000) / 12
        max_val = (max_val * 100000) / 12
        period = "month"
        
    return {
        "text": text,
        "is_paid": True,
        "compensation_type": "paid",
        "min_val": round(min_val, 2),
        "max_val": round(max_val, 2),
        "currency": currency,
        "period": period
    }

def infer_internship_category(title: str, description: str = "") -> str:
    """Classify opportunity into a standardized internship category."""
    text = f"{title} {description}".lower()
    if re.search(r'\b(ai|genai|llm|deep learning|artificial intelligence)\b', text):
        return "ai_ml"
    if re.search(r'\b(ml|machine learning)\b', text):
        return "ai_ml"
    if re.search(r'\b(data sci|data science|data analytics)\b', text):
        return "data_science"
    if re.search(r'\b(full\s*stack|fullstack)\b', text):
        return "fullstack"
    if re.search(r'\b(frontend|front-end|ui developer|web development)\b', text):
        return "frontend"
    if re.search(r'\b(backend|back-end|api developer|python developer)\b', text):
        return "backend"
    if re.search(r'\b(devops|cloud|infrastructure|sre)\b', text):
        return "devops_cloud"
    if re.search(r'\b(product management|product manager)\b', text):
        return "product"
    return "software_engineering"

def normalize_job_dict(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Execute complete Stage 2 Normalization on a job payload without inventing synthetic values."""
    raw_title = (raw.get("title") or "").strip()
    norm_title = normalize_title(raw_title) if raw_title else ""
    
    raw_loc = raw.get("location", "")
    workplace = raw.get("workplace_type", "")
    norm_loc, norm_workplace = normalize_location(raw_loc, workplace)
    
    stipend_info = normalize_stipend(raw.get("stipend_text", ""))
    
    company_name = (raw.get("company_name") or raw.get("company") or "").strip()
    
    # Clean internship type
    intern_type = "in-office"
    if norm_workplace == "remote" or "remote" in norm_loc.lower():
        intern_type = "remote"
    elif norm_workplace == "hybrid" or "hybrid" in norm_loc.lower():
        intern_type = "hybrid"

    orig_url = (raw.get("original_url") or raw.get("url") or "").strip()
    app_url = (raw.get("application_url") or orig_url).strip()
    src_url = (raw.get("source_url") or orig_url).strip()
    
    cat = raw.get("internship_category") or infer_internship_category(raw_title, raw.get("description", ""))

    return {
        "title": raw_title,
        "normalized_title": norm_title,
        "internship_category": cat,
        "company_name": company_name,
        "company_website": raw.get("company_website", ""),
        "location": raw_loc,
        "normalized_location": norm_loc,
        "workplace_type": norm_workplace,
        "internship_type": intern_type,
        "work_mode": raw.get("work_mode", "full-time"),
        "employment_type": "internship",
        "description": raw.get("description", ""),
        "required_skills": raw.get("required_skills", []),
        "preferred_skills": raw.get("preferred_skills", []),
        "eligibility": raw.get("eligibility") or None,
        "experience_required": raw.get("experience_required", "0-1 years / Fresher"),
        "stipend_text": stipend_info["text"],
        "min_stipend": stipend_info["min_val"],
        "max_stipend": stipend_info["max_val"],
        "currency": stipend_info["currency"],
        "stipend_period": stipend_info["period"],
        "is_paid": stipend_info["is_paid"],
        "compensation_type": stipend_info["compensation_type"],
        "duration_months": raw.get("duration_months"),
        "original_url": orig_url,
        "application_url": app_url,
        "source_url": src_url,
        "external_id": raw.get("external_id", ""),
        "source_platform": raw.get("source_platform", "manual"),
        "posted_at": raw.get("posted_at"),
        "deadline_at": raw.get("deadline_at"),
        "raw_data": raw
    }

