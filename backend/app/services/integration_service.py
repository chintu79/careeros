import re
import logging
from typing import Dict, Any, List, Optional
import httpx
from bs4 import BeautifulSoup
from backend.app.services.verifier import is_safe_external_url

logger = logging.getLogger(__name__)

async def fetch_github_profile_data(username: str) -> Dict[str, Any]:
    """Fetches public profile and repositories from GitHub API without scraping private pages."""
    clean_username = username.strip().lstrip("@").replace("https://github.com/", "").rstrip("/")
    if not clean_username:
        raise ValueError("Invalid GitHub username")

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "CareerOS-Candidate-Integrator"
    }
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        # Fetch user info
        user_resp = await client.get(f"https://api.github.com/users/{clean_username}", headers=headers)
        if user_resp.status_code == 404:
            raise ValueError(f"GitHub user '{clean_username}' not found.")
        if user_resp.status_code == 403:
            raise ValueError("GitHub API rate limit reached. Please try again later or add token.")
        if user_resp.status_code != 200:
            raise ValueError(f"GitHub API error: HTTP {user_resp.status_code}")
            
        user_data = user_resp.json()
        
        # Fetch repos
        repos_resp = await client.get(
            f"https://api.github.com/users/{clean_username}/repos?sort=updated&per_page=20",
            headers=headers
        )
        repos = repos_resp.json() if repos_resp.status_code == 200 else []
        
    extracted_projects = []
    detected_languages = set()
    detected_topics = set()
    
    for r in repos:
        if r.get("fork"):
            continue # Prioritize original work
        name = r.get("name", "")
        desc = r.get("description") or ""
        lang = r.get("language")
        topics = r.get("topics", [])
        stars = r.get("stargazers_count", 0)
        url = r.get("html_url", "")
        
        if lang:
            detected_languages.add(lang)
        for t in topics:
            detected_topics.add(t)
            
        tech_stack = []
        if lang:
            tech_stack.append(lang)
        tech_stack.extend([t for t in topics if t.lower() != lang.lower()][:4])
        
        extracted_projects.append({
            "title": name.replace("-", " ").title(),
            "description": desc or f"Open source repository focusing on {lang or 'software engineering'}.",
            "tech_stack": tech_stack,
            "stars": stars,
            "url": url,
            "source": "github_public_repo"
        })

    # Sort projects by stars then recency
    extracted_projects.sort(key=lambda x: x["stars"], reverse=True)

    return {
        "connected": True,
        "username": clean_username,
        "name": user_data.get("name") or clean_username,
        "bio": user_data.get("bio") or "",
        "public_repos_count": user_data.get("public_repos", len(repos)),
        "languages_detected": sorted(list(detected_languages)),
        "topics_detected": sorted(list(detected_topics)),
        "projects_discovered": extracted_projects[:6]
    }

