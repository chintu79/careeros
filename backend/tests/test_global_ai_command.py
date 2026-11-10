import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models.application import ApplicationRecord
from backend.app.models.opportunity import Opportunity
from backend.app.models.ai_audit import AIActionAuditLog

client = TestClient(app)


def test_get_permitted_tools():
    """Verify tool registry endpoint returns strictly permitted structured tools."""
    resp = client.get("/api/ai/command/tools")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 10
    tool_names = [t["name"] for t in data["tools"]]
    assert "search_opportunities" in tool_names
    assert "compare_opportunities" in tool_names
    assert "get_follow_up_applications" in tool_names
    assert "update_application_status" in tool_names
    assert "prepare_tailored_resume" in tool_names
    assert "show_strongest_technical_skills" in tool_names


def test_get_context_suggestions():
    """Verify dynamic context suggestions endpoint returns quick prompts."""
    resp = client.get("/api/ai/command/suggestions")
    assert resp.status_code == 200
    data = resp.json()
    assert "suggestions" in data
    assert len(data["suggestions"]) >= 4
    prompts = [s["prompt"] for s in data["suggestions"]]
    assert any("Find AI internships" in p for p in prompts)
    assert any("follow-up" in p for p in prompts)


def test_search_opportunities_command():
    """Verify 'Find AI internships matching my profile' returns grounded opportunities with truth layers."""
    resp = client.post("/api/ai/command/message", json={
        "content": "Find AI internships matching my profile."
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["tool_executed"] == "search_opportunities"
    assert data["is_consequential"] is False
    assert "🟢 [Verified Database Record]" in data["content"]
    assert "matching opportunities" in data["content"]
    assert len(data["suggested_actions"]) > 0


def test_compare_opportunities_command():
    """Verify 'Compare these three opportunities' runs comparative intelligence matrix."""
    resp = client.post("/api/ai/command/message", json={
        "content": "Compare these three opportunities."
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["tool_executed"] == "compare_opportunities"
    assert "🟢 [Verified Database Record]" in data["content"]
    assert "Side-by-side comparison" in data["content"]


def test_follow_up_applications_command():
    """Verify 'Which applications need follow-up?' surfaces pipeline health audit."""
    resp = client.post("/api/ai/command/message", json={
        "content": "Which applications need follow-up?"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["tool_executed"] == "get_follow_up_applications"
    assert "🟢 [Verified Database Record]" in data["content"]
    assert "Pipeline Health & Follow-Up Audit" in data["content"]


def test_show_strongest_technical_skills_command():
    """Verify 'Show my strongest technical skills' extracts verified competencies from profile."""
    resp = client.post("/api/ai/command/message", json={
        "content": "Show my strongest technical skills."
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["tool_executed"] == "show_strongest_technical_skills"
    assert "Master Candidate Profile Competencies" in data["content"]
    assert "portfolio projects" in data["content"]


def test_find_matching_projects_command():
    """Verify 'Find projects from my GitHub that match this job' maps verified projects to job requirements."""
    resp = client.post("/api/ai/command/message", json={
        "content": "Find projects from my GitHub that match this job."
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["tool_executed"] == "find_matching_projects_for_job"
    assert "Matching Projects" in data["content"]
    assert "relevance" in data["content"]


def test_consequential_action_approval_lifecycle():
    """
    Test consequential operation protocol:
    1. Issue command to update application status.
    2. Verify AI produces 'pending_approval' proposal.
    3. Verify database is NOT mutated before approval.
    4. Call approve endpoint.
    5. Verify database IS mutated and audit log marks executed.
    """
    db = SessionLocal()
    try:
        app = db.query(ApplicationRecord).first()
        assert app is not None
        target_app_id = app.id
        original_status = app.status
        new_target_status = "screening" if original_status != "screening" else "applied"
    finally:
        db.close()

    # Step 1: Issue command
    resp = client.post("/api/ai/command/message", json={
        "content": f"Update application #{target_app_id} to {new_target_status}"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_consequential"] is True
    proposal = data.get("action_proposal")
    assert proposal is not None
    assert proposal["status"] == "pending_approval"
    assert proposal["requires_approval"] is True
    action_id = proposal["action_id"]

    # Step 2: Verify database state was NOT changed prematurely
    db = SessionLocal()
    try:
        app_check = db.query(ApplicationRecord).filter(ApplicationRecord.id == target_app_id).first()
        assert app_check.status == original_status
    finally:
        db.close()

    # Step 3: Approve & Execute action
    exec_resp = client.post(f"/api/ai/command/actions/{action_id}/execute")
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert exec_data["status"] == "executed"
    assert exec_data["success"] is True

    # Step 4: Verify database was updated and transition logged
    db = SessionLocal()
    try:
        app_updated = db.query(ApplicationRecord).filter(ApplicationRecord.id == target_app_id).first()
        assert app_updated.status == new_target_status

        audit_check = db.query(AIActionAuditLog).filter(AIActionAuditLog.id == action_id).first()
        assert audit_check.status == "executed"
        assert audit_check.user_confirmed is True
        assert audit_check.executed_at is not None
    finally:
        db.close()


def test_consequential_action_rejection():
    """Verify user can explicitly reject a proposed consequential action without mutating database."""
    db = SessionLocal()
    try:
        app = db.query(ApplicationRecord).first()
        target_app_id = app.id
        original_status = app.status
        candidate_status = "rejected" if original_status != "rejected" else "withdrawn"
    finally:
        db.close()

    # Propose action
    resp = client.post("/api/ai/command/message", json={
        "content": f"Move application #{target_app_id} to {candidate_status}"
    })
    assert resp.status_code == 200
    action_id = resp.json()["action_proposal"]["action_id"]

    # Reject action
    reject_resp = client.post(f"/api/ai/command/actions/{action_id}/reject", json={
        "reason": "Not ready to reject this role yet."
    })
    assert reject_resp.status_code == 200
    reject_data = reject_resp.json()
    assert reject_data["status"] == "rejected"

    # Verify status unchanged
    db = SessionLocal()
    try:
        app_check = db.query(ApplicationRecord).filter(ApplicationRecord.id == target_app_id).first()
        assert app_check.status == original_status

        audit = db.query(AIActionAuditLog).filter(AIActionAuditLog.id == action_id).first()
        assert audit.status == "rejected"
        assert audit.user_confirmed is False
    finally:
        db.close()


def test_audit_log_endpoint():
    """Verify audit log endpoint returns logged actions and approval states."""
    resp = client.get("/api/ai/command/audit-log")
    assert resp.status_code == 200
    data = resp.json()
    assert "logs" in data
    assert data["count"] >= 1
