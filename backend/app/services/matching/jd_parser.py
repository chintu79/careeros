"""
Structured Job Description Parser for CareerOS Matching Intelligence.
Performs deterministic extraction of technical requirements, role classification,
experience and education constraints, and source-text provenance citations,
with robust adversarial defenses against prompt injection, negated requirements,
incidental mentions, and malformed inputs.
"""
import re
import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple

from backend.app.schemas.matching import (
    ParsedJobDescription,
    ExtractedRequirement,
    RequirementPriority
)
from backend.app.services.matching.taxonomy import (
    CANONICAL_ALIASES,
    canonicalize_tech_name
)

logger = logging.getLogger(__name__)

# Canonical Categorized Tech Catalogs
LANGUAGES = {
    "python", "javascript", "typescript", "c++", "c", "c#", "go", "golang",
    "rust", "java", "kotlin", "swift", "sql", "html", "css", "bash", "shell", "r"
}
FRAMEWORKS = {
    "react", "react.js", "next.js", "nextjs", "vue", "vue.js", "angular",
    "express", "fastapi", "flask", "django", "nestjs", "fastify", "spring boot",
    "node", "node.js", "nodejs",
    "pytorch", "tensorflow", "keras", "scikit-learn", "pandas", "numpy",
    "tailwind css", "graphql", "rest api"
}
DATABASES = {
    "postgresql", "postgres", "mysql", "mongodb", "redis", "sqlite", "mariadb",
    "cassandra", "elasticsearch", "dynamodb", "couchbase", "snowflake"
}
CLOUD_DEVOPS = {
    "docker", "kubernetes", "k8s", "aws", "gcp", "azure", "git", "github",
    "ci/cd", "github actions", "gitlab ci", "jenkins", "linux", "terraform", "kafka"
}
CERTIFICATIONS = {
    "aws certified", "gcp certified", "azure certified", "cka", "ckad",
    "oscp", "security+", "network+", "pmp"
}

ROLE_CATEGORIES = {
    "ai_ml": ["machine learning", "ai", "deep learning", "nlp", "computer vision", "llm", "data science"],
    "frontend": ["frontend", "front end", "react", "vue", "angular", "ui/ux", "web developer"],
    "backend": ["backend", "back end", "fastapi", "django", "flask", "express", "api engineer", "server"],
    "fullstack": ["full stack", "fullstack", "full-stack", "mern", "mean"],
    "devops_cloud": ["devops", "cloud", "infrastructure", "sre", "site reliability", "platform engineer"],
    "mobile": ["android", "ios", "flutter", "react native", "mobile"]
}

# Negation detection patterns (excluding optional/preferred indicators)
NEGATION_PREFIX_PATTERNS = [
    r'\b(?:no|not|neither|nor|without|don\'t|doesn\'t|does\s+not|do\s+not|never)\b[^.!?\n]{0,35}\b',
    r'\b(?:no\s+prior|zero|little\s+to\s+no)\b[^.!?\n]{0,35}\b'
]
NEGATION_SUFFIX_PATTERNS = [
    r'\b[^.!?\n]{0,35}\b(?:is\s+not\s+required|not\s+required|is\s+not\s+needed|not\s+needed|is\s+not\s+necessary|not\s+expected|never\s+required)\b'
]

# Incidental / legacy migration patterns (tech mentioned without requiring candidate competency)
INCIDENTAL_PATTERNS = [
    r'\b(?:migrat(?:e|ing|ion)\s+(?:away\s+from|off|from)|transition(?:ing)?\s+from|replac(?:e|ing)|deprecat(?:e|ing)|phasing\s+out)\b[^.!?\n]{0,30}\b',
    r'\b(?:collaborat(?:e|ing)\s+with\s+(?:teams\s+using|engineers\s+using)|interface\s+with\s+external\s+systems\s+in)\b[^.!?\n]{0,30}\b'
]


def sanitize_job_description_text(text: str) -> str:
    """
    Cleans untrusted job description text:
    - Truncates oversized input to 50,000 chars to prevent ReDoS.
    - Strips hidden HTML comments and prompt-injection instructions.
    """
    if not text:
        return ""
    # Clamping
    sanitized = text[:50000]
    # Strip HTML comments
    sanitized = re.sub(r'<!--.*?-->', '', sanitized, flags=re.DOTALL)
    # Strip system prompt override injections
    sanitized = re.sub(r'\[\/?(?:SYSTEM|INSTRUCTION|PROMPT)[^\]]*\]', '', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'###\s*System:.*?(?:\n|$)', '', sanitized, flags=re.IGNORECASE)
    return sanitized.strip()