async def fetch_portfolio_data(portfolio_url: str) -> Dict[str, Any]:
    """Safely extracts project titles, descriptions, and technologies from a public developer portfolio."""
    url = portfolio_url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    # Enforce strict SSRF protection
    safe, reason = is_safe_external_url(url)
    if not safe:
        raise ValueError(f"SSRF Protection: {reason}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            raise ValueError(f"Failed to fetch portfolio: HTTP {resp.status_code}")
        html = resp.text

    soup = BeautifulSoup(html, "html.parser")
    
    # Extract meta tags
    title_tag = soup.find("title")
    page_title = title_tag.text.strip() if title_tag else "Developer Portfolio"
    
    meta_desc = soup.find("meta", attrs={"name": "description"})
    page_desc = meta_desc["content"].strip() if meta_desc and "content" in meta_desc.attrs else ""
    
    # Extract projects from common portfolio classes
    projects = []
    cards = soup.find_all(lambda tag: tag.name in ["div", "article", "section"] and any(
        kw in " ".join(tag.get("class", [])).lower() for kw in ["project", "card", "portfolio-item", "work-item"]
    ))
    
    for card in cards[:6]:
        h = card.find(["h2", "h3", "h4", "h5"])
        if not h:
            continue
        p_title = h.text.strip()
        p_desc_el = card.find("p")
        p_desc = p_desc_el.text.strip() if p_desc_el else ""
        
        # Look for tech badges or tags
        tech_elements = card.find_all(lambda tag: tag.name in ["span", "li", "badge"] and any(
            kw in " ".join(tag.get("class", [])).lower() for kw in ["tag", "tech", "badge", "pill", "skill"]
        ))
        techs = [t.text.strip() for t in tech_elements if len(t.text.strip()) < 25][:5]
        
        # Link
        link_el = card.find("a", href=True)
        link = link_el["href"] if link_el else ""
        if link and not link.startswith("http"):
            link = f"{url.rstrip('/')}/{link.lstrip('/')}"
            
        if len(p_title) > 2 and len(p_title) < 80:
            projects.append({
                "title": p_title,
                "description": p_desc or "Project showcased on portfolio",
                "tech_stack": techs or ["Web / Full Stack"],
                "url": link,
                "source": "portfolio_website"
            })
            
    return {
        "portfolio_url": url,
        "page_title": page_title,
        "bio_snippet": page_desc,
        "projects_discovered": projects
    }


def parse_resume_file(content_bytes: bytes, filename: str = "") -> Dict[str, Any]:
    """
    Parses resume content (PDF or plaintext) and extracts candidate identity,
    contact info, education, skills, and projects without commiting directly to database.
    """
    import io
    import subprocess
    import tempfile

    raw_text = ""
    is_pdf = filename.lower().endswith(".pdf") or content_bytes.startswith(b"%PDF")

    if is_pdf:
        # Try pypdf first
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(content_bytes))
            pages_text = []
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    pages_text.append(extracted)
            raw_text = "\n".join(pages_text).strip()
        except Exception as e:
            logger.warning("pypdf parsing failed, falling back to pdftotext: %s", e)

        # Fallback to system pdftotext if pypdf was empty or failed
        if not raw_text:
            try:
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
                    tmp.write(content_bytes)
                    tmp.flush()
                    proc = subprocess.run(
                        ["pdftotext", tmp.name, "-"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=10,
                        text=True
                    )
                    if proc.returncode == 0 and proc.stdout:
                        raw_text = proc.stdout.strip()
            except Exception as e:
                logger.warning("pdftotext fallback failed: %s", e)
    else:
        # Plain text / markdown
        try:
            raw_text = content_bytes.decode("utf-8").strip()
        except UnicodeDecodeError:
            raw_text = content_bytes.decode("latin-1", errors="replace").strip()

    if not raw_text:
        raise ValueError("Could not extract any readable text from the provided resume file.")

    # 1. Contact & URLs
    email_match = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', raw_text)
    email = email_match.group(0) if email_match else ""

    phone_match = re.search(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', raw_text)
    phone = phone_match.group(0).strip() if phone_match else ""

    gh_match = re.search(r'github\.com/([a-zA-Z0-9_-]+)', raw_text, re.IGNORECASE)
    github_url = f"https://github.com/{gh_match.group(1)}" if gh_match else ""

    li_match = re.search(r'linkedin\.com/in/([a-zA-Z0-9_-]+)', raw_text, re.IGNORECASE)
    linkedin_url = f"https://linkedin.com/in/{li_match.group(1)}" if li_match else ""

    # Portfolio URL (non-github, non-linkedin)
    portfolio_url = ""
    for url_match in re.finditer(r'https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?', raw_text):
        u = url_match.group(0).rstrip(".,;)")
        if "github.com" not in u and "linkedin.com" not in u and "twitter.com" not in u:
            portfolio_url = u
            break

    # 2. Candidate Name
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    name = ""
    for line in lines[:8]:
        # Exclude lines with email, urls, phone digits, or common header words
        if "@" in line or "http" in line or "github" in line or "linkedin" in line:
            continue
        if any(w in line.lower() for w in ["resume", "curriculum", "vitae", "contact", "summary", "profile", "phone", "email"]):
            continue
        words = line.split()
        if 2 <= len(words) <= 4 and all(re.match(r'^[A-Za-z.\'\-]+$', w) for w in words):
            name = line
            break

    # 3. Education extraction
    college = ""
    degree = ""
    grad_year = None
    cgpa = None

    college_keywords = ["university", "college", "institute", "polytechnic", "academy", "school of engineering", "technology", "iit", "nit", "bits"]
    degree_keywords = [
        ("Bachelor of Technology", "B.Tech"),
        ("Bachelor of Engineering", "B.E."),
        ("Bachelor of Science", "B.S."),
        ("Master of Technology", "M.Tech"),
        ("Master of Science", "M.S."),
        ("B.Tech", "B.Tech"),
        ("B.E.", "B.E."),
        ("B.S.", "B.S."),
        ("M.Tech", "M.Tech"),
        ("BCA", "BCA"),
        ("MCA", "MCA")
    ]

    for line in lines:
        lower_line = line.lower()
        if not college and any(k in lower_line for k in college_keywords):
            # Clean up the line
            if len(line) < 80:
                college = line
        if not degree:
            for dk, dval in degree_keywords:
                if dk.lower() in lower_line:
                    degree = dval
                    break

    # Graduation year
    years = re.findall(r'\b(202[0-9]|201[8-9])\b', raw_text)
    if years:
        grad_year = int(years[-1])

    # CGPA / GPA
    cgpa_match = re.search(r'(?:cgpa|gpa)[\s:]*([0-9](\.[0-9]{1,2})?)', raw_text, re.IGNORECASE)
    if cgpa_match:
        try:
            cgpa = float(cgpa_match.group(1))
        except ValueError:
            pass

    # 4. Technical Skills
    SKILL_CATALOG = {
        "Python": "Language",
        "JavaScript": "Language",
        "TypeScript": "Language",
        "Go": "Language",
        "Rust": "Language",
        "Java": "Language",
        "C++": "Language",
        "C#": "Language",
        "C": "Language",
        "Kotlin": "Language",
        "Swift": "Language",
        "Dart": "Language",
        "SQL": "Language",
        "React": "Framework",
        "Next.js": "Framework",
        "Node.js": "Framework",
        "Express": "Framework",
        "FastAPI": "Framework",
        "Django": "Framework",
        "Flask": "Framework",
        "Spring Boot": "Framework",
        "Flutter": "Framework",
        "Tailwind CSS": "Framework",
        "Vue.js": "Framework",
        "Angular": "Framework",
        "PostgreSQL": "Database",
        "MySQL": "Database",
        "MongoDB": "Database",
        "Redis": "Database",
        "SQLite": "Database",
        "GraphQL": "Architecture",
        "REST APIs": "Architecture",
        "Docker": "DevOps",
        "Kubernetes": "DevOps",
        "AWS": "Cloud",
        "Azure": "Cloud",
        "GCP": "Cloud",
        "Git": "Tooling",
        "Linux": "System",
        "CI/CD": "DevOps",
        "GitHub Actions": "DevOps",
        "TensorFlow": "AI/ML",
        "PyTorch": "AI/ML",
        "Pandas": "AI/ML",
        "NumPy": "AI/ML"
    }

    detected_skills = []
    seen_skills = set()
    for skill_name, category in SKILL_CATALOG.items():
        pattern = rf'(?<![A-Za-z0-9]){re.escape(skill_name)}(?![A-Za-z0-9])'
        if re.search(pattern, raw_text, re.IGNORECASE):
            detected_skills.append({
                "name": skill_name,
                "level": "intermediate",
                "category": category,
                "evidence": f"Extracted from parsed resume ({category})"
            })
            seen_skills.add(skill_name.lower())

    # 5. Projects Extraction
    detected_projects = []
    # Find project section
    project_indices = []
    for i, line in enumerate(lines):
        if re.match(r'^(?:[#*_\-\s]*)(?:projects|key projects|technical projects|academic projects)(?:[:\s]*)$', line, re.IGNORECASE):
            project_indices.append(i)

    if project_indices:
        start_idx = project_indices[0] + 1
        curr_title = ""
        curr_desc = []
        for line in lines[start_idx:start_idx + 35]:
            # If hit another major section, stop
            if re.match(r'^(?:[#*_\-\s]*)(?:education|experience|work experience|skills|certifications|awards|leadership)(?:[:\s]*)$', line, re.IGNORECASE):
                break
            
            # Check if this line looks like a project header (e.g. bold or short title or contains |)
            if (len(line) < 60 and not line.startswith(("-", "•", "*", "–")) and (any(w in line for w in ["|", "-", "–", ":"]) or len(curr_desc) >= 2)):
                if curr_title and curr_desc:
                    proj_text = " ".join(curr_desc)
                    detected_projects.append({
                        "title": curr_title.split("|")[0].split("-")[0].strip(),
                        "description": proj_text[:280],
                        "tech_stack": [s["name"] for s in detected_skills if s["name"].lower() in (curr_title + " " + proj_text).lower()][:4] or ["Full Stack"],
                        "url": "",
                        "source": "resume_parser"
                    })
                curr_title = line
                curr_desc = []
            elif line.startswith(("-", "•", "*", "–")) or curr_title:
                curr_desc.append(line.lstrip("-•*– ").strip())

        if curr_title and curr_desc:
            proj_text = " ".join(curr_desc)
            detected_projects.append({
                "title": curr_title.split("|")[0].split("-")[0].strip(),
                "description": proj_text[:280],
                "tech_stack": [s["name"] for s in detected_skills if s["name"].lower() in (curr_title + " " + proj_text).lower()][:4] or ["Full Stack"],
                "url": "",
                "source": "resume_parser"
            })

    # Return structured draft and detected items without saving to DB
    return {
        "candidate_draft": {
            "name": name,
            "email": email,
            "phone": phone,
            "college": college,
            "degree": degree,
            "graduation_year": grad_year,
            "cgpa": cgpa,
            "github_url": github_url,
            "linkedin_url": linkedin_url,
            "portfolio_url": portfolio_url
        },
        "detected_skills": detected_skills,
        "detected_projects": detected_projects,
        "detected_skills_count": len(detected_skills),
        "detected_projects_count": len(detected_projects),
        "raw_text_snippet": raw_text[:600]
    }

