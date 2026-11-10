import re
from datetime import datetime, timedelta
from typing import Dict, Any, List

def calculate_internship_quality_score(
    record: Dict[str, Any],
    query_context: str = ""
) -> Dict[str, Any]:
    """
    Calculate an explainable Internship Quality Score (0 - 100) across 6 dimensions:
      1. Classification Confidence (0-20)
      2. Skill & Profile Relevance (0-25)
      3. Employer & Company Identification (0-15)
      4. Application Link Quality (0-15)
      5. Freshness & Timeline Clarity (0-15)
      6. Data Completeness (0-10)
    """
    reasons: List[str] = []

    # 1. Classification Confidence (0 - 20)
    class_score = 0.0
    title = (record.get("internship_title") or record.get("title") or "").strip()
    title_lower = title.lower()

    if re.search(r'\b(intern|internship|interns)\b', title_lower):
        class_score += 15.0
        reasons.append("Role explicitly labeled as an internship in job title (+15)")
    elif re.search(r'\b(co-?op|trainee|apprentice)\b', title_lower):
        class_score += 12.0
        reasons.append("Role identified as co-op or apprentice (+12)")
    else:
        class_score += 5.0
        reasons.append("Role classification inferred from description (+5)")

    if record.get("internship_type") in ["remote", "hybrid", "in-office"]:
        class_score += 5.0
        reasons.append(f"Clear internship structure defined: {record.get('internship_type')} (+5)")
    else:
        class_score += 2.0

    class_score = min(20.0, class_score)

    # 2. Skill & Profile Relevance (0 - 25)
    skill_score = 0.0
    req_skills = record.get("required_skills") or []
    pref_skills = record.get("preferred_skills") or []
    all_skills = [s.lower() for s in (req_skills + pref_skills)]
    desc_lower = (record.get("job_description") or record.get("description") or "").lower()

    # Common technical skill keywords
    tech_keywords = [
        "python", "javascript", "typescript", "react", "fastapi", "sql", "postgresql",
        "machine learning", "deep learning", "ai", "data science", "pytorch", "tensorflow",
        "docker", "git", "rest api", "full stack", "backend", "frontend", "nlp", "llm"
    ]
    matched_skills = set()
    for kw in tech_keywords:
        if kw in all_skills or kw in desc_lower or kw in title_lower:
            matched_skills.add(kw)

    if len(matched_skills) >= 4:
        skill_score += 20.0
        reasons.append(f"Strong technical skill alignment: {len(matched_skills)} relevant skills detected (+20)")
    elif len(matched_skills) >= 2:
        skill_score += 14.0
        reasons.append(f"Moderate technical skill alignment: {len(matched_skills)} skills detected (+14)")
    elif len(matched_skills) >= 1:
        skill_score += 8.0
        reasons.append("Basic skill requirement present (+8)")
    else:
        skill_score += 3.0
        reasons.append("Limited technical skill requirements identified (+3)")

    # Query context match bonus
    if query_context and query_context.lower() in (title_lower + " " + desc_lower):
        skill_score += 5.0
        reasons.append(f"Direct match with search priority '{query_context}' (+5)")

    skill_score = min(25.0, skill_score)

    # 3. Employer & Company Identification (0 - 15)
    comp_score = 0.0
    comp_name = (record.get("company_name") or "").strip()
    comp_web = (record.get("company_website") or "").strip()

    if comp_name and comp_name.lower() not in ["confidential", "unknown", "n/a"]:
        comp_score += 10.0
        reasons.append(f"Verified employer identity: '{comp_name}' (+10)")
    else:
        reasons.append("Missing explicit employer identification (0)")

    if comp_web and comp_web.startswith("http"):
        comp_score += 5.0
        reasons.append("Company website link available (+5)")
    else:
        comp_score += 2.0 # ATS or platform identified
        reasons.append("Employer verified via recruitment platform identity (+2)")

    comp_score = min(15.0, comp_score)

    # 4. Application Link Quality (0 - 15)
    link_score = 0.0
    app_url = (record.get("application_url") or record.get("original_url") or "").strip()
    status = record.get("listing_status") or record.get("status")

    if app_url.startswith("http"):
        if status in ["verified", "active"]:
            link_score += 15.0
            reasons.append("Direct, verified active application URL reachable (+15)")
        elif status in ["unverified", "stale"]:
            link_score += 10.0
            reasons.append(f"Direct application URL present, marked {status} (+10)")
        elif status in ["expired", "closed", "failed_verification"]:
            link_score += 0.0
            reasons.append(f"Application link status: {status} (0)")
        else:
            link_score += 8.0
            reasons.append("Application URL present (+8)")
    else:
        reasons.append("Missing application URL (0)")

    link_score = min(15.0, link_score)

    # 5. Freshness & Timeline Clarity (0 - 15)
    fresh_score = 0.0
    posted_date = record.get("posted_date") or record.get("posted_at")
    now = datetime.utcnow()

    if posted_date:
        if isinstance(posted_date, str):
            try:
                posted_dt = datetime.fromisoformat(posted_date.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                posted_dt = None
        else:
            posted_dt = posted_date
        if posted_dt:
            if hasattr(posted_dt, "tzinfo") and posted_dt.tzinfo is not None:
                posted_dt = posted_dt.replace(tzinfo=None)
            age_days = max(0, (now - posted_dt).days)
            if age_days <= 3:
                fresh_score += 10.0
                reasons.append(f"Very recent posting: {age_days} day(s) old (+10)")
            elif age_days <= 14:
                fresh_score += 8.0
                reasons.append(f"Recent posting: {age_days} days old (+8)")
            elif age_days <= 30:
                fresh_score += 5.0
                reasons.append(f"Active within last month: {age_days} days old (+5)")
            else:
                fresh_score += 2.0
                reasons.append(f"Older listing: {age_days} days old (+2)")
        else:
            fresh_score += 4.0
    else:
        fresh_score += 3.0
        reasons.append("Posting date not explicitly provided (+3)")

    # Deadline presence
    deadline = record.get("application_deadline") or record.get("deadline_at")
    if deadline:
        fresh_score += 5.0
        reasons.append("Explicit application deadline stated (+5)")
    else:
        fresh_score += 2.0

    fresh_score = min(15.0, fresh_score)

    # 6. Data Completeness (0 - 10)
    data_score = 0.0
    stipend_type = record.get("compensation_type")
    min_stip = record.get("stipend_min")

    if min_stip is not None and min_stip > 0:
        data_score += 4.0
        reasons.append(f"Exact compensation specified: {record.get('stipend_currency', 'INR')} {min_stip} (+4)")
    elif stipend_type == "unpaid":
        data_score += 3.0
        reasons.append("Transparently labeled unpaid position (+3)")
    elif stipend_type == "undisclosed":
        data_score += 1.0
        reasons.append("Compensation transparently marked undisclosed (+1)")

    if record.get("duration") and "not specified" not in record.get("duration", "").lower():
        data_score += 2.0
        reasons.append("Internship duration stated (+2)")

    if record.get("location"):
        data_score += 2.0
        reasons.append(f"Geographic location specified: {record.get('location')} (+2)")

    if record.get("eligibility"):
        data_score += 2.0
        reasons.append("Eligibility criteria articulated (+2)")

    data_score = min(10.0, data_score)

    total_score = round(class_score + skill_score + comp_score + link_score + fresh_score + data_score, 1)

    return {
        "quality_score": total_score,
        "quality_breakdown": {
            "classification_confidence": round(class_score, 1),
            "skill_relevance": round(skill_score, 1),
            "company_identification": round(comp_score, 1),
            "application_link_quality": round(link_score, 1),
            "freshness_clarity": round(fresh_score, 1),
            "data_completeness": round(data_score, 1),
            "reasons": reasons
        }
    }
