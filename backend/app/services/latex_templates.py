import re
from typing import Dict, Any, List, Optional

def escape_latex(text: Optional[str]) -> str:
    """Escapes special LaTeX characters for secure, error-free compilation."""
    if not text:
        return ""
    text = str(text)
    conv = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "\\": r"\textbackslash{}",
        "<": r"\textless{}",
        ">": r"\textgreater{}",
    }
    regex = re.compile("|".join(re.escape(str(key)) for key in sorted(conv.keys(), key=lambda item: -len(item))))
    return regex.sub(lambda match: conv[match.group()], text)

TEMPLATES_METADATA = [
    {
        "id": "minimal_professional",
        "name": "Minimal Professional",
        "description": "Ultra-clean single-column typography with conservative ATS margins, subtle line dividers, and high-contrast readability.",
        "tags": ["ATS Standard", "Enterprise", "Clean"],
        "recommended_for": "General Software Engineering, Corporate, Enterprise Roles"
    },
    {
        "id": "modern_technical",
        "name": "Modern Technical",
        "description": "Crisp technical layout with categorized skill matrices, inline repository badges, and prominent GitHub/LinkedIn metadata.",
        "tags": ["Modern", "Tech Stack", "GitHub Links"],
        "recommended_for": "Full Stack Developers, Web Engineers, Startup Roles"
    },
    {
        "id": "software_engineering",
        "name": "Software Engineering",
        "description": "Engineered for backend, systems, and distributed computing roles. Highlights architecture, scale, and database systems.",
        "tags": ["Backend", "Systems", "High Impact"],
        "recommended_for": "Backend Developers, DevOps/Cloud, Distributed Systems"
    },
    {
        "id": "aiml_research",
        "name": "AI/ML Research",
        "description": "Structured for Machine Learning and Data Science roles. Prioritizes model architectures, benchmarks, frameworks, and publications.",
        "tags": ["Machine Learning", "Data Science", "Research"],
        "recommended_for": "AI/ML Engineers, Data Scientists, Deep Learning Researchers"
    },
    {
        "id": "fresher_student",
        "name": "Fresher / Student",
        "description": "Student-centric layout placing Education, CGPA, coursework, competitive programming, and hackathons front and center.",
        "tags": ["Early Career", "University", "Academics"],
        "recommended_for": "University Students, New Grads, Summer Internships"
    },
    {
        "id": "experience_focused",
        "name": "Experience-Focused",
        "description": "Prioritizes chronological professional experience and internships before education and skills, detailing deliverables.",
        "tags": ["Chronological", "Internships", "Production Work"],
        "recommended_for": "Candidates with prior internships or production experience"
    }
]

def list_available_templates() -> List[Dict[str, Any]]:
    return TEMPLATES_METADATA

