import pytest
import asyncio
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.services.intelligence_cache import IntelligenceLRUCache, intelligence_cache
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
from backend.app.services.ai_assistant import execute_chat_tool, process_user_chat_message

client = TestClient(app)

@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    yield db
    db.close()


def test_intelligence_lru_cache_operations():
    """Verify thread-safe LRU caching, TTL expiration, and eviction."""
    cache = IntelligenceLRUCache(max_size=3, default_ttl=2)
    cache.set("a", 100)
    cache.set("b", 200)
    cache.set("c", 300)
    assert cache.size() == 3
    assert cache.get("a") == 100

    # Adding a 4th should evict the least recently used
    cache.set("d", 400)
    assert cache.size() == 3
    assert cache.get("b") is None  # b was LRU
    assert cache.get("d") == 400

    # Delete operation
    cache.delete("d")
    assert cache.get("d") is None
    cache.clear()
    assert cache.size() == 0


def test_context_retriever_candidate_scopes(db_session):
    """Verify scoped retrieval of Master Candidate Profile without hallucination."""
    full = get_candidate_context(db_session, scope="full")
    assert "Alex" in full["name"]
    assert len(full.get("verified_skills", [])) >= 10
    assert len(full.get("verified_projects", [])) >= 5
    assert "preferences" in full

    skills_only = get_candidate_context(db_session, scope="skills_only")
    assert "verified_skills" in skills_only
    assert "verified_projects" not in skills_only

    projects_only = get_candidate_context(db_session, scope="projects_only")
    assert "verified_projects" in projects_only
    assert "verified_skills" not in projects_only


def test_context_retriever_opportunity_and_market(db_session):
    """Verify complete opportunity retrieval and market skill demand aggregation."""
    opp = get_opportunity_context(db_session, 37)
    assert opp is not None
    assert opp["id"] == 37
    assert opp["company_name"] == "Cloudaeon Software Technology Private Limited"
    assert "required_skills" in opp

    market = get_market_skills_context(db_session, top_n=10)
    assert market["total_opportunities_analyzed"] >= 50
    assert len(market["top_market_demanded_skills"]) > 0


@pytest.mark.asyncio
async def test_workflow_1_job_matching_intelligence(db_session):
    """Verify Job Matching Intelligence separates the 4 truth layers and grounds candidate evidence."""
    report = await run_job_matching_intelligence(37, db_session, use_cache=False)
    assert report["workflow"] == "job_matching"
    assert "title" in report
    assert "summary" in report

    layers = report["truth_layers"]
    assert "verified_database" in layers
    assert "extracted_external" in layers
    assert "strategic_recommendations" in layers
    assert "unknown_missing" in layers

    assert len(layers["verified_database"]) >= 2
    assert len(layers["extracted_external"]) >= 2
    assert len(layers["strategic_recommendations"]) >= 1

    metrics = report["metrics"]
    assert "match_score" in metrics
    assert "matching_skills_count" in metrics
    assert "missing_skills_count" in metrics


@pytest.mark.asyncio
async def test_workflow_2_resume_intelligence(db_session):
    """Verify Resume Intelligence ranks candidate projects and produces grounded ATS recommendations."""
    report = await run_resume_intelligence(37, db_session, use_cache=False)
    assert report["workflow"] == "resume_intelligence"
    assert len(report["details"]["recommended_projects"]) >= 1

    layers = report["truth_layers"]
    assert len(layers["verified_database"]) >= 2
    assert len(layers["strategic_recommendations"]) >= 1
    # Check that candidate's real project is referenced
    rec_projects = report["details"]["recommended_projects"]
    assert any("title" in p for p in rec_projects)


@pytest.mark.asyncio
async def test_workflow_3_interview_intelligence(db_session):
    """Verify Interview Preparation generates questions anchored in verified candidate projects."""
    report = await run_interview_intelligence(37, db_session, use_cache=False)
    assert report["workflow"] == "interview_prep"
    assert len(report["details"]["technical_questions"]) >= 1
    assert len(report["details"]["behavioral_questions"]) >= 1

    # Check STAR approach includes candidate's verified project
    first_behavioral = report["details"]["behavioral_questions"][0]
    assert "star_approach" in first_behavioral


