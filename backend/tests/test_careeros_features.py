import os
import pytest
from unittest.mock import patch, AsyncMock
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models.candidate import CandidateProfile
from backend.app.models.opportunity import Opportunity
from backend.app.models.resume import ResumeDocument
from backend.app.models.application import ApplicationRecord
from backend.app.models.application_transition import ApplicationStageTransition
from backend.app.models.interview import InterviewJournalRecord
from backend.app.models.chat import ChatConversation, ChatMessage

from backend.app.services.latex_compiler import compile_latex, build_latex_from_profile, escape_latex
from backend.app.services.resume_tailorer import tailor_resume_for_opportunity
from backend.app.services.integration_service import fetch_portfolio_data
from backend.app.services.verifier import is_safe_external_url
from backend.app.services.analytics_service import get_application_sankey_data
from backend.app.services.ai_assistant import execute_chat_tool

client = TestClient(app)

# -------------------------------------------------------------
# 1. LaTeX Resume Studio Tests
# -------------------------------------------------------------
def test_latex_escape_and_template_generation():
    raw_text = "Experienced in C++, R&D & 100% test coverage with $500 budget and #1 rank."
    escaped = escape_latex(raw_text)
    assert "\\&" in escaped
    assert "\\%" in escaped
    assert "\\$" in escaped
    assert "\\#" in escaped

    candidate_data = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+91 98765 43210",
        "location": "Bengaluru, India",
        "github_url": "https://github.com/janedoe",
        "linkedin_url": "https://linkedin.com/in/janedoe",
        "portfolio_url": "https://janedoe.dev",
        "education": [
            {
                "degree": "B.Tech Computer Science",
                "institution": "National Institute of Technology",
                "year": "2022 - 2026",
                "score": "9.2 CGPA"
            }
        ],
        "skills": [
            {"name": "Python", "level": "advanced", "evidence": "Built backend services"},
            {"name": "FastAPI", "level": "advanced", "evidence": "REST APIs"},
            {"name": "PostgreSQL", "level": "intermediate", "evidence": "Complex queries"}
        ],
        "projects": [
            {
                "title": "Cloud Job Engine",
                "tech_stack": ["Python", "FastAPI", "PostgreSQL"],
                "bullets": ["Processed 5,000 requests per minute with async pipelines."]
            }
        ],
        "experiences": [
            {
                "title": "Software Engineering Intern",
                "company": "Tech Corp",
                "duration": "May 2025 - Jul 2025",
                "bullets": ["Integrated 4 third-party APIs."]
            }
        ]
    }

    latex = build_latex_from_profile(candidate_data, template_id="ats_modern")
    assert "\\documentclass" in latex
    assert "Jane Doe" in latex
    assert "Python" in latex
    assert "Cloud Job Engine" in latex
    assert "\\end{document}" in latex

def test_latex_pdf_compilation():
    sample_latex = r"""
\documentclass[10pt,letterpaper]{article}
\usepackage[margin=0.75in]{geometry}
\begin{document}
\begin{center}
{\LARGE \textbf{Automated Test Resume}} \\
\vspace{4pt}
test@example.com $|$ +91 99999 88888 $|$ Bengaluru, India
\end{center}
\section*{Technical Skills}
Python, FastAPI, PostgreSQL, Docker
\end{document}
"""
    success, pdf_path, compiler_used = compile_latex(sample_latex, base_name="test_compile")
    assert success is True
    assert pdf_path is not None
    assert os.path.exists(pdf_path)
    assert os.path.getsize(pdf_path) > 100
    assert compiler_used in ["tectonic", "reportlab_ats_engine"]

    # Verify download via API
    res = client.get("/api/resumes/master")
    assert res.status_code == 200
    master_id = res.json()["id"]

    res_compile = client.post(f"/api/resumes/{master_id}/compile")
    assert res_compile.status_code == 200
    assert res_compile.json()["pdf_url"] is not None

    res_pdf = client.get(f"/api/resumes/{master_id}/pdf")
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"