def _extract_profile_fields(profile_data: Dict[str, Any]) -> Dict[str, Any]:
    # Support structured format (personal_info dict) or legacy flat format
    if "personal_info" in profile_data and isinstance(profile_data["personal_info"], dict):
        pi = profile_data["personal_info"]
        name = escape_latex(pi.get("name", "")).strip()
        email = escape_latex(pi.get("email", "")).strip()
        phone = escape_latex(pi.get("phone", "")).strip()
        location = escape_latex(pi.get("location", "")).strip()
        github = escape_latex(pi.get("github_url", "")).strip()
        linkedin = escape_latex(pi.get("linkedin_url", "")).strip()
        portfolio = escape_latex(pi.get("portfolio_url", "")).strip()
    else:
        name = escape_latex(profile_data.get("name", "")).strip()
        email = escape_latex(profile_data.get("email", "")).strip()
        phone = escape_latex(profile_data.get("phone", "")).strip()
        location = escape_latex(profile_data.get("location", "")).strip()
        github = escape_latex(profile_data.get("github_url", "")).strip()
        linkedin = escape_latex(profile_data.get("linkedin_url", "")).strip()
        portfolio = escape_latex(profile_data.get("portfolio_url", "")).strip()

    summary = escape_latex(profile_data.get("summary", "")).strip()

    # Skills categorization: support SkillCategory list, flat skill dicts, or strings
    skills_raw = profile_data.get("skills", []) or []
    languages, frameworks, tools, concepts = [], [], [], []
    for s in skills_raw:
        if isinstance(s, dict) and "category" in s and "skills" in s:
            # SkillCategory structure: {"category": "Languages", "skills": ["Python", "C++"]}
            cat_name = str(s.get("category", "")).lower()
            cat_skills = [escape_latex(str(item).strip()) for item in s.get("skills", []) if str(item).strip()]
            if any(k in cat_name for k in ["lang", "language"]):
                languages.extend(cat_skills)
            elif any(k in cat_name for k in ["framework", "lib", "frontend", "backend", "web"]):
                frameworks.extend(cat_skills)
            elif any(k in cat_name for k in ["tool", "platform", "cloud", "devops", "db", "database"]):
                tools.extend(cat_skills)
            else:
                concepts.extend(cat_skills)
            continue

        s_name = s.get("name", "") if isinstance(s, dict) else str(s)
        if not s_name:
            continue
        s_cat = (s.get("category", "") if isinstance(s, dict) else "").lower()
        if any(k in s_cat for k in ["lang", "language"]):
            languages.append(escape_latex(s_name))
        elif any(k in s_cat for k in ["framework", "lib", "frontend", "backend", "web"]):
            frameworks.append(escape_latex(s_name))
        elif any(k in s_cat for k in ["tool", "platform", "cloud", "devops", "db", "database"]):
            tools.append(escape_latex(s_name))
        elif s_cat:
            concepts.append(escape_latex(s_name))
        else:
            tools.append(escape_latex(s_name))

    # Education entries: support structured list or legacy flat fields
    education_raw = profile_data.get("education", [])
    if isinstance(education_raw, list) and education_raw:
        edu_entries = education_raw
    elif profile_data.get("college") or profile_data.get("degree"):
        edu_entries = [{
            "college": profile_data.get("college", ""),
            "degree": profile_data.get("degree", ""),
            "graduation_year": profile_data.get("graduation_year", ""),
            "cgpa": profile_data.get("cgpa")
        }]
    else:
        edu_entries = []

    degree = escape_latex(profile_data.get("degree", "")).strip()
    college = escape_latex(profile_data.get("college", "")).strip()
    grad_year = escape_latex(str(profile_data.get("graduation_year", "") or "")).strip()
    cgpa_val = profile_data.get("cgpa")
    cgpa = escape_latex(str(cgpa_val) if cgpa_val is not None and str(cgpa_val).strip() else "").strip()
    
    experiences = profile_data.get("experience", []) or profile_data.get("experiences", []) or []
    projects = profile_data.get("projects", []) or []
    certs = profile_data.get("certifications", []) or []
    achievements = profile_data.get("achievements", []) or []
    publications = profile_data.get("publications", []) or []
    additional_links = profile_data.get("additional_links", []) or []
    page_size = profile_data.get("page_size") or (profile_data.get("metadata") or {}).get("page_size") or "letter"
    
    return {
        "name": name,
        "email": email,
        "phone": phone,
        "location": location,
        "github": github,
        "linkedin": linkedin,
        "portfolio": portfolio,
        "summary": summary,
        "languages": ", ".join(dict.fromkeys(languages)),
        "frameworks": ", ".join(dict.fromkeys(frameworks)),
        "tools": ", ".join(dict.fromkeys(tools)),
        "concepts": ", ".join(dict.fromkeys(concepts)),
        "education_entries": edu_entries,
        "degree": degree,
        "college": college,
        "grad_year": grad_year,
        "cgpa": cgpa,
        "experiences": experiences,
        "projects": projects,
        "certifications": certs,
        "achievements": achievements,
        "publications": publications,
        "additional_links": additional_links,
        "page_size": page_size
    }

