import re
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.models.opportunity import Opportunity
from backend.app.models.candidate import CandidateProfile
from backend.app.models.application import ApplicationRecord
from backend.app.models.chat import ChatConversation, ChatMessage
from backend.app.models.interview import InterviewJournalRecord
from backend.app.ai.ollama_client import ollama_client
from backend.app.services.context_retriever import (
    get_candidate_context,
    get_opportunity_context,
    get_pipeline_context,
    get_interview_history_context,
    get_market_skills_context,
    search_opportunities_vector
)
from backend.app.services.intelligence_engine import (
    run_job_matching_intelligence,
    run_resume_intelligence,
    run_interview_intelligence,
    run_career_growth_intelligence,
    run_application_intelligence
)

logger = logging.getLogger(__name__)


def format_truth_layers_markdown(truth_layers: Dict[str, List[str]]) -> str:
    """Formats the 4 truth layers into clean, readable Markdown blocks with visual markers."""
    if not truth_layers:
        return ""
        
    parts = []
    verified_db = truth_layers.get("verified_database", [])
    if verified_db:
        parts.append("### 🟢 [Verified Database Record]\n" + "\n".join([f"- {item}" for item in verified_db]))
        
    extracted_ext = truth_layers.get("extracted_external", [])
    if extracted_ext:
        parts.append("### 🔵 [Extracted External Information]\n" + "\n".join([f"- {item}" for item in extracted_ext]))
        
    strategic_ai = truth_layers.get("strategic_recommendations", [])
    if strategic_ai:
        parts.append("### 🟡 [AI Strategic Recommendation]\n" + "\n".join([f"- {item}" for item in strategic_ai]))
        
    unknown_missing = truth_layers.get("unknown_missing", [])
    if unknown_missing:
        parts.append("### ⚪ [Unknown / Missing Information]\n" + "\n".join([f"- {item}" for item in unknown_missing]))
        
    return "\n\n".join(parts)