def compute_job_description_hash(title: str, company: Optional[str], description: str) -> str:
    """Computes a deterministic SHA-256 content hash of job description inputs."""
    payload = f"{title or ''}:{company or ''}:{description or ''}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def find_source_snippet(keyword: str, text: str) -> str:
    """Locates the verbatim sentence or line containing the keyword in description."""
    if not text:
        return f"Mentioned in job description: {keyword}"

    lines = text.split("\n")
    for line in lines:
        cleaned = line.strip()
        if re.search(r'\b' + re.escape(keyword) + r'\b', cleaned, re.IGNORECASE):
            return cleaned[:150]
    
    # Fallback: search across sentences
    sentences = re.split(r'[.!?]+', text)
    for sent in sentences:
        cleaned = sent.strip()
        if re.search(r'\b' + re.escape(keyword) + r'\b', cleaned, re.IGNORECASE):
            return cleaned[:150]

    return f"Mentioned in job description: {keyword}"


def is_negated_mention(keyword: str, text: str) -> bool:
    """
    Determines whether a technology keyword is explicitly negated in the text
    (e.g., 'No prior Kubernetes experience required', 'Docker is not required').
    Returns True ONLY IF all occurrences of the keyword are negated.
    """
    clauses = re.split(r'[.;\n]+', text)
    escaped_kw = re.escape(keyword)
    
    has_mention = False
    has_positive = False

    for clause in clauses:
        c_clean = clause.strip()
        if not re.search(r'\b' + escaped_kw + r'\b', c_clean, re.IGNORECASE):
            continue

        has_mention = True
        is_negated_clause = False

        # Check prefix negation (e.g. "no prior Kubernetes")
        for pref in NEGATION_PREFIX_PATTERNS:
            if re.search(pref + escaped_kw + r'\b', c_clean, re.IGNORECASE):
                is_negated_clause = True
                break

        # Check suffix negation (e.g. "Kubernetes is not required")
        if not is_negated_clause:
            for suff in NEGATION_SUFFIX_PATTERNS:
                if re.search(r'\b' + escaped_kw + suff, c_clean, re.IGNORECASE):
                    is_negated_clause = True
                    break

        if not is_negated_clause:
            has_positive = True

    return has_mention and not has_positive


def is_incidental_mention(keyword: str, text: str) -> bool:
    """
    Determines whether a technology keyword is purely incidental
    (e.g., 'Migrate away from legacy PHP', 'Help teams transition from C++').
    Returns True ONLY IF all occurrences of the keyword are incidental/legacy.
    """
    clauses = re.split(r'[.;\n]+', text)
    escaped_kw = re.escape(keyword)

    has_mention = False
    has_non_incidental = False

    for clause in clauses:
        c_clean = clause.strip()
        if not re.search(r'\b' + escaped_kw + r'\b', c_clean, re.IGNORECASE):
            continue

        has_mention = True
        is_incidental_clause = False

        for inc_pat in INCIDENTAL_PATTERNS:
            if re.search(inc_pat + escaped_kw + r'\b', c_clean, re.IGNORECASE):
                is_incidental_clause = True
                break

        if not is_incidental_clause:
            has_non_incidental = True

    return has_mention and not has_non_incidental