def _build_latex_preamble(margin: str = "0.6in", font_size: str = "10pt", page_size: str = "letter") -> str:
    norm_page = str(page_size).lower().strip()
    paper_opt = "a4paper" if norm_page in ("a4", "a4paper") else "letterpaper"
    return f"""\\documentclass[{font_size},{paper_opt}]{{article}}
\\usepackage[utf8]{{inputenc}}
\\usepackage[margin={margin}]{{geometry}}
\\usepackage{{hyperref}}
\\usepackage{{enumitem}}
\\usepackage[nobottomtitles*]{{titlesec}}
\\usepackage{{parskip}}
\\usepackage{{microtype}}

\\renewcommand{{\\bottomtitlespace}}{{0.8in}}
\\raggedbottom

\\hypersetup{{
    colorlinks=true,
    linkcolor=black,
    filecolor=black,
    urlcolor=blue,
}}

\\titleformat{{\\section}}{{\\large\\bfseries\\uppercase}}{{}}{{0em}}{{}}[\\titlerule]
\\titlespacing*{{\\section}}{{0pt}}{{5pt plus 1pt minus 1pt}}{{2.5pt plus 1pt minus 1pt}}

\\pagestyle{{empty}}
"""

def _render_summary(d: Dict[str, Any]) -> str:
    summary = d.get("summary", "")
    if not summary:
        return ""
    return f"""\\section*{{Professional Summary}}
{summary}
\\vspace{{3pt}}
"""

def _render_education(d: Dict[str, Any]) -> str:
    entries = d.get("education_entries", [])
    if not entries:
        college = d.get("college", "")
        degree = d.get("degree", "")
        grad_year = d.get("grad_year", "")
        cgpa = d.get("cgpa", "")
        if not college and not degree:
            return ""
        entries = [{"college": college, "degree": degree, "graduation_year": grad_year, "cgpa": cgpa}]

    blocks = []
    for edu in entries:
        college = escape_latex(edu.get("college", "")).strip()
        degree = escape_latex(edu.get("degree", "")).strip()
        grad_year = escape_latex(str(edu.get("graduation_year", "") or "")).strip()
        cgpa_val = edu.get("cgpa")
        cgpa = escape_latex(str(cgpa_val) if cgpa_val is not None and str(cgpa_val).strip() else "").strip()
        if not college and not degree:
            continue

        line1_parts = []
        if college:
            line1_parts.append(f"\\textbf{{{college}}}")
        if grad_year:
            line1 = f"{line1_parts[0]} \\hfill Expected {grad_year} \\\\" if line1_parts else f"Expected {grad_year} \\\\"
        elif line1_parts:
            line1 = f"{line1_parts[0]} \\\\"
        else:
            line1 = ""

        line2_parts = []
        if degree:
            line2_parts.append(degree)
        if cgpa:
            line2 = f"{line2_parts[0]} \\hfill CGPA: {cgpa} / 10.0 \\\\" if line2_parts else f"CGPA: {cgpa} / 10.0 \\\\"
        elif line2_parts:
            line2 = f"{line2_parts[0]} \\\\"
        else:
            line2 = ""

        block = "\n".join([l for l in [line1, line2] if l])
        if block:
            blocks.append(block)

    if not blocks:
        return ""
    return f"""\\section*{{Education}}
{"\\vspace{3pt}\n".join(blocks)}
\\vspace{{2pt}}
"""

def _render_skills(d: Dict[str, Any], include_concepts: bool = True) -> str:
    items = []
    if d.get("languages"):
        items.append(f"  \\item \\textbf{{Languages:}} {d['languages']}")
    if d.get("frameworks"):
        items.append(f"  \\item \\textbf{{Frameworks \\& Libraries:}} {d['frameworks']}")
    if d.get("tools"):
        items.append(f"  \\item \\textbf{{Tools \\& Platforms:}} {d['tools']}")
    if include_concepts and d.get("concepts"):
        items.append(f"  \\item \\textbf{{Core Competencies:}} {d['concepts']}")
    if not items:
        return ""
    return f"""\\section*{{Technical Skills}}
\\begin{{itemize}}[leftmargin=12pt, topsep=2pt, itemsep=2pt]
{chr(10).join(items)}
\\end{{itemize}}
\\vspace{{2pt}}
"""

