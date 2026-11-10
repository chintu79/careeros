import re
from typing import Dict, Any, Tuple, Optional

# Positive internship indicators (must have word boundaries)
INTERN_TITLE_REGEX = re.compile(
    r'\b(intern|internship|interns|co-?op|trainee|apprentice|fellowship|fellow)\b',
    re.IGNORECASE
)

# False positive words that contain 'intern'
FALSE_POSITIVE_REGEX = re.compile(
    r'\b(internal|international|internet)\b',
    re.IGNORECASE
)

# Seniority keywords that disqualify a role from being an internship
SENIORITY_EXCLUSIONS = re.compile(
    r'\b(senior|sr\b|lead|principal|staff\b|director|head of|vice president|vp\b|manager|executive director|general manager)\b',
    re.IGNORECASE
)

# Training scams and fee-charging courses disguised as internships
TRAINING_SCAM_PATTERNS = [
    r'pay\s+(?:to\s+learn|for\s+training|registration\s+fee|course\s+fee)',
    r'(?:fee|charges|cost)\s+(?:applicable|required|mandatory|of\s+₹|of\s+rs)',
    r'training\s+program\s+with\s+placement\s+fee',
    r'guaranteed\s+placement\s+after\s+paid\s+training',
    r'pay\s+(?:₹|rs\.?)\s*\d+',
    r'security\s+deposit\s+required'
]
SCAM_REGEX = re.compile('|'.join(TRAINING_SCAM_PATTERNS), re.IGNORECASE)

def is_valid_internship(
    title: str, 
    description: str = "", 
    company_name: str = "", 
    url: str = ""
) -> Tuple[bool, Optional[str]]:
    """
    Strict filter to verify if a posting is a genuine internship.
    Returns: (is_valid, rejection_reason)
    """
    if not title or not title.strip():
        return False, "Missing or empty job title"

    title_clean = title.strip()

    # 1. Check for positive intern keyword
    intern_matches = list(INTERN_TITLE_REGEX.finditer(title_clean))
    if not intern_matches:
        # Check description intro if title has 'trainee' or 'co-op'
        desc_start = description[:400] if description else ""
        if not INTERN_TITLE_REGEX.search(desc_start):
            return False, f"Title '{title_clean}' does not contain an internship or apprentice keyword"

    # 2. Check for false positives: if the only 'intern' occurrences are actually 'internal', 'international', etc.
    # We remove false positive words and verify if an intern word still remains
    title_without_false_positives = FALSE_POSITIVE_REGEX.sub(" ", title_clean)
    if not INTERN_TITLE_REGEX.search(title_without_false_positives):
        return False, f"Title '{title_clean}' matched a false-positive substring (internal/international/internet)"

    # 3. Check for Senior/Lead/Manager exclusions
    if SENIORITY_EXCLUSIONS.search(title_clean):
        return False, f"Title '{title_clean}' indicates a senior, lead, or managerial full-time position"

    # 4. Check for training scams / fee requirements in description
    if description and SCAM_REGEX.search(description):
        return False, "Posting flagged as a paid training course or scam requiring fees"

    # 5. Check employer identification
    if not company_name or company_name.strip().lower() in ["unknown", "confidential", "n/a", "none"]:
        return False, "Posting lacks verified employer or company name"

    # 6. Check URL availability
    if not url or not url.strip() or not url.startswith("http"):
        return False, "Posting lacks a valid, traceable HTTP/HTTPS URL"

    return True, None