def partition_mandatory_and_preferred(text_lower: str) -> Tuple[str, str]:
    """
    Robustly partitions job description into mandatory and preferred text sections.
    Guards against false positives from compensation phrases like 'annual bonus' or 'bonus package'.
    """
    # 1. Look for explicit preferred section headers
    header_patterns = [
        r'(?:^|\n)\s*(?:###?\s*|\*\*\s*)?(?:preferred\s*(?:qualifications|skills|requirements)?|nice\s*to\s*have|bonus\s*(?:skills|points|if\s*you\s*have)|plus\s*if\s*you\s*have|desired\s*(?:qualifications|skills)|good\s*to\s*have)(?:\s*[:\n\-*]|\s*\*\*)',
        r'(?:^|\n)\s*(?:###?\s*|\*\*\s*)?(?:what\s*would\s*be\s*a\s*plus|what\s*is\s*a\s*plus)(?:\s*[:\n\-*]|\s*\*\*)'
    ]

    for pat in header_patterns:
        match = re.search(pat, text_lower, re.IGNORECASE)
        if match:
            split_idx = match.start()
            mandatory_part = text_lower[:split_idx]
            preferred_part = text_lower[split_idx:]
            return mandatory_part, preferred_part

    # 2. Fallback: check for inline plus/bonus that are NOT compensation-related
    # Guard against 'annual bonus', 'signing bonus', 'performance bonus', 'bonus structure', 'bonus plan'
    text_without_comp_bonus = re.sub(
        r'\b(?:annual|signing|sign-on|performance|cash|retention|target|incentive)\s+bonus\b',
        'COMPENSATION_REWARD',
        text_lower
    )
    text_without_comp_bonus = re.sub(
        r'\bbonus\s+(?:structure|plan|package|scheme|compensation|pool|eligible)\b',
        'COMPENSATION_REWARD',
        text_without_comp_bonus
    )

    inline_split = re.split(r'\b(preferred|nice to have|desired qualifications|is a plus|is a bonus)\b', text_without_comp_bonus)
    if len(inline_split) > 1:
        # Reconstruct actual indices
        split_match = re.search(r'\b(preferred|nice to have|desired qualifications|is a plus|is a bonus)\b', text_without_comp_bonus)
        if split_match:
            idx = split_match.start()
            return text_lower[:idx], text_lower[idx:]

    return text_lower, ""


