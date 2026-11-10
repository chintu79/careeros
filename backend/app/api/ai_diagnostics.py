import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.config import settings
from backend.app.services.ai import (
    ProviderType,
    TaskType,
    GroqAdapter,
    OllamaAdapter,
    telemetry,
    router
)
from backend.app.services.ai.task_router import TASK_ROUTING_MAP

ai_diagnostics_router = APIRouter(prefix="/ai", tags=["AI Infrastructure & Diagnostics"])

groq_adapter = GroqAdapter()
ollama_adapter = OllamaAdapter()


class TestProviderRequest(BaseModel):
    provider: str # "groq" or "ollama"


@ai_diagnostics_router.get("/status")
async def get_ai_status():
    """
    Returns live health, provider configuration status, telemetry metrics,
    and task-routing policies for Groq and local Ollama.
    """
    groq_ok, groq_msg = groq_adapter.is_available()
    ollama_ok, ollama_msg = await ollama_adapter.is_available()
    metrics = telemetry.get_metrics()

    routing_info = {
        task.value: provider.value
        for task, provider in TASK_ROUTING_MAP.items()
    }

    return {
        "status": "operational" if (groq_ok or ollama_ok) else "degraded",
        "providers": {
            "groq": {
                "name": "Groq Cloud API",
                "role": "Complex Reasoning & Structured Generation",
                "configured": groq_ok,
                "model": settings.GROQ_MODEL,
                "status_message": groq_msg,
                "telemetry": metrics.get("groq", {})
            },
            "ollama": {
                "name": "Local Ollama Daemon",
                "role": "Everyday Interactions & Private Chat",
                "configured": ollama_ok,
                "model": settings.OLLAMA_CHAT_MODEL,
                "base_url": settings.OLLAMA_BASE_URL,
                "status_message": ollama_msg,
                "telemetry": metrics.get("ollama", {})
            }
        },
        "routing_policy": routing_info,
        "privacy_guarantee": "Zero cross-provider leakage. Local chat is strictly isolated from cloud APIs.",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@ai_diagnostics_router.post("/test-provider")
async def test_provider_connectivity(req: TestProviderRequest):
    """
    Executes an on-demand connectivity ping for either Groq or Ollama.
    """
    prov = req.provider.lower().strip()
    start = time.time()

    if prov == "ollama":
        ok, msg = await ollama_adapter.is_available()
        latency = round((time.time() - start) * 1000, 2)
        return {
            "provider": "ollama",
            "available": ok,
            "message": msg,
            "model": settings.OLLAMA_CHAT_MODEL,
            "base_url": settings.OLLAMA_BASE_URL,
            "latency_ms": latency
        }
    elif prov == "groq":
        ok, msg = groq_adapter.is_available()
        latency = round((time.time() - start) * 1000, 2)
        return {
            "provider": "groq",
            "available": ok,
            "message": msg,
            "model": settings.GROQ_MODEL,
            "latency_ms": latency
        }
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider '{req.provider}'. Allowed values are 'groq' or 'ollama'."
        )