def _render_experience(d: Dict[str, Any]) -> str:
    exps = d.get("experiences", [])
    if not exps:
        return ""
    body = "\\section*{Experience}\n"
    rendered_any = False
    for exp in exps:
        t = escape_latex(exp.get("title", ""))
        c = escape_latex(exp.get("company", ""))
        dur = escape_latex(exp.get("duration", ""))
        desc = escape_latex(exp.get("description", ""))
        dur_str = f"\\hfill {dur}" if dur else ""
        head = f"\\textbf{{{t}}} {dur_str} \\\\\n" if t else ""
        comp = f"\\textit{{{c}}} \\\\\n" if c else ""
        
        # Support multiple bullets or single description
        bullets = exp.get("bullets", [])
        bullet_items = []
        if bullets:
            for b in bullets:
                b_text = b.get("text", "") if isinstance(b, dict) else str(b)
                b_clean = escape_latex(b_text).strip()
                if b_clean:
                    bullet_items.append(f"  \\item {b_clean}")
        elif desc:
            bullet_items.append(f"  \\item {desc}")

        if not head and not comp and not bullet_items:
            continue

        rendered_any = True
        desc_line = f"\\begin{{itemize}}[leftmargin=12pt, topsep=2pt, itemsep=1pt]\n{chr(10).join(bullet_items)}\n\\end{{itemize}}\n" if bullet_items else ""
        body += f"""{head}{comp}\\vspace{{-4pt}}
{desc_line}\\vspace{{3pt}}
"""
    return body if rendered_any else ""

def _render_projects(d: Dict[str, Any], title: str = "Key Technical Projects") -> str:
    projs = d.get("projects", [])
    if not projs:
        return ""
    body = f"\\section*{{{title}}}\n"
    rendered_any = False
    for p in projs:
        p_title = escape_latex(p.get("title", ""))
        tech_list = p.get("tech_stack", [])
        tech = escape_latex(", ".join(tech_list) if isinstance(tech_list, list) else str(tech_list))
        desc = escape_latex(p.get("description", ""))
        url = escape_latex(p.get("url", ""))
        link_str = f"\\hfill \\href{{{url}}}{{[Code]}}" if url else ""
        tech_str = f"| \\textit{{{tech}}}" if tech else ""
        
        # Support multiple bullets or single description
        bullets = p.get("bullets", [])
        bullet_items = []
        if bullets:
            for b in bullets:
                b_text = b.get("text", "") if isinstance(b, dict) else str(b)
                b_clean = escape_latex(b_text).strip()
                if b_clean:
                    bullet_items.append(f"  \\item {b_clean}")
        elif desc:
            bullet_items.append(f"  \\item {desc}")

        if not p_title and not tech and not bullet_items:
            continue

        rendered_any = True
        desc_line = f"\\begin{{itemize}}[leftmargin=12pt, topsep=2pt, itemsep=1pt]\n{chr(10).join(bullet_items)}\n\\end{{itemize}}\n" if bullet_items else ""
        body += f"""\\textbf{{{p_title}}} {tech_str} {link_str} \\\\
\\vspace{{-4pt}}
{desc_line}\\vspace{{3pt}}
"""
    return body if rendered_any else ""

def _render_certifications(d: Dict[str, Any]) -> str:
    certs = d.get("certifications", [])
    if not certs:
        return ""
    items = []
    for cert in certs:
        c_name = escape_latex(cert.get("name", "")).strip()
        if not c_name:
            continue
        c_issuer = escape_latex(cert.get("issuer", "")).strip()
        c_year = escape_latex(str(cert.get("year", "") or "")).strip()
        issuer_str = f" -- {c_issuer}" if c_issuer else ""
        year_str = f" ({c_year})" if c_year else ""
        items.append(f"  \\item \\textbf{{{c_name}}}{issuer_str}{year_str}")
    if not items:
        return ""
    return f"\\section*{{Certifications}}\n\\begin{{itemize}}[leftmargin=12pt, topsep=2pt, itemsep=1pt]\n" + "\n".join(items) + "\n\\end{itemize}\n\\vspace{3pt}\n"

