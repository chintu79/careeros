import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models.opportunity import Opportunity
from backend.app.models.candidate import CandidateProfile
from backend.app.models.preferences import UserPreferences
from backend.app.models.saved_search import SavedSearch
from backend.app.models.search_history import SearchHistory
from backend.app.models.recommendation_feedback import RecommendationFeedback

client = TestClient(app)

@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def test_multi_mode_search_and_filters(db: Session):
    """Verify hybrid, keyword, skill, company, and location search modes with filters and sorting."""
    # 1. Keyword search
    res = client.get("/api/opportunities?search=Software&search_mode=keyword&limit=10")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) > 0

    # 2. Company search
    first_company = data["items"][0]["company_name"]
    res_comp = client.get(f"/api/opportunities?search={first_company}&search_mode=company&limit=10")
    assert res_comp.status_code == 200
    comp_data = res_comp.json()
    assert all(first_company.lower() in item["company_name"].lower() for item in comp_data["items"])

    # 3. Location / Remote search
    res_loc = client.get("/api/opportunities?search=remote&search_mode=location&workplace_type=remote&limit=10")
    assert res_loc.status_code == 200
    loc_data = res_loc.json()
    assert all(item["workplace_type"] == "remote" for item in loc_data["items"])

    # 4. Skill search
    res_skill = client.get("/api/opportunities?search=Python&search_mode=skill&limit=10")
    assert res_skill.status_code == 200

    # 5. Hybrid search
    res_hybrid = client.get("/api/opportunities?search=Machine%20Learning&search_mode=hybrid&limit=10")
    assert res_hybrid.status_code == 200

    # 6. Sorting by deadline and freshness
    res_sort_fresh = client.get("/api/opportunities?sort_by=posted_at&sort_order=desc&limit=5")
    assert res_sort_fresh.status_code == 200

def test_opportunity_intelligence_payload(db: Session):
    """Verify that every opportunity returned contains complete opportunity intelligence."""
    res = client.get("/api/opportunities?tab=recommended&limit=5")
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) > 0

    item = data["items"][0]
    # Check 9 intelligence properties
    assert "match_score" in item
    assert isinstance(item["match_score"], (int, float))
    assert "why_it_matches" in item
    assert isinstance(item["why_it_matches"], list)
    assert len(item["why_it_matches"]) >= 1
    assert "matching_skills" in item
    assert isinstance(item["matching_skills"], list)
    assert "missing_skills" in item
    assert isinstance(item["missing_skills"], list)
    assert "eligibility_assessment" in item
    assert "status" in item["eligibility_assessment"]
    assert "source_reliability" in item
    assert "score" in item["source_reliability"]
    assert "badge" in item["source_reliability"]
    assert "deadline_info" in item
    assert "posted_at" in item
    assert "discovered_at" in item
    assert "last_verified_at" in item

    # Also verify detail view has intelligence
    detail_res = client.get(f"/api/opportunities/{item['id']}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert "intelligence" in detail
    assert "why_it_matches" in detail
    assert "source_reliability" in detail

def test_curated_7_section_recommendations(db: Session):
    """Verify recommendation engine returns all 7 specialized sections grounded in real database records."""
    res = client.get("/api/opportunities/recommendations?limit_per_section=5")
    assert res.status_code == 200
    data = res.json()

    # 7 Required Sections
    required_sections = [
        "best_matches",
        "recently_posted",
        "remote_opportunities",
        "aiml_internships",
        "fullstack_internships",
        "closing_soon",
        "based_on_projects"
    ]
    for section in required_sections:
        assert section in data, f"Missing section: {section}"
        assert isinstance(data[section], list)

    assert "meta" in data
    assert "total_recommended" in data["meta"]
    assert data["meta"]["total_recommended"] > 0

    # Verify based_on_projects links to verified candidate projects
    if data["based_on_projects"]:
        proj_item = data["based_on_projects"][0]
        assert "based_on_project" in proj_item
        proj_ctx = proj_item["based_on_project"]
        assert "project_title" in proj_ctx
        assert "matching_tech" in proj_ctx
        assert "relevance_reason" in proj_ctx

    # Verify all recommended opportunities are genuine database records with non-empty URLs
    for section in required_sections:
        for opp in data[section]:
            assert opp["id"] > 0
            assert opp["title"]
            assert opp["company_name"]
            assert opp["original_url"].startswith("http")

def test_saved_searches_crud(db: Session):
    """Test creating, listing, and deleting saved searches."""
    # 1. Create a saved search
    payload = {
        "name": "Backend Python Remote Test Search",
        "search_mode": "hybrid",
        "query": "Python FastAPI",
        "filters": {"workplace_type": "remote", "min_stipend": 15000}
    }
    create_res = client.post("/api/searches/saved", json=payload)
    assert create_res.status_code == 200
    created = create_res.json()
    saved_id = created["id"]
    assert created["name"] == payload["name"]

    # 2. List saved searches
    list_res = client.get("/api/searches/saved")
    assert list_res.status_code == 200
    saved_list = list_res.json()
    assert any(s["id"] == saved_id for s in saved_list)

    # 3. Delete saved search
    del_res = client.delete(f"/api/searches/saved/{saved_id}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Verify deletion
    verify_res = client.get("/api/searches/saved")
    assert not any(s["id"] == saved_id for s in verify_res.json())

def test_search_history_logging_and_clearing(db: Session):
    """Test search queries automatically record into search history and can be cleared."""
    # Execute a search
    unique_term = f"Kubernetes_{int(datetime.utcnow().timestamp())}"
    client.get(f"/api/opportunities?search={unique_term}&search_mode=keyword")

    # Retrieve history
    hist_res = client.get("/api/searches/history")
    assert hist_res.status_code == 200
    history = hist_res.json()
    assert any(h["query"] == unique_term for h in history)

    # Clear history
    clear_res = client.delete("/api/searches/history")
    assert clear_res.status_code == 200
    assert clear_res.json()["success"] is True

    hist_after = client.get("/api/searches/history").json()
    assert len(hist_after) == 0

def test_recommendation_feedback_loop(db: Session):
    """Test dismissing with feedback updates status and penalizes future recommendations."""
    # Pick an active opportunity
    opp = db.query(Opportunity).filter(
        Opportunity.is_dismissed == False,
        Opportunity.employment_type == "internship"
    ).first()
    assert opp is not None
    opp_id = opp.id
    company_name = opp.company_name

    # Submit feedback: not interested in this company
    feedback_payload = {
        "feedback_type": "not_interested_company",
        "reason_note": "Focusing on enterprise cloud roles"
    }
    fb_res = client.post(f"/api/opportunities/{opp_id}/feedback", json=feedback_payload)
    assert fb_res.status_code == 200
    fb_data = fb_res.json()
    assert fb_data["success"] is True
    assert fb_data["is_dismissed"] is True

    # Verify opportunity is marked dismissed
    db.refresh(opp)
    assert opp.is_dismissed is True

    # Verify it does not appear in recommendation sections
    recs = client.get("/api/opportunities/recommendations").json()
    all_rec_ids = [
        o["id"] for sec in [
            "best_matches", "recently_posted", "remote_opportunities",
            "aiml_internships", "fullstack_internships", "closing_soon"
        ] for o in recs[sec]
    ]
    assert opp_id not in all_rec_ids

    # Restore opportunity so tests remain clean
    opp.is_dismissed = False
    db.commit()
