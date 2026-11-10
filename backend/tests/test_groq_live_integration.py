import os
import time
import pytest
from backend.app.config import settings
from backend.app.services.ai.service import (
    CentralizedAIService, 
    ResumeTailoringOutput,
    validate_tailoring_safety
)
from backend.app.services.ai.groq_adapter import GroqAdapter
from backend.app.services.ai.task_router import TaskRouter


@pytest.mark.asyncio
async def test_live_groq_inference_connectivity_and_safety_pipeline():
    """
    Genuine live integration test verifying direct connectivity to Groq API.
    Requirements:
    - Opt-in based on GROQ_API_KEY in environment.
    - If GROQ_API_KEY is not configured or placeholder: marks test as SKIPPED.
    - Never logs or exposes the API key.
    - Uses minimal synthetic candidate and opportunity data (never real user data).
    - Validates response schema with ResumeTailoringOutput.
    - Verifies response through validate_tailoring_safety() pipeline.
    - Records and asserts latency and token usage.
    """
    api_key = settings.GROQ_API_KEY
    if not api_key or api_key.strip() == "" or api_key.startswith("your_groq_api_key"):
        pytest.skip("GROQ_API_KEY is not configured in backend environment. Skipping live Groq test.")

    model = settings.GROQ_MODEL
    # Initialize live adapter with real credentials and configured model
    adapter = GroqAdapter(api_key=api_key, model=model)
    is_avail, avail_msg = adapter.is_available()
    assert is_avail is True, f"Groq adapter reports unavailable: {avail_msg}"

    router = TaskRouter(groq_adapter=adapter)
    service = CentralizedAIService(task_router=router)

    # 1. Minimal synthetic data (strictly no PII or real user records)
    synthetic_candidate = {
        "name": "Synthetic Candidate 101",
        "degree": "B.S. Computer Engineering",
        "skills": [
            {"name": "Python", "level": "advanced", "category": "language"},
            {"name": "FastAPI", "level": "intermediate", "category": "framework"}
        ],
        "projects": [
            {
                "title": "Synthetic Async REST Gateway",
                "technologies": ["Python", "FastAPI"],
                "bullets": ["Engineered high-throughput asynchronous HTTP gateway."]
            }
        ],
        "experience": []
    }

    synthetic_opportunity = {
        "title": "Backend Systems Engineer",
        "company_name": "Synthetic Cloud Corp",
        "description": "Seeking a Backend Systems Engineer skilled in Python and FastAPI to build reliable cloud services with Docker.",
        "required_skills": ["Python", "FastAPI", "Docker"],
        "preferred_skills": ["PostgreSQL"]
    }

    synthetic_latex_stub = (
        r"\documentclass{article}"
        r"\begin{document}"
        r"Synthetic Candidate - Python Developer"
        r"\end{document}"
    )

    # 2. Genuine request to Groq
    start_time = time.time()
    result = await service.tailor_resume(
        resume_latex=synthetic_latex_stub,
        opportunity_data=synthetic_opportunity,
        profile_data=synthetic_candidate
    )
    elapsed_ms = (time.time() - start_time) * 1000

    # 3. Verify response success and provider details
    assert result is not None, "Provider returned None"
    assert result.get("success") is True, f"Live Groq request failed: {result.get('error')}"
    assert result.get("provider") == "groq"
    assert result.get("model") == model

    # 4. Telemetry verification: latency and token usage
    latency_ms = result.get("latency_ms")
    assert latency_ms is not None and latency_ms > 0, "Expected positive latency telemetry"
    assert elapsed_ms < 30000, "Live Groq request exceeded 30s timeout threshold"

    tokens = result.get("tokens")
    assert tokens is not None and tokens > 0, "Expected positive token count from Groq completion"

    # 5. Schema validation via ResumeTailoringOutput
    tailoring_data = result.get("data")
    assert tailoring_data is not None, "Missing data payload in successful response"
    validated = ResumeTailoringOutput.model_validate(tailoring_data)
    assert isinstance(validated.matched_skills, list)
    assert isinstance(validated.missing_skills, list)
    assert isinstance(validated.bullet_refinements, list)

    # 6. Verify Zero-Fabrication safety pipeline
    safe_data = validate_tailoring_safety(
        tailoring_data=tailoring_data,
        candidate_skills=synthetic_candidate["skills"],
        candidate_projects=synthetic_candidate["projects"],
        candidate_experience=synthetic_candidate["experience"]
    )

    # Candidate has Python and FastAPI, but does NOT have Docker
    # Matched skills in safe_data must only contain verified skills
    for skill in safe_data.get("matched_skills", []):
        assert skill.lower() in ["python", "fastapi"], f"Hallucinated skill escaped safety filter: {skill}"

    # Docker must NOT be in matched_skills (must be dropped or in missing_skills)
    assert "Docker" not in safe_data.get("matched_skills", []), "Unverified skill allowed in matched_skills"