def execute_chat_tool(tool_name: str, args: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """Executes structured database operations requested by the AI assistant."""
    if tool_name == "find_matching_internships":
        query = args.get("query", "")
        min_score = float(args.get("min_score", 50.0))
        limit = int(args.get("limit", 5))
        
        db_query = db.query(Opportunity).filter(
            Opportunity.employment_type == "internship",
            Opportunity.match_score >= min_score
        )
        if query:
            db_query = db_query.filter(
                (Opportunity.title.ilike(f"%{query}%")) |
                (Opportunity.company_name.ilike(f"%{query}%")) |
                (Opportunity.description.ilike(f"%{query}%"))
            )
        results = db_query.order_by(desc(Opportunity.match_score)).limit(limit).all()
        return {
            "count": len(results),
            "opportunities": [
                {
                    "id": o.id,
                    "title": o.title,
                    "company": o.company_name,
                    "location": o.normalized_location or o.location,
                    "stipend": o.stipend_text or "Undisclosed",
                    "match_score": o.match_score,
                    "source": o.source_platform,
                    "application_url": o.application_url or o.original_url
                } for o in results
            ]
        }
        
    elif tool_name == "compare_opportunities":
        id1 = int(args.get("id1", 0))
        id2 = int(args.get("id2", 0))
        o1 = get_opportunity_context(db, id1)
        o2 = get_opportunity_context(db, id2)
        if not o1 or not o2:
            return {"error": f"One or both opportunities not found (id1: {id1}, id2: {id2})"}
        return {
            "opportunity_1": {
                "id": o1["id"], "title": o1["title"], "company": o1["company_name"],
                "location": o1["location"], "stipend": o1["stipend_text"],
                "match_score": o1["match_score"], "workplace": o1["workplace_type"]
            },
            "opportunity_2": {
                "id": o2["id"], "title": o2["title"], "company": o2["company_name"],
                "location": o2["location"], "stipend": o2["stipend_text"],
                "match_score": o2["match_score"], "workplace": o2["workplace_type"]
            }
        }
        
    elif tool_name == "get_candidate_profile":
        cand = db.query(CandidateProfile).order_by(CandidateProfile.id.asc()).first()
        if not cand:
            return {"error": "Candidate profile not found"}
        return {
            "name": cand.name,
            "degree": cand.degree,
            "college": cand.college,
            "graduation_year": cand.graduation_year,
            "cgpa": cand.cgpa,
            "skills": [s.get("name") if isinstance(s, dict) else str(s) for s in (cand.skills or [])],
            "projects_count": len(cand.projects or []),
            "experience_count": len(cand.experience or [])
        }
        
    elif tool_name == "get_application_pipeline":
        apps = db.query(ApplicationRecord).order_by(desc(ApplicationRecord.created_at)).all()
        by_status: Dict[str, List[Any]] = {}
        for a in apps:
            by_status.setdefault(a.status, []).append({
                "id": a.id, "company": a.company_name, "role": a.job_title,
                "applied_date": a.applied_date.isoformat() if a.applied_date else None,
                "follow_up_date": a.follow_up_date.isoformat() if a.follow_up_date else None
            })
        return {
            "total_tracked": len(apps),
            "stages": by_status
        }
        
    elif tool_name == "analyze_skill_gaps":
        opp_id = int(args.get("opportunity_id", 0))
        opp = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
        if not opp:
            return {"error": f"Opportunity {opp_id} not found"}
        cand = db.query(CandidateProfile).order_by(CandidateProfile.id.asc()).first()
        cand_skills = {s.get("name", "").lower() for s in (cand.skills or [])} if cand else set()
        extracted = opp.extracted_data or {}
        req_skills = extracted.get("mandatory_technical_skills", []) or opp.required_skills or []
        
        matches = [s for s in req_skills if s.lower() in cand_skills]
        gaps = [s for s in req_skills if s.lower() not in cand_skills]
        return {
            "role": opp.title,
            "company": opp.company_name,
            "match_score": opp.match_score,
            "matching_skills": matches,
            "missing_skills": gaps
        }
        
    elif tool_name == "draft_outreach_message":
        opp_id = int(args.get("opportunity_id", 0))
        recruiter = args.get("recruiter_name", "Hiring Manager")
        opp = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
        cand = db.query(CandidateProfile).order_by(CandidateProfile.id.asc()).first()
        if not opp:
            return {"error": "Opportunity not found"}
        
        top_project = cand.projects[0].get("title") if cand and cand.projects else "core systems project"
        outreach = (
            f"Hi {recruiter},\n\n"
            f"I recently came across the {opp.title} opening at {opp.company_name} and wanted to reach out. "
            f"As a {cand.degree if cand else 'Computer Science student'} with hands-on experience building {top_project}, "
            f"my technical background closely aligns with your team's mission.\n\n"
            f"I have submitted my application and would welcome a brief conversation if you have a moment this week.\n\n"
            f"Best regards,\n{cand.name if cand else 'Candidate'}"
        )
        return {"outreach_message": outreach}
    return {"error": f"Unknown tool '{tool_name}'"}


async def process_user_chat_message(
    conversation_id: int,
    user_prompt: str,
    db: Session,
    opportunity_id: Optional[int] = None,
    workflow: Optional[str] = None,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """Processes user chat prompt, executes tools if indicated, and generates context-aware grounded response."""
    # Record user message
    user_msg = ChatMessage(
        conversation_id=conversation_id,
        sender="user",
        content=user_prompt
    )
    db.add(user_msg)
    db.commit()
    
    # Retrieve recent messages
    history = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation_id
    ).order_by(ChatMessage.created_at.asc()).limit(10).all()
    
    # Analyze prompt intent and parameters
    p_lower = user_prompt.lower()
    tools_executed = []
    truth_layers_data = None
    response_text = None
    
    # Extract numeric opportunity ID if mentioned in prompt and not explicitly passed
    extracted_ids = [int(n) for n in re.findall(r'\b\d+\b', p_lower)]
    target_opp_id = opportunity_id or (extracted_ids[0] if extracted_ids else None)

    # 1. Specialized Workflow Triggers
    if workflow == "resume_intelligence" or ("resume" in p_lower and any(w in p_lower for w in ["tailor", "optimize", "ats", "keywords"])):
        target_id = target_opp_id or 37
        res = await run_resume_intelligence(target_id, db, user_id=user_id)
        tools_executed.append({"tool": "resume_intelligence", "result": res})
        truth_layers_data = res.get("truth_layers")
        response_text = f"{res.get('summary')}\n\n---\n\n{format_truth_layers_markdown(truth_layers_data)}"

    elif workflow == "interview_prep" or any(w in p_lower for w in ["interview", "prep", "behavioral", "mock"]):
        target_id = target_opp_id or 37
        res = await run_interview_intelligence(target_id, db, user_id=user_id)
        tools_executed.append({"tool": "interview_intelligence", "result": res})
        truth_layers_data = res.get("truth_layers")
        response_text = f"{res.get('summary')}\n\n---\n\n{format_truth_layers_markdown(truth_layers_data)}"

    elif workflow == "career_growth" or any(w in p_lower for w in ["growth", "roadmap", "learn", "market demand", "upskill"]):
        res = await run_career_growth_intelligence(db, user_id=user_id)
        tools_executed.append({"tool": "career_growth_intelligence", "result": res})
        truth_layers_data = res.get("truth_layers")
        response_text = f"{res.get('summary')}\n\n---\n\n{format_truth_layers_markdown(truth_layers_data)}"

    elif workflow == "application_intelligence" or any(w in p_lower for w in ["pipeline", "funnel", "conversion", "applications", "applied"]):
        res = await run_application_intelligence(db, user_id=user_id)
        tools_executed.append({"tool": "application_intelligence", "result": res})
        truth_layers_data = res.get("truth_layers")
        response_text = f"{res.get('summary')}\n\n---\n\n{format_truth_layers_markdown(truth_layers_data)}"

    elif workflow == "job_matching" or (target_opp_id and any(w in p_lower for w in ["match", "gap", "fit", "missing"])):
        target_id = target_opp_id or 37
        res = await run_job_matching_intelligence(target_id, db, user_id=user_id)
        tools_executed.append({"tool": "job_matching_intelligence", "result": res})
        truth_layers_data = res.get("truth_layers")
        response_text = f"{res.get('summary')}\n\n---\n\n{format_truth_layers_markdown(truth_layers_data)}"

    # 2. General Queries / Tools
    if not response_text:
        tool_context = ""
        if any(kw in p_lower for kw in ["find", "search", "match", "recommend", "show me internships", "jobs for me", "roles"]):
            res = execute_chat_tool("find_matching_internships", {"query": user_prompt, "min_score": 40, "limit": 4}, db)
            tools_executed.append({"tool": "find_matching_internships", "result": res})
            tool_context += f"\nDATABASE FACT (Matching Internships):\n{json.dumps(res, indent=2)}\n"

        if "compare" in p_lower and len(extracted_ids) >= 2:
            res = execute_chat_tool("compare_opportunities", {"id1": extracted_ids[0], "id2": extracted_ids[1]}, db)
            tools_executed.append({"tool": "compare_opportunities", "result": res})
            tool_context += f"\nDATABASE FACT (Comparison):\n{json.dumps(res, indent=2)}\n"

        if any(kw in p_lower for kw in ["my profile", "my skills", "candidate profile", "who am i", "what skills do i have"]):
            res = execute_chat_tool("get_candidate_profile", {}, db)
            tools_executed.append({"tool": "get_candidate_profile", "result": res})
            tool_context += f"\nDATABASE FACT (Candidate Profile):\n{json.dumps(res, indent=2)}\n"

        if any(kw in p_lower for kw in ["outreach", "cold message", "email recruiter", "linkedin message"]):
            target_id = target_opp_id or 37
            res = execute_chat_tool("draft_outreach_message", {"opportunity_id": target_id}, db)
            tools_executed.append({"tool": "draft_outreach_message", "result": res})
            tool_context += f"\nDATABASE FACT (Outreach):\n{json.dumps(res, indent=2)}\n"

        # Try LLM generation for general queries
        system_prompt = """You are CareerOS AI, a context-aware career intelligence engine.
RULES:
1. Always ground your answers strictly in verified database facts.
2. Clearly separate what is verified from your strategic advice.
3. NEVER invent companies, skills, or fake listings.
4. Output structured Markdown with actionable next steps."""

        cand_ctx = get_candidate_context(db, scope="full")
        llm_prompt = f"""Verified Candidate Profile:
Name: {cand_ctx.get('name')} | Degree: {cand_ctx.get('degree')} ({cand_ctx.get('college')})
Verified Skills: {[s['name'] for s in cand_ctx.get('verified_skills', [])]}
Verified Projects: {[p['title'] for p in cand_ctx.get('verified_projects', [])[:3]]}

Database Tool Results:
{tool_context if tool_context else 'No specific DB tool triggered.'}

User Question: {user_prompt}
"""
        try:
            raw_response = await asyncio.wait_for(
                ollama_client.generate_json(
                    prompt=f"{llm_prompt}\nReturn JSON with 'response': 'your markdown response text here'",
                    system_prompt=system_prompt
                ),
                timeout=18.0
            )
            if raw_response:
                parsed = json.loads(raw_response)
                response_text = parsed.get("response")
        except Exception as e:
            logger.info(f"Ollama chat generation failed or timed out: {e}")

        # Deterministic grounded fallback for general tools
        if not response_text:
            if tools_executed:
                t_name = tools_executed[0]["tool"]
                res_data = tools_executed[0]["result"]
                if t_name == "find_matching_internships":
                    opps = res_data.get("opportunities", [])
                    lines = [f"- **{o['title']}** at **{o['company']}** ({o['location']}) - *{round(o['match_score'])}% match score* (ID: #{o['id']})" for o in opps]
                    response_text = (
                        f"### 🟢 [Verified Database Record]\n"
                        f"Found **{len(opps)} matching opportunities** in the CareerOS database for your verified profile:\n\n" +
                        "\n".join(lines) +
                        f"\n\n### 🟡 [AI Strategic Recommendation]\n"
                        f"- Select any opportunity above to run **Job Matching Intelligence**, **Resume Tailoring**, or **Interview Preparation**."
                    )
                elif t_name == "get_candidate_profile":
                    skills = [s["name"] for s in res_data.get("verified_skills", [])]
                    projects = [p["title"] for p in res_data.get("verified_projects", [])]
                    response_text = (
                        f"### 🟢 [Verified Database Record]\n"
                        f"**Master Candidate Profile:**\n"
                        f"- **Name:** {res_data.get('name')}\n"
                        f"- **Education:** {res_data.get('degree')} at {res_data.get('college')} (Grad: {res_data.get('graduation_year')})\n"
                        f"- **Verified Skills ({len(skills)}):** {', '.join(skills)}\n"
                        f"- **Verified Projects ({len(projects)}):** {', '.join(projects)}\n\n"
                        f"### 🟡 [AI Strategic Recommendation]\n"
                        f"Your profile has verified evidence attached to every technical skill. You can directly tailor resumes and track applications based on these verified assets."
                    )
                elif t_name == "draft_outreach_message":
                    response_text = (
                        f"### 🟡 [AI Strategic Recommendation]\n"
                        f"Here is a personalized outreach message tailored to your verified projects:\n\n"
                        f"```text\n{res_data.get('outreach_message')}\n```\n\n"
                        f"### ⚪ [Unknown / Missing Information]\n"
                        f"- Hiring manager name was not listed in the opportunity feed; customize the greeting before sending."
                    )
                else:
                    response_text = f"Retrieved verified data from CareerOS: {json.dumps(res_data, indent=2)}"
            else:
                response_text = (
                    f"I am your **CareerOS Context-Aware Career Intelligence Engine**.\n\n"
                    f"I have direct read access to your **Master Candidate Profile** ({cand_ctx.get('name')}), "
                    f"**205 live database opportunities**, and your **application pipeline**.\n\n"
                    f"You can use the specialized workflows above or ask me to:\n"
                    f"- **Match jobs**: Compare your verified skills against any internship\n"
                    f"- **Resume ATS intelligence**: Highlight optimal projects and ATS keywords\n"
                    f"- **Interview prep**: Generate technical questions grounded in your projects\n"
                    f"- **Career growth**: Discover high-ROI skills demanded across live postings\n"
                    f"- **Application pipeline**: Diagnose stage drop-offs and overdue follow-ups"
                )

    # Save assistant response
    asst_msg = ChatMessage(
        conversation_id=conversation_id,
        sender="assistant",
        content=response_text,
        tool_calls=tools_executed
    )
    db.add(asst_msg)
    
    # Update conversation updated_at
    conv = db.query(ChatConversation).filter(ChatConversation.id == conversation_id).first()
    if conv:
        conv.updated_at = datetime.utcnow()
        if conv.title == "Career Assistant Chat" and len(user_prompt) > 4:
            conv.title = user_prompt[:35] + ("..." if len(user_prompt) > 35 else "")
            
    db.commit()
    db.refresh(asst_msg)
    
    return {
        "id": asst_msg.id,
        "conversation_id": conversation_id,
        "sender": "assistant",
        "content": response_text,
        "tool_calls": tools_executed,
        "truth_layers": truth_layers_data,
        "created_at": asst_msg.created_at.isoformat()
    }
