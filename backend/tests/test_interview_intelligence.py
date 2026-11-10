import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models.opportunity import Opportunity
from backend.app.models.candidate import CandidateProfile
from backend.app.models.interview import InterviewJournalRecord
from backend.app.models.practice_session import MockPracticeSession

client = TestClient(app)

def test_interview_prep_generation():
    # 1. Fetch an opportunity from DB
    db = SessionLocal()
    opp = db.query(Opportunity).first()
    opp_id = opp.id if opp else 1
    db.close()

    res = client.get(f"/api/interviews/prep?opportunity_id={opp_id}")
    assert res.status_code == 200
    prep = res.json()

    assert "technical_questions" in prep
    assert len(prep["technical_questions"]) >= 4
    assert "dsa_questions" in prep
    assert len(prep["dsa_questions"]) >= 3
    assert "project_questions" in prep
    assert len(prep["project_questions"]) >= 1
    # Check that project questions tie to candidate evidence
    assert any("project_name" in q for q in prep["project_questions"])
    assert "behavioral_questions" in prep
    assert len(prep["behavioral_questions"]) >= 3
    assert "hr_questions" in prep
    assert len(prep["hr_questions"]) >= 3
    assert "company_topics" in prep
    assert len(prep["company_topics"]) >= 4

def test_interview_journal_enhanced_crud():
    # 1. Create a rich interview journal record
    create_payload = {
        "company_name": "Palantir Technologies",
        "role": "Forward Deployed Software Engineer Intern",
        "round_name": "System Architecture Deep Dive",
        "round_type": "technical",
        "interview_format": "virtual_video",
        "interview_date": datetime.utcnow().isoformat(),
        "topics_covered": ["Distributed Systems", "FastAPI", "Database Indexing", "Concurrency"],
        "confidence_level": 4,
        "difficulty_rating": 4,
        "performance_rating": 4,
        "interview_result": "passed",
        "interviewer_feedback": "Strong architectural explanations and proactive trade-off analysis.",
        "personal_notes": "Mentioned write amplification in B-Trees which impressed the tech lead.",
        "questions_asked": [
            {
                "question": "How do you handle race conditions during high-volume updates?",
                "user_answer": "Utilized SELECT FOR UPDATE and optimistic concurrency with version integers.",
                "topic": "Concurrency",
                "confidence": 4
            }
        ]
    }
    create_res = client.post("/api/interviews", json=create_payload)
    assert create_res.status_code == 200
    created = create_res.json()
    entry_id = created["id"]
    assert created["role"] == "Forward Deployed Software Engineer Intern"
    assert created["interview_format"] == "virtual_video"
    assert created["interview_result"] == "passed"
    assert "Distributed Systems" in created["topics_covered"]
    assert created["interviewer_feedback"] == "Strong architectural explanations and proactive trade-off analysis."

    # 2. Retrieve by ID
    get_res = client.get(f"/api/interviews/{entry_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == entry_id

    # 3. Update entry
    update_res = client.put(f"/api/interviews/{entry_id}", json={
        "interview_result": "offer",
        "confidence_level": 5
    })
    assert update_res.status_code == 200
    assert update_res.json()["interview_result"] == "offer"
    assert update_res.json()["confidence_level"] == 5

    # 4. Clean up
    del_res = client.delete(f"/api/interviews/{entry_id}")
    assert del_res.status_code == 200
    assert del_res.json()["message"] == "Interview journal entry deleted"

def test_mock_practice_simulator_lifecycle():
    # 1. Start a new mock practice session
    create_res = client.post("/api/interviews/practice/sessions", json={
        "session_title": "Backend Engineering Simulation",
        "session_type": "technical"
    })
    assert create_res.status_code == 200
    session_data = create_res.json()
    session_id = session_data["id"]
    assert session_data["status"] == "in_progress"
    assert len(session_data["questions"]) >= 3
    q1_id = session_data["questions"][0]["id"]

    # 2. Submit candidate answer for question 1
    eval_res = client.post(f"/api/interviews/practice/sessions/{session_id}/evaluate-question", json={
        "question_id": q1_id,
        "user_answer": "Python uses an event loop managed by asyncio where tasks yield control during I/O operations. When CPU-bound tasks block the main thread, we offload to run_in_executor to avoid starvation."
    })
    assert eval_res.status_code == 200
    eval_data = eval_res.json()
    assert eval_data["question_id"] == q1_id
    evaluation = eval_data["evaluation"]
    assert evaluation["evaluation_type"] == "ai_generated_evaluation"
    assert "score" in evaluation
    assert evaluation["score"] >= 60
    assert "strengths" in evaluation
    assert "improvement_areas" in evaluation
    assert "ideal_answer_points" in evaluation

    # 3. Retrieve session details
    detail_res = client.get(f"/api/interviews/practice/sessions/{session_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["questions"][0]["user_answer"] is not None
    assert detail["questions"][0]["ai_evaluation"] is not None

    # 4. Complete practice session
    complete_res = client.post(f"/api/interviews/practice/sessions/{session_id}/complete")
    assert complete_res.status_code == 200
    completed = complete_res.json()
    assert completed["status"] == "completed"
    assert completed["overall_score"] is not None
    assert "ai_session_summary" in completed
    assert completed["completed_at"] is not None

def test_historical_interview_analytics():
    # 1. Fetch analytics (handles both zero-state and populated state)
    res = client.get("/api/interviews/analytics")
    assert res.status_code == 200
    analytics = res.json()

    assert "total_interviews" in analytics
    assert "funnel_metrics" in analytics
    assert "repeatedly_difficult_topics" in analytics
    assert "strong_technical_areas" in analytics
    assert "communication_improvement_areas" in analytics
    assert "preparation_priorities" in analytics