# -------------------------------------------------------------
# 2. Strict Factual Resume Tailoring (Zero Synthetic Inventions)
# -------------------------------------------------------------
def test_strict_factual_resume_tailoring():
    db = SessionLocal()
    try:
        cand = db.query(CandidateProfile).first()
        opp = db.query(Opportunity).first()
        assert cand is not None
        assert opp is not None

        # Verify candidate's real skill set
        cand_skill_names = {s.get("name", "").lower() for s in (cand.skills or [])}

        cand_dict = {
            "name": cand.name, 
            "email": cand.email, 
            "skills": cand.skills, 
            "projects": cand.projects,
            "degree": cand.degree, 
            "college": cand.college,
            "experience": cand.experience
        }
        opp_dict = {
            "id": opp.id, 
            "title": opp.title, 
            "company_name": opp.company_name, 
            "extracted_data": opp.extracted_data
        }
        tailored = tailor_resume_for_opportunity(cand_dict, opp_dict, template_id="ats_classic")
        assert tailored["latex_content"] is not None
        assert "tailored_insights" in tailored
        insights = tailored["tailored_insights"]
        
        # Verify matched skills come exclusively from candidate's genuine skills
        for matched in insights.get("highlighted_skills", []):
            assert matched.lower() in cand_skill_names, f"Invented skill detected: {matched}"

        # Verify zero hallucination guarantee
        assert insights.get("traceability", {}).get("invented_skills", 0) == 0

        # Test API endpoint with mocked Groq response
        with patch("backend.app.api.resumes.ai_service.tailor_resume", new_callable=AsyncMock) as mock_tailor:
            cand_skills_list = [s.get("name") if isinstance(s, dict) else s for s in (cand.skills or [])]
            mock_tailor.return_value = {
                "success": True,
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "latency_ms": 120.0,
                "tokens": 400,
                "data": {
                    "matched_skills": cand_skills_list[:2],
                    "missing_skills": [],
                    "bullet_refinements": [],
                    "suggested_section_order": ["Education", "Skills", "Projects"],
                    "rationale": "Tailored for software engineering"
                }
            }
            res = client.post("/api/resumes/tailor", json={"opportunity_id": opp.id, "template_id": "ats_classic"})
            assert res.status_code == 200
            data = res.json()
            assert data["target_opportunity_id"] == opp.id
            assert data["pdf_path"] is not None
            # Clean up tailored test resume
            client.delete(f"/api/resumes/{data['id']}")
    finally:
        db.close()

# -------------------------------------------------------------
# 3. SSRF Protection & External Integrations
# -------------------------------------------------------------
def test_ssrf_protection_in_portfolio_scanning():
    dangerous_urls = [
        "http://localhost:8000/internal",
        "http://127.0.0.1:5432",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.5:8080/admin",
        "http://192.168.1.1/setup"
    ]
    for url in dangerous_urls:
        safe, reason = is_safe_external_url(url)
        assert safe is False
        assert "SSRF" in reason

    # Test API endpoint blocks local/private IPs
    res_api = client.post("/api/candidate/integrations/portfolio", json={"url": "http://127.0.0.1:9000/config"})
    assert res_api.status_code == 400
    assert "SSRF" in res_api.json()["detail"]

# -------------------------------------------------------------
# 4. Server-Side Pagination Across All Modules
# -------------------------------------------------------------
def test_server_side_pagination_metadata():
    # 1. Opportunities Pagination
    res_opp = client.get("/api/opportunities?page=1&page_size=10")
    assert res_opp.status_code == 200
    opp_data = res_opp.json()
    assert opp_data["page"] == 1
    assert opp_data["page_size"] == 10
    assert "total" in opp_data
    assert "total_pages" in opp_data
    assert len(opp_data["items"]) <= 10

    # 2. Resumes Pagination
    res_res = client.get("/api/resumes?page=1&page_size=5")
    assert res_res.status_code == 200
    res_data = res_res.json()
    assert res_data["page"] == 1
    assert res_data["page_size"] == 5
    assert "total" in res_data
    assert "total_pages" in res_data

    # 3. Applications Pagination
    res_app = client.get("/api/applications?page=1&page_size=5")
    assert res_app.status_code == 200
    app_data = res_app.json()
    assert app_data["page"] == 1
    assert app_data["page_size"] == 5
    assert "total" in app_data
    assert "total_pages" in app_data

    # 4. Companies Pagination
    res_comp = client.get("/api/companies?page=1&page_size=10")
    assert res_comp.status_code == 200
    comp_data = res_comp.json()
    assert comp_data["page"] == 1
    assert comp_data["page_size"] == 10
    assert "total" in comp_data
    assert "total_pages" in comp_data

    # 5. Interviews Pagination
    res_int = client.get("/api/interviews?page=1&page_size=5")
    assert res_int.status_code == 200
    int_data = res_int.json()
    assert int_data["page"] == 1
    assert int_data["page_size"] == 5
    assert "total" in int_data
    assert "total_pages" in int_data

# -------------------------------------------------------------
# 5. Parallel Source Sync & Progress Monitor
# -------------------------------------------------------------
def test_sync_progress_endpoint():
    res = client.get("/api/sources/sync-progress")
    assert res.status_code == 200
    data = res.json()
    assert "is_running" in data
    assert "active_sources" in data
    assert "summary" in data

# -------------------------------------------------------------
# 6. Interactive Database-Backed Sankey Analytics
# -------------------------------------------------------------
def test_sankey_data_computation_and_stage_transitions():
    db = SessionLocal()
    try:
        sankey = get_application_sankey_data(db)
        assert "nodes" in sankey
        assert "links" in sankey
        assert "total_transitions" in sankey
        assert len(sankey["nodes"]) > 0

        # Verify nodes structure
        node_names = [n["name"] for n in sankey["nodes"]]
        assert "Discovered" in node_names

        # Test API endpoint
        res = client.get("/api/analytics/sankey")
        assert res.status_code == 200
        assert "nodes" in res.json()
    finally:
        db.close()