def _render_achievements(d: Dict[str, Any]) -> str:
    achs = d.get("achievements", [])
    if not achs:
        return ""
    items = []
    for ach in achs:
        a_title = escape_latex(ach.get("title", "")).strip()
        if not a_title:
            continue
        a_org = escape_latex(ach.get("organization", "")).strip()
        a_year = escape_latex(str(ach.get("year", "") or "")).strip()
        org_str = f" -- {a_org}" if a_org else ""
        year_str = f" ({a_year})" if a_year else ""
        items.append(f"  \\item \\textbf{{{a_title}}}{org_str}{year_str}")
    if not items:
        return ""
    return f"\\section*{{Honors \\& Achievements}}\n\\begin{{itemize}}[leftmargin=12pt, topsep=2pt, itemsep=1pt]\n" + "\n".join(items) + "\n\\end{itemize}\n\\vspace{3pt}\n"

def _render_publications(d: Dict[str, Any]) -> str:
    pubs = d.get("publications", [])
    if not pubs:
        return ""
    items = []
    for pub in pubs:
        title = escape_latex(pub.get("title", "")).strip()
        if not title:
            continue
        venue = escape_latex(pub.get("venue", "")).strip()
        year = escape_latex(str(pub.get("year", "") or "")).strip()
        url = escape_latex(pub.get("url", "")).strip()
        venue_str = f" -- \\textit{{{venue}}}" if venue else ""
        year_str = f" ({year})" if year else ""
        link_str = f" \\hfill \\href{{{url}}}{{[Paper]}}" if url else ""
        items.append(f"  \\item \\textbf{{{title}}}{venue_str}{year_str}{link_str}")
    if not items:
        return ""
    return f"\\section*{{Publications}}\n\\begin{{itemize}}[leftmargin=12pt, topsep=2pt, itemsep=1pt]\n" + "\n".join(items) + "\n\\end{itemize}\n\\vspace{3pt}\n"

def _render_header_block(d: Dict[str, Any], subtitle: str = "") -> str:
    name = d.get("name", "")
    lines = []
    if name:
        lines.append(f"{{\\Huge \\textbf{{{name}}}}}")
    if subtitle:
        lines.append(f"\\textbf{{{subtitle}}}")
        
    line1 = []
    if d.get("location"):
        line1.append(d["location"])
    if d.get("phone"):
        line1.append(d["phone"])
    if d.get("email"):
        line1.append(f"\\href{{mailto:{d['email']}}}{{{d['email']}}}")
    if line1:
        lines.append(" $\\cdot$ ".join(line1))
        
    line2 = []
    if d.get("github"):
        line2.append(f"\\href{{{d['github']}}}{{GitHub}}")
    if d.get("linkedin"):
        line2.append(f"\\href{{{d['linkedin']}}}{{LinkedIn}}")
    if d.get("portfolio"):
        line2.append(f"\\href{{{d['portfolio']}}}{{Portfolio}}")
    if line2:
        lines.append(" $\\cdot$ ".join(line2))
        
    if not lines:
        return ""
        
    formatted = " \\\\[2pt]\n  ".join(lines)
    return f"""\\begin{{center}}
  {formatted}
\\end{{center}}
\\vspace{{-4pt}}
"""

# ================= Template Implementations =================

def _template_minimal_professional(d: Dict[str, Any]) -> str:
    preamble = _build_latex_preamble(margin="0.6in", font_size="10pt", page_size=d.get("page_size", "letter"))
    header = _render_header_block(d)
    body = "\n".join([s for s in [
        header,
        _render_summary(d),
        _render_education(d),
        _render_skills(d),
        _render_experience(d),
        _render_projects(d, "Technical Projects"),
        _render_certifications(d),
        _render_achievements(d),
        _render_publications(d)
    ] if s])
    return f"""{preamble}
\\begin{{document}}
{body}
\\end{{document}}
"""

def _template_modern_technical(d: Dict[str, Any]) -> str:
    preamble = _build_latex_preamble(margin="0.55in", font_size="10pt", page_size=d.get("page_size", "letter"))
    header = _render_header_block(d)
    body = "\n".join([s for s in [
        header,
        _render_summary(d),
        _render_skills(d, include_concepts=True),
        _render_projects(d, "Featured Systems \\& Applications"),
        _render_experience(d),
        _render_education(d),
        _render_certifications(d),
        _render_achievements(d),
        _render_publications(d)
    ] if s])
    return f"""{preamble}
\\begin{{document}}
{body}
\\end{{document}}
"""

