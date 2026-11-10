import json
import re
import logging
from typing import Dict, Any, List
from backend.app.ai.ollama_client import ollama_client

logger = logging.getLogger(__name__)

SYSTEM_EXTRACTION_PROMPT = """
You are an expert technical job description analyzer for CareerOS.
Analyze the provided job title and description and return a strictly valid JSON object with the following schema:
{
  "responsibilities": ["string"],
  "mandatory_technical_skills": ["string"],
  "preferred_skills": ["string"],
  "programming_languages": ["string"],
  "frameworks_libraries": ["string"],
  "tools_platforms": ["string"],
  "educational_requirements": "string",
  "experience_requirements": "string",
  "soft_skills": ["string"],
  "eligibility_restrictions": ["string"],
  "duration_details": "string",
  "compensation_details": "string"
}
Extract concrete skills and actual requirements without hallucinating. Return JSON only.
"""

COMMON_TECH_SKILLS = [
    "Python", "JavaScript", "TypeScript", "C++", "Java", "Go", "Rust", "SQL",
    "React", "Node.js", "Express", "Next.js", "Vue", "Angular", "Django", "FastAPI", "Flask",
    "PyTorch", "TensorFlow", "Keras", "Scikit-Learn", "Pandas", "NumPy", "HuggingFace", "LangChain",
    "PostgreSQL", "MongoDB", "MySQL", "Redis", "Docker", "Kubernetes", "AWS", "GCP", "Azure",
    "Git", "Linux", "REST API", "GraphQL", "CI/CD", "Tailwind CSS", "HTML", "CSS"
]

def fallback_heuristic_extraction(title: str, description: str) -> Dict[str, Any]:
    """Deterministic, resilient extraction fallback using pattern matching and keyword analysis."""
    text = f"{title} {description}".lower()
    
    # 1. Detect technical skills
    found_mandatory: List[str] = []
    found_preferred: List[str] = []
    found_languages: List[str] = []
    found_frameworks: List[str] = []
    found_tools: List[str] = []

    languages = ["python", "javascript", "typescript", "c++", "java", "go", "rust", "sql", "html", "css"]
    frameworks = ["react", "node.js", "express", "next.js", "vue", "django", "fastapi", "flask", "pytorch", "tensorflow", "scikit-learn", "langchain", "tailwind css"]
    tools = ["docker", "kubernetes", "aws", "gcp", "azure", "git", "linux", "postgresql", "mongodb", "redis", "rest api"]

    for skill in COMMON_TECH_SKILLS:
        s_lower = skill.lower()
        # regex boundary match
        pattern = r'\b' + re.escape(s_lower) + r'\b'
        if re.search(pattern, text):
            if s_lower in languages:
                found_languages.append(skill)
            elif s_lower in frameworks:
                found_frameworks.append(skill)
            elif s_lower in tools:
                found_tools.append(skill)
            
            # Divide into mandatory vs preferred
            if "preferred" in text and s_lower in text.split("preferred")[-1]:
                found_preferred.append(skill)
            else:
                found_mandatory.append(skill)

    # 2. Extract responsibilities (bullet points or sentences)
    responsibilities = []
    lines = description.split("\n")
    for line in lines:
        cleaned = line.strip()
        if cleaned.startswith(("-", "*", "•", "1.", "2.", "3.")) and len(cleaned) > 15:
            responsibilities.append(cleaned.lstrip("-*• 0123456789.").strip())
        if len(responsibilities) >= 6:
            break
            
    if not responsibilities:
        responsibilities = [
            f"Contribute to active {title} codebase and architecture",
            "Collaborate with engineering team on sprints and code reviews",
            "Write clean, maintainable, and well-tested code",
            "Assist in debugging, testing, and deployment"
        ]

    # 3. Educational & Experience requirements
    edu = "Pursuing or completed Bachelor's/Master's in Computer Science, Data Science, or related engineering discipline."
    if "graduat" in text or "202" in text:
        edu_match = re.search(r'(b\.?tech|bachelor|master|m\.?tech|degree|student|graduating in 202[4-7])', text, re.IGNORECASE)
        if edu_match:
            edu = f"Degree requirement: {edu_match.group(0).capitalize()}"

    exp = "0-1 years (Internship / Entry-level). Fresh graduates and final-year students eligible."
    if "year" in text and ("experience" in text or "exp" in text):
        exp_match = re.search(r'(\d+[\-\+]?\s*(?:to\s*\d+)?\s*(?:years?|yrs?|months?)\s*(?:of\s*)?experience)', text, re.IGNORECASE)
        if exp_match:
            exp = exp_match.group(0)

    # 4. Eligibility restrictions (Country, work auth, etc.)
    restrictions = []
    if "us only" in text or "united states only" in text or "must be located in the us" in text:
        restrictions.append("US Residents Only (Not eligible for India applicants)")
    elif "eu only" in text or "european union" in text:
        restrictions.append("EU Residents Only")
    elif "india" in text or "pune" in text or "bengaluru" in text or "mumbai" in text or "hyderabad" in text:
        restrictions.append("Eligible for Candidates located in India")
    else:
        restrictions.append("Worldwide / Verify timezone overlap")

    if "citizen" in text or "visa" in text or "security clearance" in text:
        restrictions.append("Specific citizenship/clearance or authorization required")

    return {
        "responsibilities": responsibilities[:6],
        "mandatory_technical_skills": list(set(found_mandatory))[:8],
        "preferred_skills": list(set(found_preferred))[:5],
        "programming_languages": list(set(found_languages)),
        "frameworks_libraries": list(set(found_frameworks)),
        "tools_platforms": list(set(found_tools)),
        "educational_requirements": edu,
        "experience_requirements": exp,
        "soft_skills": ["Problem Solving", "Team Collaboration", "Clear Written Communication"],
        "eligibility_restrictions": restrictions,
        "duration_details": None,
        "compensation_details": None
    }

async def extract_job_requirements(title: str, description: str) -> Dict[str, Any]:
    """Extract structured technical requirements using Ollama with deterministic fallback."""
    if not description or len(description.strip()) < 40:
        return fallback_heuristic_extraction(title, description or title)
    
    prompt = f"Job Title: {title}\n\nJob Description:\n{description[:2500]}"
    try:
        response_text = await ollama_client.generate_json(prompt, system_prompt=SYSTEM_EXTRACTION_PROMPT)
        if response_text:
            data = json.loads(response_text)
            # Validate essential fields
            if "mandatory_technical_skills" in data and isinstance(data["mandatory_technical_skills"], list):
                # Ensure fallbacks if fields are empty
                if not data.get("responsibilities"):
                    data["responsibilities"] = [f"Contribute to {title} projects"]
                return data
    except Exception as e:
        logger.warning(f"Ollama structured extraction failed, falling back to heuristics: {e}")
        
    return fallback_heuristic_extraction(title, description)
