import re
from typing import Dict, Any, List, Optional, Tuple
from backend.app.schemas.structured_resume import (
    PersonalInfo,
    EducationEntry,
    SkillCategory,
    ProjectEntry,
    ExperienceEntry,
    CertificationEntry,
    AchievementEntry,
    PublicationEntry,
    BulletPoint,
    StructuredResumeContent,
    generate_stable_id,
)

def extract_braced(text: str, start: int = 0) -> Tuple[str, int]:
    r"""
    Finds the first opening brace '{' at or after start and returns the balanced
    inner content and ending character index.
    """
    start_pos = text.find("{", start)
    if start_pos == -1:
        return "", -1
    depth = 0
    for i in range(start_pos, len(text)):
        if text[i] == "{" and (i == 0 or text[i - 1] != "\\"):
            depth += 1
        elif text[i] == "}" and (i == 0 or text[i - 1] != "\\"):
            depth -= 1
            if depth == 0:
                return text[start_pos + 1:i], i + 1
    return text[start_pos + 1:], len(text)

def clean_latex_text(text: str) -> str:
    r"""
    Strips LaTeX formatting commands, macros, environments, and special character
    escapes while preserving the semantic human-readable text.
    """
    if not text:
        return ""

    # Replace escaped characters
    escapes = [
        (r"\&", "&"),
        (r"\%", "%"),
        (r"\$", "$"),
        (r"\#", "#"),
        (r"\_", "_"),
        (r"\{", "{"),
        (r"\}", "}"),
        (r"\textasciitilde{}", "~"),
        (r"\textasciicircum{}", "^"),
        (r"\textbackslash{}", "\\"),
        (r"\textless{}", "<"),
        (r"\textgreater{}", ">"),
    ]
    for esc, repl in escapes:
        text = text.replace(esc, repl)

    # Unwrap \href{url}{text} -> text
    text = re.sub(r"\\href\{[^}]*\}\{([^}]*)\}", r"\1", text)

    # Iteratively unwrap commands like \kw{...}, \textbf{...}, \textit{...}, etc.
    for _ in range(5):
        text = re.sub(r"\\[a-zA-Z]+\{([^{}]*)\}", r"\1", text)

    # Remove standalone LaTeX commands (e.g. \hfill, \quad, \titlerule, \vspace{...})
    text = re.sub(r"\\vspace\{[^}]*\}", " ", text)
    text = re.sub(r"\\(?:hfill|quad|qquad|titlerule|bigskip|medskip|smallskip|par|bfseries|huge|Huge|large|Large|normalsize|small|footnotesize)", " ", text)
    text = re.sub(r"\\[a-zA-Z]+", " ", text)

    # Clean up double backslashes, remaining braces, and normalize spaces
    text = text.replace("\\\\", " ").replace("{", "").replace("}", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def split_latex_sections(latex_str: str) -> Dict[str, str]:
    r"""
    Parses LaTeX document into a dictionary of normalized section titles and their raw body text.
    Handles \section*{...} and \section{...}.
    """
    parts = re.split(r"\\section\*?\{([^}]+)\}", latex_str)
    sections: Dict[str, str] = {}
    if len(parts) >= 3:
        for i in range(1, len(parts), 2):
            raw_title = parts[i].strip()
            norm_title = clean_latex_text(raw_title).lower()
            body = parts[i + 1].strip()
            # If body has \end{document}, trim it
            if r"\end{document}" in body:
                body = body.split(r"\end{document}")[0].strip()
            sections[norm_title] = body
    return sections

def parse_personal_info(latex_str: str, candidate_dict: Optional[Dict[str, Any]] = None) -> PersonalInfo:
    r"""
    Extracts name and contact information from document header, falling back to CandidateProfile.
    """
    cand = candidate_dict or {}

    # Extract name from header
    name = ""
    name_patterns = [
        r"\{\s*\\(?:huge|Huge)\s*\\bfseries\s*([^}]+)\}",
        r"\\(?:huge|Huge)\s*\\textbf\{([^}]+)\}",
        r"\\textbf\{\s*\\(?:huge|Huge)\s*([^}]+)\}",
        r"\\begin\{center\}\s*\{\s*\\(?:huge|Huge)\s*([^}]+)\}",
        r"\\begin\{center\}\s*\\textbf\{([^}]+)\}",
    ]
    for pat in name_patterns:
        m = re.search(pat, latex_str, re.IGNORECASE)
        if m:
            name = clean_latex_text(m.group(1))
            break
    if not name:
        name = cand.get("name") or cand.get("full_name") or "Candidate"

    # Contact header parsing
    center_m = re.search(r"\\begin\{center\}(.*?)\\end\{center\}", latex_str, re.DOTALL)
    header_chunk = center_m.group(1) if center_m else latex_str[:1200]

    # Email
    email = ""
    email_m = re.search(r"mailto:([\w\.\-\+]+@[\w\.\-]+\.\w+)", header_chunk)
    if email_m:
        email = email_m.group(1).strip()
    else:
        email_direct_m = re.search(r"\b([\w\.\-\+]+@[\w\.\-]+\.\w+)\b", header_chunk)
        if email_direct_m:
            email = email_direct_m.group(1).strip()
        else:
            email = cand.get("email", "")
    if not email or "@" not in email:
        email = cand.get("email") or "candidate@careeros.internal"

    # Phone
    phone = ""
    phone_m = re.search(r"(\+?\d[\d\s\-]{8,}\d)", header_chunk)
    if phone_m:
        phone = phone_m.group(1).strip()
    else:
        phone = cand.get("phone", "")

    # Links
    linkedin = ""
    li_m = re.search(r"(https?://(?:www\.)?linkedin\.com/in/[^}\s\)]+)", header_chunk)
    if li_m:
        linkedin = li_m.group(1).strip()
    else:
        linkedin = cand.get("linkedin_url", "")

    github = ""
    gh_m = re.search(r"(https?://(?:www\.)?github\.com/[^}\s\)]+)", header_chunk)
    if gh_m:
        github = gh_m.group(1).strip()
    else:
        github = cand.get("github_url", "")

    portfolio = ""
    port_m = re.search(r"\\href\{(https?://[^}]+)\}\{(?:Portfolio|Website|Web|Blog)[^}]*\}", header_chunk, re.IGNORECASE)
    if port_m:
        portfolio = port_m.group(1).strip()
    else:
        portfolio = cand.get("portfolio_url", "")

    location = cand.get("location", "")

    return PersonalInfo(
        name=name,
        email=email,
        phone=phone,
        location=location,
        linkedin_url=linkedin,
        github_url=github,
        portfolio_url=portfolio
    )

def parse_summary_section(body: str, candidate_dict: Optional[Dict[str, Any]] = None) -> str:
    r"""Extracts user-authored summary if present, else falls back to candidate headline."""
    cleaned = clean_latex_text(body)
    if cleaned:
        return cleaned
    cand = candidate_dict or {}
    return cand.get("summary") or cand.get("headline") or ""

def parse_skills_section(body: str, candidate_dict: Optional[Dict[str, Any]] = None) -> List[SkillCategory]:
    r"""
    Parses itemized skills categories from LaTeX into SkillCategory models.
    """
    categories: List[SkillCategory] = []
    # Match items formatted as: \item \textbf{Category:} skill1, skill2, ...
    items = re.findall(r"\\item\s+\\textbf\{([^}]+):?\}\s*(.*?)(?=\\item|\Z|\\end\{itemize\})", body, re.DOTALL)
    for cat_name, skill_str in items:
        clean_cat = clean_latex_text(cat_name).rstrip(":")
        clean_skills = [clean_latex_text(s) for s in clean_latex_text(skill_str).split(",") if clean_latex_text(s)]
        if clean_cat and clean_skills:
            categories.append(SkillCategory(category=clean_cat, skills=clean_skills))

    if categories:
        return categories

    # Fallback to candidate profile skills if absent
    cand = candidate_dict or {}
    raw_skills = cand.get("skills", [])
    if isinstance(raw_skills, list) and raw_skills:
        if isinstance(raw_skills[0], dict) and "category" in raw_skills[0]:
            return [
                SkillCategory(
                    category=s.get("category", "Skills"),
                    skills=s.get("skills", [])
                )
                for s in raw_skills
            ]
        elif isinstance(raw_skills[0], str):
            return [SkillCategory(category="Technical Skills", skills=raw_skills)]
    return []

def parse_experience_section(body: str, candidate_dict: Optional[Dict[str, Any]] = None) -> List[ExperienceEntry]:
    r"""
    Extracts experience entries and bullet points from LaTeX.
    Handles \subheading{Title}{Company}{Duration} and standard template patterns.
    """
    entries: List[ExperienceEntry] = []

    # Format 1: \subheading{Title}{Company}{Duration}
    subheading_matches = re.finditer(r"\\subheading\{([^}]+)\}\{([^}]+)\}\{([^}]+)\}(.*?)(?=\\subheading|\Z)", body, re.DOTALL)
    for m in subheading_matches:
        role = clean_latex_text(m.group(1))
        comp = clean_latex_text(m.group(2))
        dur = clean_latex_text(m.group(3))
        entry_body = m.group(4)

        raw_bullets = re.findall(r"\\item\s+(.*?)(?=\\item|\Z|\\end\{itemize\})", entry_body, re.DOTALL)
        bullets = [
            BulletPoint(id=generate_stable_id("bullet"), text=clean_latex_text(b))
            for b in raw_bullets if clean_latex_text(b)
        ]

        entries.append(ExperienceEntry(
            id=generate_stable_id("exp"),
            title=role,
            company=comp,
            duration=dur,
            bullets=bullets
        ))

    if entries:
        return entries

    # Format 2: \textbf{Title} \hfill Duration \\ \textit{Company} \\
    block_splits = re.split(r"(?=\\textbf\{)", body)
    for b in block_splits:
        if not b.strip():
            continue
        first_line = b.split("\n")[0]
        # Title
        t_idx = first_line.find(r"\textbf{")
        if t_idx == -1:
            continue
        title_raw, _ = extract_braced(first_line, t_idx)
        title = clean_latex_text(title_raw)
        if not title:
            continue

        # Company from \textit
        comp_idx = b.find(r"\textit{")
        comp = ""
        if comp_idx != -1:
            comp_raw, _ = extract_braced(b, comp_idx)
            comp = clean_latex_text(comp_raw)

        # Duration
        dur_m = re.search(r"\\hfill\s*([^\\]+)\\", first_line)
        dur = clean_latex_text(dur_m.group(1)) if dur_m else ""

        raw_bullets = re.findall(r"\\item\s+(.*?)(?=\\item|\Z|\\end\{itemize\})", b, re.DOTALL)
        bullets = [
            BulletPoint(id=generate_stable_id("bullet"), text=clean_latex_text(rb))
            for rb in raw_bullets if clean_latex_text(rb)
        ]

        entries.append(ExperienceEntry(
            id=generate_stable_id("exp"),
            title=title,
            company=comp or "Company",
            duration=dur,
            bullets=bullets
        ))

    if entries:
        return entries

    # Fallback to candidate profile experience
    cand = candidate_dict or {}
    cand_exp = cand.get("experience", [])
    result = []
    for exp in cand_exp:
        bullets = [
            BulletPoint(id=generate_stable_id("bullet"), text=str(b))
            for b in exp.get("bullets", [])
        ]
        result.append(ExperienceEntry(
            id=generate_stable_id("exp"),
            title=exp.get("title") or exp.get("role") or "Role",
            company=exp.get("company") or "Company",
            duration=exp.get("duration", ""),
            bullets=bullets
        ))
    return result

def parse_projects_section(body: str, candidate_dict: Optional[Dict[str, Any]] = None) -> List[ProjectEntry]:
    r"""
    Extracts projects, URLs, tech stacks, and bullet points from LaTeX.
    Handles \textbf{\href{url}{Title}} and \textbf{Title} patterns.
    """
    entries: List[ProjectEntry] = []
    blocks = re.split(r"(?=\\textbf\{)", body)

    for pb in blocks:
        if not pb.strip():
            continue
        first_line = pb.split("\n")[0]

        # Extract title and URL
        tb_idx = first_line.find(r"\textbf{")
        if tb_idx == -1:
            continue
        tb_inner, _ = extract_braced(first_line, tb_idx)

        url = ""
        title = ""
        if r"\href{" in tb_inner:
            href_idx = tb_inner.find(r"\href{")
            url_raw, end_href = extract_braced(tb_inner, href_idx)
            title_raw, _ = extract_braced(tb_inner, end_href)
            url = url_raw.strip()
            title = clean_latex_text(title_raw)
        else:
            title = clean_latex_text(tb_inner)

        # Check for URL in [Code] \href
        if not url:
            code_url_m = re.search(r"\\href\{([^}]+)\}\{[^}]*\}", first_line)
            if code_url_m:
                url = code_url_m.group(1).strip()

        if not title:
            continue

        # Tech stack from \textit{...}
        tech_idx = first_line.find(r"\textit{")
        tech_list = []
        if tech_idx != -1:
            tech_raw, _ = extract_braced(first_line, tech_idx)
            clean_tech_str = clean_latex_text(tech_raw)
            tech_list = [t.strip() for t in clean_tech_str.split("|") if t.strip()]

        # Bullets
        raw_bullets = re.findall(r"\\item\s+(.*?)(?=\\item|\Z|\\end\{itemize\})", pb, re.DOTALL)
        bullets = [
            BulletPoint(id=generate_stable_id("bullet"), text=clean_latex_text(b))
            for b in raw_bullets if clean_latex_text(b)
        ]

        entries.append(ProjectEntry(
            id=generate_stable_id("proj"),
            title=title,
            tech_stack=tech_list,
            url=url,
            bullets=bullets
        ))

    if entries:
        return entries

    # Fallback to candidate profile projects
    cand = candidate_dict or {}
    cand_proj = cand.get("projects", [])
    result = []
    for p in cand_proj:
        bullets = [
            BulletPoint(id=generate_stable_id("bullet"), text=str(b))
            for b in p.get("bullets", [])
        ]
        result.append(ProjectEntry(
            id=generate_stable_id("proj"),
            title=p.get("title", "Project"),
            tech_stack=p.get("tech_stack") if isinstance(p.get("tech_stack"), list) else [str(p.get("tech_stack", ""))],
            url=p.get("url", ""),
            bullets=bullets
        ))
    return result

def parse_education_section(body: str, candidate_dict: Optional[Dict[str, Any]] = None) -> List[EducationEntry]:
    r"""
    Extracts education entries from LaTeX \heading{Degree}{College Year} or \textbf{College} patterns.
    """
    entries: List[EducationEntry] = []

    # Pattern A: \heading{Degree}{College \quad Year}
    heading_matches = re.findall(r"\\heading\{([^}]+)\}\{([^}]+)\}", body)
    for deg_raw, place_raw in heading_matches:
        degree = clean_latex_text(deg_raw)
        place_clean = clean_latex_text(place_raw)
        # Check for year in place_clean
        year_m = re.search(r"(\b(?:19|20)\d{2}(?:--\d{2,4})?|\bCompleted \d{4}|\bExpected \d{4})", place_clean)
        year = year_m.group(1) if year_m else None
        college = place_clean.split(year)[0].strip(" ,-\t") if year else place_clean
        entries.append(EducationEntry(
            college=college or place_clean or "University",
            degree=degree or "Degree",
            graduation_year=year
        ))

    if entries:
        return entries

    # Pattern B: \textbf{College} \hfill Year \\ \n Degree \hfill CGPA: ...
    college_matches = re.finditer(r"\\textbf\{([^}]+)\}(?:[^\\]*\\hfill\s*([^\\]+)\\\\)?(?:[^\n]*\n\s*([^\\\n]+))?", body)
    for m in college_matches:
        college = clean_latex_text(m.group(1))
        year = clean_latex_text(m.group(2)) if m.group(2) else None
        deg_line = clean_latex_text(m.group(3)) if m.group(3) else "Degree"
        cgpa_m = re.search(r"CGPA:?\s*([0-9\.]+)", deg_line)
        cgpa = cgpa_m.group(1) if cgpa_m else None
        deg_clean = re.sub(r"CGPA:?.*", "", deg_line).strip(" -|")
        if college:
            entries.append(EducationEntry(
                college=college,
                degree=deg_clean or "Degree",
                graduation_year=year,
                cgpa=cgpa
            ))

    if entries:
        return entries

    # Fallback to candidate profile education
    cand = candidate_dict or {}
    college = cand.get("college", "")
    degree = cand.get("degree", "")
    if college or degree:
        return [
            EducationEntry(
                college=college or "University",
                degree=degree or "Degree",
                graduation_year=str(cand.get("graduation_year", "") or "") or None,
                cgpa=cand.get("cgpa")
            )
        ]
    return []

def parse_certifications_section(body: str, candidate_dict: Optional[Dict[str, Any]] = None) -> List[CertificationEntry]:
    r"""Extracts certification entries from LaTeX items."""
    entries: List[CertificationEntry] = []
    items = re.findall(r"\\item\s+(.*?)(?=\\item|\Z|\\end\{itemize\})", body, re.DOTALL)
    for it in items:
        clean_it = clean_latex_text(it)
        if clean_it:
            entries.append(CertificationEntry(name=clean_it))
    if entries:
        return entries

    cand = candidate_dict or {}
    for c in cand.get("certifications", []):
        entries.append(CertificationEntry(
            name=c.get("name", "") if isinstance(c, dict) else str(c),
            issuer=c.get("issuer", "") if isinstance(c, dict) else ""
        ))
    return entries

def parse_honors_section(body: str, candidate_dict: Optional[Dict[str, Any]] = None) -> List[AchievementEntry]:
    r"""Extracts honors and achievements from LaTeX items."""
    entries: List[AchievementEntry] = []
    items = re.findall(r"\\item\s+(.*?)(?=\\item|\Z|\\end\{itemize\})", body, re.DOTALL)
    for it in items:
        clean_it = clean_latex_text(it)
        if clean_it:
            entries.append(AchievementEntry(title=clean_it))
    if entries:
        return entries

    cand = candidate_dict or {}
    for a in cand.get("achievements", []):
        entries.append(AchievementEntry(
            title=a.get("title", "") if isinstance(a, dict) else str(a)
        ))
    return entries

def parse_publications_section(body: str, candidate_dict: Optional[Dict[str, Any]] = None) -> List[PublicationEntry]:
    r"""Extracts publications from LaTeX items."""
    entries: List[PublicationEntry] = []
    items = re.findall(r"\\item\s+(.*?)(?=\\item|\Z|\\end\{itemize\})", body, re.DOTALL)
    for it in items:
        clean_it = clean_latex_text(it)
        if clean_it:
            entries.append(PublicationEntry(title=clean_it))
    if entries:
        return entries

    cand = candidate_dict or {}
    for p in cand.get("publications", []):
        entries.append(PublicationEntry(
            title=p.get("title", "") if isinstance(p, dict) else str(p)
        ))
    return entries

def parse_latex_to_structured_content(
    latex_str: str,
    candidate_dict: Optional[Dict[str, Any]] = None
) -> StructuredResumeContent:
    r"""
    Parses an existing LaTeX resume into a structured representation without losing
    user customizations, bullets, or sections. Candidate profile is only used to
    fill genuinely absent information.
    """
    cand = candidate_dict or {}
    sections = split_latex_sections(latex_str)

    # 1. Personal Info
    personal_info = parse_personal_info(latex_str, cand)

    # 2. Summary
    summary_body = sections.get("summary") or sections.get("professional summary") or ""
    summary = parse_summary_section(summary_body, cand)

    # 3. Skills
    skills_body = sections.get("technical skills") or sections.get("skills") or ""
    skills = parse_skills_section(skills_body, cand)

    # 4. Experience
    exp_body = sections.get("experience") or sections.get("work experience") or sections.get("employment") or ""
    experience = parse_experience_section(exp_body, cand)

    # 5. Projects
    proj_body = sections.get("projects") or sections.get("key technical projects") or sections.get("technical projects") or ""
    projects = parse_projects_section(proj_body, cand)

    # 6. Education
    edu_body = sections.get("education") or sections.get("academic background") or ""
    education = parse_education_section(edu_body, cand)

    # 7. Certifications
    cert_body = sections.get("certifications") or sections.get("licenses & certifications") or ""
    certifications = parse_certifications_section(cert_body, cand)

    # 8. Honors / Achievements
    honors_body = sections.get("honors & achievements") or sections.get("honors & awards") or sections.get("achievements") or sections.get("awards") or ""
    honors = parse_honors_section(honors_body, cand)

    # 9. Publications
    pub_body = sections.get("publications") or ""
    publications = parse_publications_section(pub_body, cand)

    return StructuredResumeContent(
        personal_info=personal_info,
        summary=summary,
        skills=skills,
        projects=projects,
        experience=experience,
        education=education,
        certifications=certifications,
        honors_awards=honors,
        publications=publications
    )