def _template_software_engineering(d: Dict[str, Any]) -> str:
    preamble = _build_latex_preamble(margin="0.55in", font_size="10pt", page_size=d.get("page_size", "letter"))
    header = _render_header_block(d, subtitle="Software Engineering Candidate")
    body = "\n".join([s for s in [
        header,
        _render_summary(d),
        _render_skills(d),
        _render_experience(d),
        _render_projects(d, "System Architecture \\& Backend Engineering"),
        _render_education(d),
        _render_certifications(d),
        _render_achievements(d),
        _render_publications(d)
    ] if s])
    return f"""{preamble}
\\begin{{document}}
{body}
\\end{{document}}
"""

def _template_aiml_research(d: Dict[str, Any]) -> str:
    preamble = _build_latex_preamble(margin="0.6in", font_size="10pt", page_size=d.get("page_size", "letter"))
    header = _render_header_block(d, subtitle="AI / Machine Learning Researcher \\& Engineer")
    body = "\n".join([s for s in [
        header,
        _render_summary(d),
        _render_education(d),
        _render_skills(d),
        _render_projects(d, "AI/ML Models, Pipelines \\& Research Projects"),
        _render_publications(d),
        _render_experience(d),
        _render_certifications(d),
        _render_achievements(d)
    ] if s])
    return f"""{preamble}
\\begin{{document}}
{body}
\\end{{document}}
"""

def _template_fresher_student(d: Dict[str, Any]) -> str:
    preamble = _build_latex_preamble(margin="0.6in", font_size="10pt", page_size=d.get("page_size", "letter"))
    sub = f"{d['degree']} $\\cdot$ {d['college']}" if (d.get('degree') and d.get('college')) else (d.get('degree') or d.get('college') or "")
    header = _render_header_block(d, subtitle=sub)
    body = "\n".join([s for s in [
        header,
        _render_summary(d),
        _render_education(d),
        _render_skills(d),
        _render_projects(d, "Academic \\& Independent Projects"),
        _render_achievements(d),
        _render_certifications(d),
        _render_experience(d),
        _render_publications(d)
    ] if s])
    return f"""{preamble}
\\begin{{document}}
{body}
\\end{{document}}
"""

def _template_experience_focused(d: Dict[str, Any]) -> str:
    preamble = _build_latex_preamble(margin="0.6in", font_size="10pt", page_size=d.get("page_size", "letter"))
    header = _render_header_block(d)
    body = "\n".join([s for s in [
        header,
        _render_summary(d),
        _render_experience(d),
        _render_projects(d, "Key Technical Deliverables"),
        _render_skills(d),
        _render_education(d),
        _render_certifications(d),
        _render_achievements(d),
        _render_publications(d)
    ] if s])
    return f"""{preamble}
\\begin{{document}}
{body}
\\end{{document}}
"""

TEMPLATE_REGISTRY = {
    "minimal_professional": _template_minimal_professional,
    "modern_technical": _template_modern_technical,
    "software_engineering": _template_software_engineering,
    "aiml_research": _template_aiml_research,
    "fresher_student": _template_fresher_student,
    "experience_focused": _template_experience_focused,
    # Aliases for backwards compatibility
    "ats_modern": _template_modern_technical,
    "ats_classic": _template_minimal_professional,
    "ats_compact": _template_software_engineering
}

def build_latex_template(
    profile_data: Dict[str, Any],
    template_id: str = "minimal_professional",
    page_size: Optional[str] = None
) -> str:
    """Builds an ATS-friendly LaTeX resume according to the chosen template and page size."""
    clean_data = _extract_profile_fields(profile_data)
    if page_size:
        clean_data["page_size"] = page_size
    builder = TEMPLATE_REGISTRY.get(template_id, _template_minimal_professional)
    return builder(clean_data)

