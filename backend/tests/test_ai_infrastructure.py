import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from pydantic import BaseModel

from backend.app.main import app
from backend.app.config import settings
from backend.app.services.ai.types import (
    ProviderType,
    TaskType,
    ModelResponse,
    AIProviderError,
    GroqProviderError,
    OllamaProviderError,
    RateLimitError,
    ProviderUnavailableError,
    StructuredOutputValidationError,
    CrossProviderLeakageViolation
)
from backend.app.services.ai.telemetry import AITelemetryTracker, telemetry
from backend.app.services.ai.groq_adapter import GroqAdapter
from backend.app.services.ai.ollama_adapter import OllamaAdapter
from backend.app.services.ai.task_router import TaskRouter, TASK_ROUTING_MAP
from backend.app.services.ai.service import (
    CentralizedAIService,
    ResumeTailoringOutput,
    JobDescriptionAnalysisOutput,
    InterviewEvaluationOutput
)

client = TestClient(app)


# --- 1. Configuration & Safe Defaults ---

def test_configuration_and_defaults():
    assert settings.GROQ_MODEL != ""
    assert any(m in settings.GROQ_MODEL.lower() for m in ["llama", "mixtral", "openai", "gpt"])
    assert settings.OLLAMA_BASE_URL.startswith("http")
    assert settings.OLLAMA_CHAT_MODEL != ""


# --- 2. Groq Adapter: Unconfigured State & Error Handling ---

@pytest.mark.asyncio
async def test_groq_adapter_unconfigured_error():
    adapter = GroqAdapter(api_key="")
    available, msg = adapter.is_available()
    assert available is False
    assert "not configured" in msg

    with pytest.raises(ProviderUnavailableError) as exc_info:
        await adapter.generate("Test prompt")
    assert "GROQ_API_KEY is not configured" in str(exc_info.value)
    assert exc_info.value.retryable is False


# --- 3. Groq Adapter: Structured JSON Schema Validation ---

class SampleTestSchema(BaseModel):
    title: str
    skills: list[str]
    score: int


@pytest.mark.asyncio
async def test_groq_adapter_structured_json_validation():
    adapter = GroqAdapter(api_key="gsk_mock_test_key_12345")

    # Mock client and response
    mock_resp = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = '{"title": "Backend Intern", "skills": ["Python", "FastAPI"], "score": 95}'
    mock_choice.finish_reason = "stop"
    mock_resp.choices = [mock_choice]
    mock_resp.usage = MagicMock(prompt_tokens=42, completion_tokens=18, total_tokens=60)

    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_resp
    adapter._client = mock_client

    res = await adapter.generate(
        prompt="Analyze backend intern",
        response_schema=SampleTestSchema,
        task_name="test_schema_validation"
    )

    assert isinstance(res, ModelResponse)
    assert res.provider == ProviderType.GROQ
    assert res.prompt_tokens == 42
    assert res.completion_tokens == 18
    assert res.total_tokens == 60
    assert res.parsed_json is not None
    assert res.parsed_json["title"] == "Backend Intern"
    assert res.parsed_json["skills"] == ["Python", "FastAPI"]
    assert res.parsed_json["score"] == 95


@pytest.mark.asyncio
async def test_groq_adapter_schema_validation_failure():
    adapter = GroqAdapter(api_key="gsk_mock_test_key_12345")

    mock_resp = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = '{"title": "Missing required fields"}'
    mock_choice.finish_reason = "stop"
    mock_resp.choices = [mock_choice]
    mock_resp.usage = None

    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_resp
    adapter._client = mock_client

    with pytest.raises(StructuredOutputValidationError) as exc_info:
        await adapter.generate(
            prompt="Analyze role",
            response_schema=SampleTestSchema,
            task_name="test_schema_fail"
        )
    assert exc_info.value.retryable is True


# --- 4. Ollama Adapter: Live Health Check against Local Daemon ---

@pytest.mark.asyncio
async def test_ollama_adapter_live_health():
    adapter = OllamaAdapter()
    available, msg = await adapter.is_available()
    assert available is True
    assert "Running locally" in msg or "Daemon running" in msg


# --- 5. Ollama Adapter: Live Streaming Chat ---

@pytest.mark.asyncio
async def test_ollama_adapter_live_streaming():
    adapter = OllamaAdapter()
    tokens = []
    messages = [{"role": "user", "content": "Respond with the single word: OK"}]

    try:
        async for token in adapter.stream_chat(messages, system_prompt="Answer briefly.", temperature=0.1):
            tokens.append(token)
            if len(tokens) >= 5:
                break
    except Exception as e:
        pytest.skip(f"Skipping live stream test if Ollama daemon is busy: {e}")

    assert len(tokens) > 0
    full_text = "".join(tokens)
    assert len(full_text.strip()) > 0


