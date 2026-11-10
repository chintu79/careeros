import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.app.services.intelligence_cache import intelligence_cache
from backend.app.services.context_retriever import (
    get_candidate_context,
    get_opportunity_context,
    get_pipeline_context,
    get_interview_history_context,
    get_market_skills_context,
    search_opportunities_vector
)
from backend.app.ai.ollama_client import ollama_client

logger = logging.getLogger(__name__)

# Truth Layer Labels
TRUTH_DB = "[Verified Database Record]"
TRUTH_EXTERNAL = "[Extracted External Information]"
TRUTH_AI = "[AI Strategic Recommendation]"
TRUTH_UNKNOWN = "[Unknown / Missing Information]"


def _create_truth_layers(
    verified_db: List[str],
    extracted_ext: List[str],
    strategic_ai: List[str],
    unknown_missing: List[str]
) -> Dict[str, List[str]]:
    return {
        "verified_database": verified_db,
        "extracted_external": extracted_ext,
        "strategic_recommendations": strategic_ai,
        "unknown_missing": unknown_missing
    }


async def run_job_matching_intelligence(
    opportunity_id: int,
    db: Session,
    use_cache: bool = True,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Workflow 1: Job Matching Intelligence
    Deep-dives into a specific opportunity vs the candidate profile with verified evidence.
    """
    cand = get_candidate_context(db, scope="full", user_id=user_id)
    cand_id = cand.get("id", 1)
    cache_key = f"job_matching:{opportunity_id}:{cand_id}"

    if use_cache:
        cached = intelligence_cache.get(cache_key)
        if cached:
            return cached

    opp = get_opportunity_context(db, opportunity_id, user_id=user_id)
    if not opp:
        return {
            "workflow": "job_matching",
            "error": f"Opportunity {opportunity_id} not found in database.",
            "truth_layers": _create_truth_layers([], [], [], [f"Opportunity ID {opportunity_id} does not exist in CareerOS."])
        }

    # Evaluate skill overlap
    cand_skills_map = {
        s["name"].lower(): s for s in cand.get("verified_skills", [])
    }
    
    req_skills = opp.get("required_skills") or []
    pref_skills = opp.get("preferred_skills") or []
    all_job_skills = list(dict.fromkeys(req_skills + pref_skills))

    matching_skills = []
    missing_skills = []

    for js in all_job_skills:
        js_clean = js.strip()
        js_lower = js_clean.lower()
        if js_lower in cand_skills_map:
            cs = cand_skills_map[js_lower]
            matching_skills.append({
                "name": js_clean,
                "candidate_level": cs.get("level", "intermediate"),
                "evidence": cs.get("evidence", "Verified in Master Candidate Profile")
            })
        else:
            missing_skills.append(js_clean)

    # Evaluate project alignment
    cand_projects = cand.get("verified_projects", [])
    relevant_projects = []
    for p in cand_projects:
        stack = [tech.lower() for tech in p.get("tech_stack", [])]
        overlap = [js for js in all_job_skills if js.lower() in stack]
        if overlap or any(kw in p.get("description", "").lower() for kw in [opp["title"].lower(), "backend", "full stack", "api", "ai"]):
            relevant_projects.append({
                "title": p.get("title"),
                "overlapping_skills": overlap,
                "description": p.get("description")
            })

    # Evaluate preference fit
    prefs = cand.get("preferences", {})
    workplace_types = prefs.get("workplace_types", ["remote", "hybrid", "onsite"])
    opp_workplace = opp.get("workplace_type") or "unspecified"
    workplace_match = opp_workplace.lower() in [w.lower() for w in workplace_types] or opp_workplace == "unspecified"
    
    min_stipend_pref = prefs.get("min_stipend") or 0
    opp_min_stipend = opp.get("min_stipend") or 0
    stipend_satisfied = True
    if min_stipend_pref > 0:
        if opp.get("stipend_text") and "unpaid" in opp["stipend_text"].lower():
            stipend_satisfied = False
        elif opp_min_stipend > 0 and opp_min_stipend < min_stipend_pref:
            stipend_satisfied = False

    # Build Grounded Truth Layers
    verified_db = [
        f"Candidate: {cand.get('name')} ({cand.get('degree')} at {cand.get('college')}, Grad: {cand.get('graduation_year')})",
        f"Verified Candidate Skills: {len(cand.get('verified_skills', []))} documented technical skills with evidence in Master Profile.",
        f"Matching Verified Skills: {', '.join([m['name'] for m in matching_skills]) or 'None identified'}",
        f"Candidate Portfolio/GitHub: {cand.get('github_url') or 'Configured in profile'}",
        f"Stored Opportunity Record: ID #{opp['id']} - Status '{opp['status']}', Match Score {opp['match_score']}%"
    ]

    extracted_ext = [
        f"Employer Job Posting: '{opp['title']}' at '{opp['company_name']}'",
        f"Role Location & Type: {opp['location']} ({opp['workplace_type']})",
        f"Extracted Requirements: {len(all_job_skills)} skills ({', '.join(all_job_skills[:6]) if all_job_skills else 'General'})",
        f"Extracted Compensation: {opp['stipend_text']} ({opp.get('currency', 'INR')})"
    ]

    strategic_ai = [
        f"Target Opportunity Fit: {'Strong Alignment' if opp['match_score'] >= 75 else 'Moderate Match / Reach Opportunity'} ({round(opp['match_score'])}% match score).",
        f"Recommended Project to Highlight: '{relevant_projects[0]['title'] if relevant_projects else cand_projects[0]['title'] if cand_projects else 'Core Systems Project'}' directly demonstrates relevant capabilities.",
        f"Workplace Preference Compatibility: {'Fully compatible with candidate preferences' if workplace_match else 'Location/type may require relocation or policy adjustment'}."
    ]

    unknown_missing = []
    if not opp.get("deadline_at"):
        unknown_missing.append("Application deadline is undisclosed in the job posting.")
    if opp.get("stipend_text") == "Undisclosed" or not opp.get("min_stipend"):
        unknown_missing.append("Exact compensation figures are undisclosed by the employer.")
    if missing_skills:
        unknown_missing.append(f"Candidate profile currently lacks verified experience in: {', '.join(missing_skills)} (required/preferred by job description).")
    if not opp.get("company_website"):
        unknown_missing.append("Company website domain was not provided in listing metadata.")

    # Try LLM generation for enhanced strategic reasoning
    summary_text = None
    try:
        prompt = f"""Compare candidate to job posting.
Candidate Profile:
- Name: {cand.get('name')}
- Degree: {cand.get('degree')} ({cand.get('college')})
- Verified Skills: {[s['name'] for s in cand.get('verified_skills', [])]}
- Top Projects: {[p['title'] for p in cand_projects[:3]]}

Job Posting:
- Title: {opp['title']}
- Company: {opp['company_name']}
- Required Skills: {all_job_skills}
- Location: {opp['location']} ({opp['workplace_type']})
- Description: {opp.get('description', '')[:1000]}

Provide a 2-paragraph professional match analysis. Explain strengths and missing skills objectively. Return JSON with 'analysis'."""
        
        raw = await asyncio.wait_for(
            ollama_client.generate_json(prompt=prompt, system_prompt="You are a senior technical hiring analyst. Ground answers strictly in provided facts."),
            timeout=15.0
        )
        if raw:
            parsed = json.loads(raw)
            summary_text = parsed.get("analysis")
    except Exception as e:
        logger.info(f"Ollama deep matching skipped or timed out, using deterministic synthesis: {e}")

    if not summary_text:
        summary_text = (
            f"**Evaluation for {opp['title']} at {opp['company_name']}**\n\n"
            f"Your profile demonstrates a **{round(opp['match_score'])}% alignment** with this position. "
            f"You possess {len(matching_skills)} of {len(all_job_skills)} core technical requirements, including "
            f"**{', '.join([m['name'] for m in matching_skills[:4]]) if matching_skills else 'fundamental CS concepts'}**. "
            f"{'Your verified project experience in ' + relevant_projects[0]['title'] + ' directly reinforces your application.' if relevant_projects else ''}\n\n"
            f"**Areas to address:** The employer lists **{', '.join(missing_skills[:3]) if missing_skills else 'no additional unverified skills'}**, "
            f"which you should be prepared to discuss or demonstrate foundational knowledge in."
        )

    result = {
        "workflow": "job_matching",
        "title": f"Job Match Intelligence: {opp['title']} @ {opp['company_name']}",
        "summary": summary_text,
        "metrics": {
            "match_score": opp["match_score"],
            "matching_skills_count": len(matching_skills),
            "missing_skills_count": len(missing_skills),
            "total_job_skills": len(all_job_skills),
            "workplace_match": workplace_match,
            "stipend_satisfied": stipend_satisfied
        },
        "details": {
            "opportunity": {
                "id": opp["id"],
                "title": opp["title"],
                "company_name": opp["company_name"],
                "location": opp["location"],
                "workplace_type": opp["workplace_type"],
                "stipend_text": opp["stipend_text"],
                "application_url": opp["application_url"]
            },
            "matching_skills": matching_skills,
            "missing_skills": missing_skills,
            "relevant_projects": relevant_projects
        },
        "truth_layers": _create_truth_layers(verified_db, extracted_ext, strategic_ai, unknown_missing)
    }

    intelligence_cache.set(cache_key, result, ttl=600)
    return result


async def run_resume_intelligence(
    opportunity_id: int,
    db: Session,
    use_cache: bool = True,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Workflow 2: Resume Intelligence
    Synthesizes job-specific ATS tailoring recommendations, highlighting candidate's verified projects and skills.
    """
    cand = get_candidate_context(db, scope="full", user_id=user_id)
    cand_id = cand.get("id", 1)
    cache_key = f"resume_intel:{opportunity_id}:{cand_id}"

    if use_cache:
        cached = intelligence_cache.get(cache_key)
        if cached:
            return cached

    opp = get_opportunity_context(db, opportunity_id, user_id=user_id)
    if not opp:
        return {
            "workflow": "resume_intelligence",
            "error": f"Opportunity {opportunity_id} not found in database.",
            "truth_layers": _create_truth_layers([], [], [], [f"Opportunity ID {opportunity_id} does not exist."])
        }

    cand_projects = cand.get("verified_projects", [])
    cand_skills = cand.get("verified_skills", [])
    job_skills = (opp.get("required_skills") or []) + (opp.get("preferred_skills") or [])
    job_skills_lower = [s.lower() for s in job_skills]

    # Rank candidate projects by tech overlap
    scored_projects = []
    for p in cand_projects:
        stack = p.get("tech_stack", [])
        overlap = [tech for tech in stack if tech.lower() in job_skills_lower]
        score = len(overlap) * 10
        if any(term in p.get("title", "").lower() for term in ["engine", "system", "agent", "platform", "cloud"]):
            score += 5
        scored_projects.append({
            "title": p.get("title"),
            "tech_stack": stack,
            "overlap_keywords": overlap,
            "score": score,
            "description": p.get("description", ""),
            "url": p.get("url", "")
        })
    scored_projects.sort(key=lambda x: x["score"], reverse=True)
    top_projects = scored_projects[:3]

    # Suggest ATS keywords strictly from the JD
    ats_keywords = list(dict.fromkeys(job_skills[:8]))

    # Tailored bullet points grounded in real candidate project data
    tailored_bullets = []
    for p in top_projects[:2]:
        desc = p.get("description", "")
        stack_str = ", ".join(p.get("tech_stack", [])[:3])
        tailored_bullets.append(
            f"Architected **{p['title']}** leveraging {stack_str}, ensuring high reliability and end-to-end functionality. ({desc[:90]}...)"
        )

    verified_db = [
        f"Master Candidate Profile: {cand.get('name')}, {cand.get('degree')} ({cand.get('college')})",
        f"Verified Technical Skills: {', '.join([s['name'] for s in cand_skills[:8]])}",
        f"Verified Projects in DB: {len(cand_projects)} projects available for resume tailoring.",
        f"Top Aligned Project: '{top_projects[0]['title'] if top_projects else 'None'}' ({', '.join(top_projects[0]['tech_stack']) if top_projects else ''})"
    ]

    extracted_ext = [
        f"Target Position: {opp['title']} at {opp['company_name']}",
        f"Target ATS Keywords: {', '.join(ats_keywords) if ats_keywords else 'Software engineering fundamentals'}",
        f"Required Experience: {opp.get('experience_required') or 'Entry-level / Internship'}"
    ]

    strategic_ai = [
        f"Feature '{top_projects[0]['title'] if top_projects else 'Top Project'}' as Project #1 at the top of your resume.",
        f"Incorporate ATS keywords: Ensure exact matches for {', '.join(ats_keywords[:4]) if ats_keywords else 'core skills'}.",
        "Reframe bullet points using Action Verb + Technical Method + Outcome format without inventing false metrics."
    ]

    unknown_missing = [
        "Candidate profile lacks verified quantitative metrics (e.g. % performance increase) for some projects; add if available.",
        "Specific internal ATS parsing software (e.g. Workday, Greenhouse, Lever) used by employer is unknown."
    ]

    summary_text = (
        f"**Resume Optimization Blueprint for {opp['title']} @ {opp['company_name']}**\n\n"
        f"To maximize ATS screen pass rates, prioritize your verified projects that showcase "
        f"**{', '.join(ats_keywords[:4]) if ats_keywords else 'relevant technical capabilities'}**. "
        f"Position **'{top_projects[0]['title'] if top_projects else 'Core Project'}'** prominently at the top of your Experience/Projects section.\n\n"
        f"**ATS Keyword Alignment:** Ensure your technical skills section highlights verified matches: "
        f"{', '.join(ats_keywords[:6]) if ats_keywords else 'None'}.\n\n"
        f"**Grounded Action Bullet Suggestions:**\n" +
        "\n".join([f"- {b}" for b in tailored_bullets])
    )

    result = {
        "workflow": "resume_intelligence",
        "title": f"Resume Intelligence: {opp['title']} @ {opp['company_name']}",
        "summary": summary_text,
        "metrics": {
            "top_projects_selected": len(top_projects),
            "ats_keywords_count": len(ats_keywords),
            "match_score": opp["match_score"]
        },
        "details": {
            "recommended_projects": top_projects,
            "ats_keywords": ats_keywords,
            "tailored_bullets": tailored_bullets
        },
        "truth_layers": _create_truth_layers(verified_db, extracted_ext, strategic_ai, unknown_missing)
    }

    intelligence_cache.set(cache_key, result, ttl=600)
    return result


async def run_interview_intelligence(
    opportunity_id: int,
    db: Session,
    interview_id: Optional[int] = None,
    use_cache: bool = True,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Workflow 3: Interview Intelligence
    Generates role-specific technical & behavioral interview preparation grounded in the candidate's real projects and past interview performance.
    """
    cand = get_candidate_context(db, scope="full", user_id=user_id)
    cand_id = cand.get("id", 1)
    cache_key = f"interview_intel:{opportunity_id}:{interview_id}:{cand_id}"

    if use_cache:
        cached = intelligence_cache.get(cache_key)
        if cached:
            return cached

    opp = get_opportunity_context(db, opportunity_id, user_id=user_id)
    if not opp:
        return {
            "workflow": "interview_prep",
            "error": f"Opportunity {opportunity_id} not found in database.",
            "truth_layers": _create_truth_layers([], [], [], [f"Opportunity ID {opportunity_id} does not exist."])
        }

    history = get_interview_history_context(db)
    cand_projects = cand.get("verified_projects", [])
    top_project = cand_projects[0] if cand_projects else {"title": "Core Engineering Project", "tech_stack": ["Python", "SQL"]}
    job_skills = (opp.get("required_skills") or []) + (opp.get("preferred_skills") or [])

    # Technical Questions tailored to job requirements
    tech_questions = []
    primary_skills = job_skills[:3] or ["Python", "REST APIs", "System Design"]
    for s in primary_skills:
        tech_questions.append({
            "skill": s,
            "question": f"How do you implement and optimize {s} in production-grade services?",
            "talking_point": f"Reference your verified work on '{top_project.get('title')}' where you utilized {', '.join(top_project.get('tech_stack', []))}."
        })

    # Behavioral Questions (STAR methodology)
    behavioral_questions = [
        {
            "category": "Problem Solving & Architecture",
            "question": f"Describe a challenging technical hurdle you faced while building {top_project.get('title')}, and how you debugged it.",
            "star_approach": f"Situation: Architecture of {top_project.get('title')}. Task: Resolving performance/data synchronization bottleneck. Action: Implemented systematic logging and profiling. Result: Achieved stable operation."
        },
        {
            "category": "Collaboration & Delivery",
            "question": "Tell me about a time you had to quickly learn a new technology or framework to meet a project goal.",
            "star_approach": f"Discuss adopting {top_project.get('tech_stack', ['modern tools'])[0]} during your academic/project work at {cand.get('college', 'college')}."
        }
    ]

    # Questions candidate should ask interviewer
    candidate_questions_to_ask = [
        f"What does the day-to-day workflow look like for the {opp['title']} on your team?",
        f"What are the highest-priority initiatives your engineering team is tackling at {opp['company_name']} over the next 6 months?",
        "What opportunities exist for mentorship and transition into full-time roles upon successful completion?"
    ]

    verified_db = [
        f"Candidate Verified Foundation: {cand.get('name')}, {cand.get('degree')} at {cand.get('college')}",
        f"Verified Project Anchor: '{top_project.get('title')}' ({', '.join(top_project.get('tech_stack', []))})",
        f"Interview History Record: {history['total_interviews']} logged interviews in CareerOS (Avg Performance: {history['average_performance']}/5.0)",
        f"Historical Strengths: {', '.join(history['historical_strengths']) if history['historical_strengths'] else 'No prior interview entries logged yet.'}"
    ]

    extracted_ext = [
        f"Employer: {opp['company_name']} ({opp.get('company_website') or 'External source'})",
        f"Target Role: {opp['title']} ({opp['workplace_type']}, {opp['location']})",
        f"Evaluated Technical Focus: {', '.join(primary_skills)}"
    ]

    strategic_ai = [
        f"When answering technical questions, always anchor your answers in '{top_project.get('title')}' to demonstrate practical execution over theoretical trivia.",
        "Use the STAR framework (Situation, Task, Action, Result) for behavioral questions, keeping answers under 2 minutes each.",
        f"Inquire about team tech stack and mentorship during the candidate question segment to demonstrate strong initiative."
    ]

    unknown_missing = [
        "Candidate's exact interviewer name and specific interview stage (e.g. recruiter screen vs live coding) is unassigned.",
        "Specific live coding environment (e.g. LeetCode, CodeSignal, take-home) is not specified in the public posting."
    ]
    if history["historical_weaknesses"]:
        strategic_ai.append(f"Past Interview Warning: You previously noted difficulties in '{', '.join(history['historical_weaknesses'])}'. Practice these areas beforehand.")

    summary_text = (
        f"**Interview Intelligence Dossier: {opp['title']} @ {opp['company_name']}**\n\n"
        f"To excel in this interview, anchor your responses directly in your verified engineering projects. "
        f"The role demands demonstrated proficiency in **{', '.join(primary_skills)}**.\n\n"
        f"**Key Technical Inquiries:**\n" +
        "\n".join([f"- **{q['skill']}**: {q['question']}\n  *Talking Point:* {q['talking_point']}" for q in tech_questions]) +
        f"\n\n**Behavioral Preparation (STAR Framework):**\n" +
        "\n".join([f"- **{b['category']}**: {b['question']}" for b in behavioral_questions])
    )

    result = {
        "workflow": "interview_prep",
        "title": f"Interview Preparation: {opp['title']} @ {opp['company_name']}",
        "summary": summary_text,
        "metrics": {
            "technical_questions_count": len(tech_questions),
            "behavioral_questions_count": len(behavioral_questions),
            "historical_interviews_analyzed": history["total_interviews"]
        },
        "details": {
            "technical_questions": tech_questions,
            "behavioral_questions": behavioral_questions,
            "questions_to_ask": candidate_questions_to_ask,
            "anchor_project": top_project
        },
        "truth_layers": _create_truth_layers(verified_db, extracted_ext, strategic_ai, unknown_missing)
    }

    intelligence_cache.set(cache_key, result, ttl=600)
    return result


async def run_career_growth_intelligence(
    db: Session,
    use_cache: bool = True,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Workflow 4: Career Growth Intelligence
    Analyzes live market skill demands across active database opportunities against the candidate's verified profile to generate a pragmatic learning roadmap.
    """
    cand = get_candidate_context(db, scope="full", user_id=user_id)
    cand_id = cand.get("id", 1)
    cache_key = f"career_growth:{cand_id}"

    if use_cache:
        cached = intelligence_cache.get(cache_key)
        if cached:
            return cached

    market = get_market_skills_context(db, top_n=20)
    market_skills = market.get("top_market_demanded_skills", [])
    
    cand_skills_set = {s["name"].lower() for s in cand.get("verified_skills", [])}

    # Identify candidate's verified market-relevant skills
    mastered_high_demand = [
        m for m in market_skills if m["skill"].lower() in cand_skills_set
    ]

    # Identify high-ROI skills missing from candidate's profile
    high_roi_missing = [
        m for m in market_skills if m["skill"].lower() not in cand_skills_set
    ][:5]

    # Pragmatic multi-week roadmap
    roadmap = []
    if high_roi_missing:
        roadmap.append({
            "phase": "Phase 1 (Weeks 1-2)",
            "focus_skill": high_roi_missing[0]["skill"],
            "market_demand_postings": high_roi_missing[0]["frequency"],
            "learning_objective": f"Master core fundamentals, syntax, and idiomatic design patterns for {high_roi_missing[0]['skill']}.",
            "milestone_project": f"Build a focused micro-service or module integrating {high_roi_missing[0]['skill']} into your existing portfolio."
        })
    if len(high_roi_missing) > 1:
        roadmap.append({
            "phase": "Phase 2 (Weeks 3-4)",
            "focus_skill": high_roi_missing[1]["skill"],
            "market_demand_postings": high_roi_missing[1]["frequency"],
            "learning_objective": f"Apply {high_roi_missing[1]['skill']} in cloud-native or production-simulated workflows.",
            "milestone_project": f"Deploy a production-ready application showcasing {high_roi_missing[1]['skill']} alongside {high_roi_missing[0]['skill']}."
        })
    if len(high_roi_missing) > 2:
        roadmap.append({
            "phase": "Phase 3 (Weeks 5-6)",
            "focus_skill": high_roi_missing[2]["skill"],
            "market_demand_postings": high_roi_missing[2]["frequency"],
            "learning_objective": f"Explore advanced paradigms and performance tuning with {high_roi_missing[2]['skill']}.",
            "milestone_project": "Publish benchmark reports and open-source GitHub repository with full test coverage."
        })

    verified_db = [
        f"Candidate: {cand.get('name')} ({cand.get('degree')} at {cand.get('college')}, Grad: {cand.get('graduation_year')})",
        f"Verified Profile Skills: {len(cand.get('verified_skills', []))} skills recorded with verified evidence.",
        f"Verified High-Demand Skills Already Mastered: {', '.join([m['skill'] for m in mastered_high_demand[:5]]) or 'None'}",
        f"Market Dataset Analyzed: {market.get('total_opportunities_analyzed', 0)} active, verified internship postings in CareerOS database."
    ]

    market_demand_strs = [f"{m['skill']} ({m['frequency']} roles)" for m in market_skills[:5]]
    extracted_ext = [
        f"Top Market Demanded Skills: {', '.join(market_demand_strs)}",
        f"Most Active Job Category: {max(market.get('category_distribution', {}).items(), key=lambda x: x[1])[0] if market.get('category_distribution') else 'Software Engineering'}"
    ]

    strategic_ai = [
        f"Priority Learning Recommendation: Acquire '{high_roi_missing[0]['skill'] if high_roi_missing else 'System Design'}' to unlock the highest number of active listings.",
        "Build concrete projects to substantiate new skills rather than relying solely on course completion certificates.",
        "Add GitHub repository links and verifiable metrics to your Master Candidate Profile as soon as projects reach MVP."
    ]

    unknown_missing = [
        "Candidate's daily/weekly available study hours are unspecified in profile.",
        "Long-term career track preference (e.g. AI Research vs DevOps vs Full-Stack) is not formally set."
    ]

    summary_text = (
        f"**Market-Driven Career Growth Strategy**\n\n"
        f"Based on real-time aggregation of **{market.get('total_opportunities_analyzed', 0)} live internship postings** in CareerOS, "
        f"your verified profile strongly aligns with high-demand competencies such as "
        f"**{', '.join([m['skill'] for m in mastered_high_demand[:4]]) if mastered_high_demand else 'core programming'}**.\n\n"
        f"**High-ROI Skill Gaps:**\n" +
        "\n".join([f"- **{m['skill']}**: Appears in **{m['frequency']}** active postings currently missing from your verified profile." for m in high_roi_missing]) +
        f"\n\n**Structured Learning Roadmap:**\n" +
        "\n".join([f"- **{r['phase']} - {r['focus_skill']}**: {r['learning_objective']}\n  *Milestone Project:* {r['milestone_project']}" for r in roadmap])
    )

    result = {
        "workflow": "career_growth",
        "title": "Career Growth & Market Skill Intelligence",
        "summary": summary_text,
        "metrics": {
            "opportunities_analyzed": market.get("total_opportunities_analyzed", 0),
            "verified_skills_mastered": len(mastered_high_demand),
            "high_roi_gaps_identified": len(high_roi_missing)
        },
        "details": {
            "mastered_skills": mastered_high_demand,
            "missing_high_roi_skills": high_roi_missing,
            "roadmap": roadmap
        },
        "truth_layers": _create_truth_layers(verified_db, extracted_ext, strategic_ai, unknown_missing)
    }

    intelligence_cache.set(cache_key, result, ttl=600)
    return result


async def run_application_intelligence(
    db: Session,
    use_cache: bool = True,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Workflow 5: Application Intelligence
    Analyzes application pipeline funnel conversion, overdue follow-ups, and actionable next steps.
    """
    cand = get_candidate_context(db, scope="preferences_only", user_id=user_id)
    cand_id = cand.get("id", 1)
    cache_key = f"app_intelligence:{cand_id}"

    if use_cache:
        cached = intelligence_cache.get(cache_key)
        if cached:
            return cached

    pipeline = get_pipeline_context(db, user_id=user_id)
    total_apps = pipeline.get("total_applications", 0)
    stages = pipeline.get("stages", {})
    stages_count = pipeline.get("stages_count", {})
    overdue_follow_ups = pipeline.get("overdue_follow_ups", [])

    applied_count = stages_count.get("applied", 0)
    interviewing_count = stages_count.get("interviewing", 0)
    offered_count = stages_count.get("offered", 0)
    rejected_count = stages_count.get("rejected", 0)

    # Conversion calculations
    interview_rate = (interviewing_count / applied_count * 100) if applied_count > 0 else 0.0
    offer_rate = (offered_count / interviewing_count * 100) if interviewing_count > 0 else 0.0

    # Bottleneck diagnosis
    bottlenecks = []
    if applied_count > 5 and interviewing_count == 0:
        bottlenecks.append("High application volume without interview conversions suggests resume ATS optimization or portfolio presentation needs improvement.")
    if overdue_follow_ups:
        bottlenecks.append(f"{len(overdue_follow_ups)} application(s) have been pending for >7 days without a status change or follow-up note.")
    if total_apps < 5:
        bottlenecks.append("Application volume is low (<5 active applications). Pipeline health requires consistent application cadence.")

    # Actionable recommendations
    recommendations = []
    if overdue_follow_ups:
        recommendations.append(f"Send polite professional follow-ups to {', '.join([o['company_name'] for o in overdue_follow_ups[:3]])}.")
    recommendations.append("Target at least 3-5 verified high-match roles (>=80% match score) per week.")
    recommendations.append("Log interview notes and questions into the Interview Journal immediately following any recruiter or technical call.")

    verified_db = [
        f"Total Tracked Applications in DB: {total_apps} applications recorded in CareerOS.",
        f"Stage Breakdown: Applied: {applied_count}, Interviewing: {interviewing_count}, Offered: {offered_count}, Rejected: {rejected_count}",
        f"Overdue Follow-ups Flagged: {len(overdue_follow_ups)} applications pending >7 days.",
        f"Recent Stage Transitions: {len(pipeline.get('recent_transitions', []))} transitions recorded."
    ]

    extracted_ext = [
        "Typical Tech Internship Response Window: 7 to 14 business days post-submission.",
        "Industry Benchmark: 10-15% initial recruiter screen conversion rate for cold online applications."
    ]

    strategic_ai = [
        f"Pipeline Health Assessment: {'Healthy conversion' if interview_rate >= 15 else 'Attention needed on resume / application quality'}.",
        f"Immediate Action: {recommendations[0] if recommendations else 'Maintain application pacing'}.",
        "Focus applications on roles with match score >70% to conserve effort and improve response rates."
    ]

    unknown_missing = [
        "Internal recruiter review stage inside target employer Applicant Tracking Systems cannot be retrieved externally.",
        "Specific rejection reasons are not shared by employers."
    ]

    summary_text = (
        f"**Application Pipeline Intelligence & Funnel Diagnostic**\n\n"
        f"You currently have **{total_apps} applications tracked** in CareerOS. "
        f"Pipeline breakdown: **{applied_count} applied**, **{interviewing_count} interviewing**, **{offered_count} offers**, and **{rejected_count} rejected**.\n\n"
        f"**Conversion Metrics:**\n"
        f"- Interview Conversion Rate: **{round(interview_rate, 1)}%**\n"
        f"- Offer Conversion Rate: **{round(offer_rate, 1)}%**\n\n"
        f"**Identified Bottlenecks & Overdue Actions:**\n" +
        ("\n".join([f"- {b}" for b in bottlenecks]) if bottlenecks else "- Pipeline flow is operating normally.") +
        f"\n\n**Actionable Recommendations:**\n" +
        "\n".join([f"- {r}" for r in recommendations])
    )

    result = {
        "workflow": "application_intelligence",
        "title": "Application Pipeline Intelligence",
        "summary": summary_text,
        "metrics": {
            "total_applications": total_apps,
            "interview_rate": round(interview_rate, 1),
            "offer_rate": round(offer_rate, 1),
            "overdue_count": len(overdue_follow_ups)
        },
        "details": {
            "stages_count": stages_count,
            "overdue_follow_ups": overdue_follow_ups,
            "bottlenecks": bottlenecks,
            "recommendations": recommendations
        },
        "truth_layers": _create_truth_layers(verified_db, extracted_ext, strategic_ai, unknown_missing)
    }

    intelligence_cache.set(cache_key, result, ttl=600)
    return result