def parse_job_description_deterministic(
    title: str,
    description: str,
    company: Optional[str] = None,
    location: Optional[str] = None
) -> ParsedJobDescription:
    """
    Deterministically parses job description with adversarial safety:
    - Strips prompt injections and truncates oversized text.
    - Accurately classifies role category, employment type, and work mode.
    - Filters negated requirements and incidental legacy mentions.
    - Partitions mandatory vs preferred requirements without compensation collision.
    - Captures source text evidence references for each requirement.
    """
    clean_title = sanitize_job_description_text(title or "Software Engineer")
    clean_desc = sanitize_job_description_text(description or "")

    full_text = f"{clean_title}\n{clean_desc}"
    text_lower = full_text.lower()

    # 1. Classify role category
    role_cat = "software_engineering"
    for cat, keywords in ROLE_CATEGORIES.items():
        if any(kw in clean_title.lower() for kw in keywords) or any(kw in text_lower[:300] for kw in keywords):
            role_cat = cat
            break

    # 2. Classify employment type and work mode
    is_internship = bool(
        re.search(r'\b(intern|internship|co-?op|trainee|fresher)\b', clean_title, re.IGNORECASE) or
        re.search(r'\b(internship|intern|fresher)\b', text_lower[:400])
    )
    employment_type = "internship" if is_internship else "full_time"

    work_mode = "onsite"
    if "remote" in text_lower or (location and "remote" in location.lower()):
        work_mode = "remote"
    elif "hybrid" in text_lower or (location and "hybrid" in location.lower()):
        work_mode = "hybrid"

    # 3. Classify experience constraints (handles "5+ years", "3-5 years", "18+ months", "freshers")
    exp_req = "0-1 years / Fresher" if is_internship else "1-3 years"
    exp_match = re.search(
        r'(\d+[\-\+]?\s*(?:to|-)?\s*(?:\d+)?\s*(?:years?|yrs?|months?)(?:\s+(?:of\s+)?(?:[\w\/\-]+\s+){0,3}experience)?)',
        text_lower
    )
    if exp_match:
        exp_req = exp_match.group(0).capitalize()
    elif is_internship or "no experience required" in text_lower or "fresher" in text_lower:
        exp_req = "0-1 years / Fresher"

    # 4. Classify educational prerequisites
    edu_req = "Bachelor's / Master's degree in Computer Science, Engineering, or related field."
    edu_match = re.search(
        r'(b\.?tech|bachelor\'?s?|master\'?s?|m\.?tech|phd|degree|currently enrolled|pursuing)',
        text_lower
    )
    if edu_match:
        edu_req = f"Degree requirement: {edu_match.group(0).capitalize()}"

    # 5. Robust partitioning of text into mandatory and preferred sections
    mandatory_text, preferred_text = partition_mandatory_and_preferred(text_lower)

    # 6. Extract concrete technical requirements across taxonomies
    req_dict: Dict[str, ExtractedRequirement] = {} # canonical_name.lower() -> ExtractedRequirement

    def _process_catalog(catalog: set, category: str):
        for raw_kw in catalog:
            # Fast substring check before running regexes (blazing fast on massive texts)
            if raw_kw not in text_lower:
                continue

            pattern = r'\b' + re.escape(raw_kw) + r'\b'
            canon_name = canonicalize_tech_name(raw_kw)
            canon_lower = canon_name.lower()

            # Adversarial Check 1: Negated mentions (e.g. "No prior Kubernetes experience required")
            if is_negated_mention(raw_kw, text_lower):
                continue

            # Adversarial Check 2: Incidental legacy migration (e.g. "Migrating off PHP")
            if is_incidental_mention(raw_kw, text_lower):
                continue

            source = find_source_snippet(raw_kw, clean_desc or clean_title)
            source_lower = source.lower()

            # Check if this requirement's specific source context indicates preferred/optional
            is_inline_preferred = bool(re.search(
                r'\b(?:is\s+a\s+plus|is\s+a\s+bonus|is\s+optional|not\s+mandatory|nice\s+to\s+have|preferred|bonus\s+points)\b',
                source_lower
            ))

            in_mandatory = bool(re.search(pattern, mandatory_text))
            in_preferred = bool(re.search(pattern, preferred_text))

            if in_mandatory and not is_inline_preferred:
                priority = RequirementPriority.MANDATORY
            elif in_preferred or is_inline_preferred:
                priority = RequirementPriority.PREFERRED
            else:
                continue

            # Deduplication with priority elevation
            if canon_lower in req_dict:
                existing = req_dict[canon_lower]
                # If existing is preferred and we find mandatory, upgrade priority and source
                if existing.priority == RequirementPriority.PREFERRED and priority == RequirementPriority.MANDATORY:
                    existing.priority = RequirementPriority.MANDATORY
                    existing.source_text = source
            else:
                prefix = "req_mand" if priority == RequirementPriority.MANDATORY else "req_pref"
                req_dict[canon_lower] = ExtractedRequirement(
                    name=canon_name,
                    category=category,
                    priority=priority,
                    source_text=source,
                    evidence_reference=f"{prefix}_{len(req_dict)}"
                )

    _process_catalog(LANGUAGES, "programming_language")
    _process_catalog(FRAMEWORKS, "framework_library")
    _process_catalog(DATABASES, "database")
    _process_catalog(CLOUD_DEVOPS, "cloud_devops")
    _process_catalog(CERTIFICATIONS, "certification")

    req_list = list(req_dict.values())

    # Group extracted lists
    mandatory_skills = [r.name for r in req_list if r.priority == RequirementPriority.MANDATORY]
    preferred_skills = [r.name for r in req_list if r.priority == RequirementPriority.PREFERRED]
    languages = [r.name for r in req_list if r.category == "programming_language"]
    frameworks = [r.name for r in req_list if r.category == "framework_library"]
    databases = [r.name for r in req_list if r.category == "database"]
    cloud_devops = [r.name for r in req_list if r.category == "cloud_devops"]
    certs = [r.name for r in req_list if r.category == "certification"]

    # 7. Extract Responsibilities
    responsibilities = []
    lines = clean_desc.split("\n")
    for line in lines:
        cleaned = line.strip()
        if cleaned.startswith(("-", "*", "•", "1.", "2.", "3.")) and len(cleaned) > 15:
            responsibilities.append(cleaned.lstrip("-*• 0123456789.").strip())
        if len(responsibilities) >= 6:
            break

    if not responsibilities:
        responsibilities = [
            f"Develop and maintain {clean_title} components and modules.",
            "Write clean, testable, and well-documented code.",
            "Collaborate with cross-functional engineering teams."
        ]

    content_hash = compute_job_description_hash(clean_title, company, clean_desc)

    return ParsedJobDescription(
        job_title=clean_title,
        company=company,
        role_category=role_cat,
        experience_requirements=exp_req,
        mandatory_skills=mandatory_skills,
        preferred_skills=preferred_skills,
        programming_languages=languages,
        frameworks_libraries=frameworks,
        database_technologies=databases,
        cloud_devops=cloud_devops,
        education_requirements=edu_req,
        certifications=certs,
        responsibilities=responsibilities,
        location=location,
        work_mode=work_mode,
        employment_type=employment_type,
        requirements=req_list,
        content_hash=content_hash
    )