# --- 6. Task Router Policy & Cross-Provider Privacy Isolation ---

@pytest.mark.asyncio
async def test_task_router_policy_and_isolation():
    router = TaskRouter()

    # 1. Routing classification checks
    assert router.get_designated_provider(TaskType.RESUME_GENERATION) == ProviderType.GROQ
    assert router.get_designated_provider(TaskType.RESUME_TAILORING) == ProviderType.GROQ
    assert router.get_designated_provider(TaskType.JD_ANALYSIS) == ProviderType.GROQ
    assert router.get_designated_provider(TaskType.INTERVIEW_EVALUATION) == ProviderType.GROQ
    assert router.get_designated_provider(TaskType.CHAT) == ProviderType.OLLAMA
    assert router.get_designated_provider(TaskType.TEXT_CLASSIFICATION) == ProviderType.OLLAMA
    assert router.get_designated_provider(TaskType.DETERMINISTIC) == ProviderType.DETERMINISTIC

    # 2. Deterministic operations blocked from LLMs
    with pytest.raises(AIProviderError) as exc_info:
        await router.execute(TaskType.DETERMINISTIC, prompt="sort applications")
    assert "deterministic operation" in str(exc_info.value).lower()

    # 3. Privacy boundary: Private chat cannot be streamed to cloud Groq
    with pytest.raises(CrossProviderLeakageViolation):
        async for _ in router.stream(TaskType.RESUME_GENERATION, messages=[{"role": "user", "content": "hi"}]):
            pass


# --- 7. Telemetry Tracking ---

def test_telemetry_metrics_tracking():
    tracker = AITelemetryTracker()
    tracker.record_success(provider="groq", task_name="resume_tailoring", latency_ms=450.0, prompt_tokens=100, completion_tokens=50)
    tracker.record_success(provider="groq", task_name="resume_tailoring", latency_ms=350.0, prompt_tokens=120, completion_tokens=60)
    tracker.record_failure(provider="groq", task_name="jd_analysis", latency_ms=100.0, error_message="Mock Rate limit")

    tracker.record_success(provider="ollama", task_name="chat", latency_ms=120.0, prompt_tokens=30, completion_tokens=20)

    m = tracker.get_metrics()
    groq_stats = m["groq"]
    assert groq_stats["total_requests"] == 3
    assert groq_stats["successful_requests"] == 2
    assert groq_stats["failed_requests"] == 1
    assert groq_stats["avg_latency_ms"] == 400.0
    assert groq_stats["total_tokens"] == 330
    assert groq_stats["last_error"] == "Mock Rate limit"

    ollama_stats = m["ollama"]
    assert ollama_stats["total_requests"] == 1
    assert ollama_stats["successful_requests"] == 1
    assert ollama_stats["total_tokens"] == 50


# --- 8. AI Diagnostics API Endpoints ---

def test_ai_status_endpoint():
    resp = client.get("/api/ai/status")
    assert resp.status_code == 200
    data = resp.json()

    assert "status" in data
    assert "providers" in data
    assert "groq" in data["providers"]
    assert "ollama" in data["providers"]
    assert data["providers"]["groq"]["role"] == "Complex Reasoning & Structured Generation"
    assert data["providers"]["ollama"]["role"] == "Everyday Interactions & Private Chat"
    assert "routing_policy" in data
    assert data["routing_policy"]["resume_tailoring"] == "groq"
    assert data["routing_policy"]["chat"] == "ollama"
    assert "Zero cross-provider leakage" in data["privacy_guarantee"]


def test_ai_test_provider_endpoint():
    # Test Ollama ping
    resp = client.post("/api/ai/test-provider", json={"provider": "ollama"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "ollama"
    assert "available" in data
    assert "latency_ms" in data

    # Test Groq ping
    resp2 = client.post("/api/ai/test-provider", json={"provider": "groq"})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["provider"] == "groq"
    assert "available" in data2
    assert "latency_ms" in data2
    if not settings.GROQ_API_KEY:
        assert data2["available"] is False
        assert "not configured" in data2["message"]
    else:
        assert data2["available"] is True

    # Test invalid provider
    resp3 = client.post("/api/ai/test-provider", json={"provider": "invalid_provider"})
    assert resp3.status_code == 400
