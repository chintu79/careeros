import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.integration_service import parse_resume_file

SAMPLE_RESUME_TEXT = """Jane Doe
jane.doe@example.com | +1 (555) 123-4567 | San Francisco, CA
https://github.com/janedoe | https://linkedin.com/in/janedoe | https://janedoe.dev

EDUCATION
University of California, Berkeley
B.Tech in Computer Science | CGPA: 3.88 | Class of 2025

TECHNICAL SKILLS
Languages: Python, TypeScript, Go, C++, SQL
Frameworks: React, Next.js, FastAPI, Node.js
DevOps & Tools: Docker, Kubernetes, AWS, Git, Linux, PostgreSQL, Redis

PROJECTS
CareerOS Navigator | Full Stack Job Platform
- Built reactive internship search platform using React, FastAPI, and PostgreSQL.
- Implemented asynchronous ingestion pipelines with Docker and Redis caching.

Cloud Task Orchestrator
- Engineered distributed task runner in Go and AWS with automated retry policies.
"""

def test_parse_resume_plaintext():
    content = SAMPLE_RESUME_TEXT.encode("utf-8")
    result = parse_resume_file(content, filename="resume.txt")
    
    draft = result["candidate_draft"]
    assert draft["name"] == "Jane Doe"
    assert draft["email"] == "jane.doe@example.com"
    assert "555" in draft["phone"]
    assert "Berkeley" in draft["college"]
    assert draft["degree"] == "B.Tech"
    assert draft["graduation_year"] == 2025
    assert draft["cgpa"] == 3.88
    assert "janedoe" in draft["github_url"]
    assert "janedoe" in draft["linkedin_url"]
    assert "janedoe.dev" in draft["portfolio_url"]
    
    skill_names = [s["name"] for s in result["detected_skills"]]
    assert "Python" in skill_names
    assert "FastAPI" in skill_names
    assert "React" in skill_names
    assert "PostgreSQL" in skill_names
    assert "Docker" in skill_names
    
    assert len(result["detected_projects"]) >= 1
    proj_titles = [p["title"] for p in result["detected_projects"]]
    assert any("CareerOS" in t or "Navigator" in t for t in proj_titles)


def test_parse_resume_endpoint():
    client = TestClient(app)
    files = {
        "file": ("jane_doe_resume.txt", SAMPLE_RESUME_TEXT.encode("utf-8"), "text/plain")
    }
    resp = client.post("/api/candidate/integrations/parse-resume", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["candidate_draft"]["email"] == "jane.doe@example.com"
    assert len(data["detected_skills"]) > 5
    assert len(data["detected_projects"]) >= 1


def test_approve_integrations_with_candidate_updates():
    from backend.app.core.auth import create_access_token
    user_id = 99999
    token = create_access_token(user_id=user_id)
    headers = {"Authorization": f"Bearer {token}"}
    client = TestClient(app)
    # Ensure profile exists for this test user
    client.get("/api/candidate", headers=headers)

    payload = {
        "candidate_updates": {
            "bio": "Passionate systems and backend engineer specializing in distributed architectures."
        },
        "approved_skills": [
            {
                "name": "Rust",
                "level": "intermediate",
                "category": "Language",
                "evidence": "Approved from resume extraction"
            }
        ],
        "approved_projects": [
            {
                "title": "Distributed Key-Value Store",
                "description": "Raft consensus implementation in Rust.",
                "tech_stack": ["Rust", "Raft", "Distributed Systems"],
                "url": "https://github.com/janedoe/kv-store"
            }
        ]
    }
    resp = client.post("/api/candidate/integrations/approve", json=payload, headers=headers)
    assert resp.status_code == 200
    updated_profile = resp.json()
    assert updated_profile["bio"] == "Passionate systems and backend engineer specializing in distributed architectures."
    skill_names = [s["name"] for s in updated_profile["skills"]]
    assert "Rust" in skill_names
    proj_titles = [p["title"] for p in updated_profile["projects"]]
    assert "Distributed Key-Value Store" in proj_titles