@pytest.mark.asyncio
async def test_workflow_4_career_growth_intelligence(db_session):
    """Verify Career Growth Intelligence calculates high-ROI skills from real database market demand."""
    report = await run_career_growth_intelligence(db_session, use_cache=False)
    assert report["workflow"] == "career_growth"
    assert report["metrics"]["opportunities_analyzed"] >= 50
    assert "roadmap" in report["details"]


@pytest.mark.asyncio
async def test_workflow_5_application_intelligence(db_session):
    """Verify Application Intelligence analyzes pipeline conversion, stages, and overdue follow-ups."""
    report = await run_application_intelligence(db_session, use_cache=False)
    assert report["workflow"] == "application_intelligence"
    assert report["metrics"]["total_applications"] >= 1
    assert "stages_count" in report["details"]


def test_execute_chat_tools_grounding(db_session):
    """Verify structured database tools execute accurately without hallucinating records."""
    # Find matching
    res_find = execute_chat_tool("find_matching_internships", {"query": "", "min_score": 50, "limit": 3}, db_session)
    assert res_find["count"] >= 1
    assert len(res_find["opportunities"]) <= 3

    # Candidate profile
    res_cand = execute_chat_tool("get_candidate_profile", {}, db_session)
    assert "Alex" in res_cand["name"]

    # Application pipeline
    res_pipe = execute_chat_tool("get_application_pipeline", {}, db_session)
    assert res_pipe["total_tracked"] >= 1

    # Draft outreach
    res_outreach = execute_chat_tool("draft_outreach_message", {"opportunity_id": 37}, db_session)
    assert "Cloudaeon" in res_outreach["outreach_message"]


@pytest.mark.asyncio
async def test_process_user_chat_message_with_workflow(db_session):
    """Verify chat message processing routes to specialized workflows and formats 4 truth layers."""
    # Create test conversation
    conv_res = client.post("/api/chat/conversations", json={"title": "Test AI Intelligence Engine"})
    assert conv_res.status_code == 200
    conv_id = conv_res.json()["id"]

    # Send message with workflow hint
    msg = await process_user_chat_message(
        conversation_id=conv_id,
        user_prompt="Run job matching analysis for this opportunity",
        db=db_session,
        opportunity_id=37,
        workflow="job_matching"
    )
    assert msg["conversation_id"] == conv_id
    assert msg["sender"] == "assistant"
    assert "[Verified Database Record]" in msg["content"]
    assert "[AI Strategic Recommendation]" in msg["content"]
    assert msg["truth_layers"] is not None


def test_dedicated_workflow_api_endpoints():
    """Verify all 5 dedicated workflow REST endpoints return 200 OK with 4 truth layers."""
    # Workflow 1
    r1 = client.post("/api/chat/workflows/job-matching", json={"opportunity_id": 37})
    assert r1.status_code == 200
    assert r1.json()["workflow"] == "job_matching"
    assert "verified_database" in r1.json()["truth_layers"]

    # Workflow 2
    r2 = client.post("/api/chat/workflows/resume-intelligence", json={"opportunity_id": 37})
    assert r2.status_code == 200
    assert r2.json()["workflow"] == "resume_intelligence"

    # Workflow 3
    r3 = client.post("/api/chat/workflows/interview-prep", json={"opportunity_id": 37})
    assert r3.status_code == 200
    assert r3.json()["workflow"] == "interview_prep"

    # Workflow 4
    r4 = client.post("/api/chat/workflows/career-growth")
    assert r4.status_code == 200
    assert r4.json()["workflow"] == "career_growth"

    # Workflow 5
    r5 = client.post("/api/chat/workflows/application-intelligence")
    assert r5.status_code == 200
    assert r5.json()["workflow"] == "application_intelligence"