# -------------------------------------------------------------
# 7. Assisted Application Workflow & Dossier
# -------------------------------------------------------------
def test_assisted_application_dossier_and_submission():
    db = SessionLocal()
    try:
        opp = db.query(Opportunity).first()
        assert opp is not None

        # 1. Prepare application dossier (POST)
        res_prep = client.post(f"/api/applications/prepare/{opp.id}")
        assert res_prep.status_code == 200
        dossier = res_prep.json()
        assert dossier["opportunity_id"] == opp.id
        assert dossier["company_name"] == opp.company_name
        assert dossier["draft_cover_letter"] is not None
        assert len(dossier["draft_cover_letter"]) > 50
        assert "applicant_info" in dossier
        assert "standard_questions" in dossier

        # 2. Submit assisted application with explicit authorization
        submit_payload = {
            "opportunity_id": opp.id,
            "submission_mode": "assisted",
            "notes": "Automated verified test submission",
            "submission_verified": True
        }
        res_sub = client.post("/api/applications/submit-assisted", json=submit_payload)
        assert res_sub.status_code == 200
        app_record = res_sub.json()
        assert app_record["opportunity_id"] == opp.id
        assert app_record["submission_mode"] == "assisted"
        assert app_record["submission_verified"] is True
    finally:
        db.close()

# -------------------------------------------------------------
# 8. CareerOS AI Chat Assistant Tools & Conversation Persistence
# -------------------------------------------------------------
def test_ai_chat_tools_and_conversation_persistence():
    db = SessionLocal()
    try:
        # 1. Tool execution: find matching internships
        res_tool = execute_chat_tool("find_matching_internships", {"query": "Intern", "limit": 3}, db)
        assert res_tool["count"] >= 1
        assert len(res_tool["opportunities"]) >= 1

        # 2. Tool execution: get application pipeline
        res_pipe = execute_chat_tool("get_application_pipeline", {}, db)
        assert "total_tracked" in res_pipe
        assert "stages" in res_pipe

        # 3. Tool execution: analyze skill gaps
        opp = db.query(Opportunity).first()
        res_gap = execute_chat_tool("analyze_skill_gaps", {"opportunity_id": opp.id}, db)
        assert "matching_skills" in res_gap
        assert "missing_skills" in res_gap

        # 4. Tool execution: draft outreach message
        res_outreach = execute_chat_tool("draft_outreach_message", {"opportunity_id": opp.id}, db)
        assert "outreach_message" in res_outreach
        assert len(res_outreach["outreach_message"]) > 20

        # 5. Conversation lifecycle via API
        res_conv = client.post("/api/chat/conversations", json={"title": "Test AI Pipeline Chat"})
        assert res_conv.status_code == 200
        conv_id = res_conv.json()["id"]

        # Send message
        res_msg = client.post(f"/api/chat/conversations/{conv_id}/messages", json={
            "content": "Can you check my application pipeline?"
        })
        assert res_msg.status_code == 200
        msg_data = res_msg.json()
        assert msg_data["conversation_id"] == conv_id
        assert msg_data["sender"] == "assistant"
        assert len(msg_data["content"]) > 0

        # Retrieve conversation detail
        res_detail = client.get(f"/api/chat/conversations/{conv_id}")
        assert res_detail.status_code == 200
        messages = res_detail.json()["messages"]
        assert len(messages) >= 2 # user + assistant

        # Clean up test conversation
        res_del = client.delete(f"/api/chat/conversations/{conv_id}")
        assert res_del.status_code == 200
    finally:
        db.close()

# -------------------------------------------------------------
# 9. Interview Journal Recording & Diagnosis
# -------------------------------------------------------------
def test_interview_journal_recording_and_ai_diagnosis():
    # 1. Create interview entry
    create_payload = {
        "company_name": "TestCorp Robotics",
        "round_name": "System Design Round 1",
        "round_type": "technical",
        "scheduled_at": datetime.utcnow().isoformat(),
        "performance_rating": 4,
        "difficulty_rating": 3,
        "questions_asked": [
            {"question": "How do you handle database indexing for range queries?", "candidate_answer": "I use B-Tree indexes on the timestamp column."}
        ],
        "notes": "Good discussion on PostgreSQL execution plans."
    }
    res_create = client.post("/api/interviews", json=create_payload)
    assert res_create.status_code == 200
    int_id = res_create.json()["id"]
    assert int_id is not None

    # 2. Trigger AI diagnosis
    res_diag = client.post(f"/api/interviews/{int_id}/ai-analysis")
    assert res_diag.status_code == 200
    diag_data = res_diag.json()
    assert "strengths" in diag_data
    assert "weaknesses" in diag_data

    # 3. Clean up
    res_del = client.delete(f"/api/interviews/{int_id}")
    assert res_del.status_code == 200
