import asyncio
import logging
from typing import Dict, Any, Optional, Type, List, AsyncGenerator
from pydantic import BaseModel

from backend.app.services.ai.types import (
    TaskType,
    ProviderType,
    ModelResponse,
    AIProviderError,
    GroqProviderError,
    OllamaProviderError,
    RateLimitError,
    ProviderUnavailableError,
    CrossProviderLeakageViolation
)
from backend.app.services.ai.groq_adapter import GroqAdapter
from backend.app.services.ai.ollama_adapter import OllamaAdapter

logger = logging.getLogger(__name__)

# Task-to-Provider Definitive Routing Mapping
TASK_ROUTING_MAP: Dict[TaskType, ProviderType] = {
    # Complex Reasoning (Cloud Groq)
    TaskType.RESUME_GENERATION: ProviderType.GROQ,
    TaskType.RESUME_TAILORING: ProviderType.GROQ,
    TaskType.JD_ANALYSIS: ProviderType.GROQ,
    TaskType.COMPATIBILITY_EXPLANATION: ProviderType.GROQ,
    TaskType.PROJECT_ANALYSIS: ProviderType.GROQ,
    TaskType.INTERVIEW_EVALUATION: ProviderType.GROQ,
    TaskType.CAREER_RECOMMENDATION: ProviderType.GROQ,

    # Everyday Conversational & Low-cost Classification (Local Ollama)
    TaskType.CHAT: ProviderType.OLLAMA,
    TaskType.TEXT_CLASSIFICATION: ProviderType.OLLAMA,
    TaskType.SUMMARIZATION: ProviderType.OLLAMA,
    TaskType.INFORMATION_EXTRACTION: ProviderType.OLLAMA,

    # Deterministic Operations (Must never invoke LLMs)
    TaskType.DETERMINISTIC: ProviderType.DETERMINISTIC
}


class TaskRouter:
    """
    Central task routing engine.
    Dispatches tasks to the appropriate provider adapter according to architectural policy,
    enforces strict cross-provider privacy/quality boundaries, and manages exponential backoff retries.
    """
    def __init__(
        self,
        groq_adapter: Optional[GroqAdapter] = None,
        ollama_adapter: Optional[OllamaAdapter] = None
    ):
        self.groq = groq_adapter or GroqAdapter()
        self.ollama = ollama_adapter or OllamaAdapter()

    def get_designated_provider(self, task_type: TaskType) -> ProviderType:
        """Returns the designated provider for a given task type."""
        return TASK_ROUTING_MAP.get(task_type, ProviderType.DETERMINISTIC)

    async def execute(
        self,
        task_type: TaskType,
        prompt: str,
        system_prompt: str = "",
        response_schema: Optional[Type[BaseModel]] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        temperature: Optional[float] = None,
        max_retries: int = 1
    ) -> ModelResponse:
        """
        Routes the task to its designated provider with retry logic.
        Strictly guarantees:
        - Groq failure NEVER produces a degraded local output.
        - Ollama failure NEVER sends private conversations to Groq.
        """
        provider = self.get_designated_provider(task_type)

        if provider == ProviderType.DETERMINISTIC:
            raise AIProviderError(
                f"Task '{task_type.value}' is a deterministic operation. Do not invoke an AI provider.",
                provider=ProviderType.DETERMINISTIC.value,
                retryable=False
            )

        task_name = task_type.value
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                if provider == ProviderType.GROQ:
                    # Enforce privacy boundary: Verify task is actually intended for Groq
                    if task_type in [TaskType.CHAT, TaskType.TEXT_CLASSIFICATION]:
                        raise CrossProviderLeakageViolation(
                            f"Security violation: Attempted to route private conversational task '{task_type}' to cloud Groq API."
                        )
                    
                    temp = temperature if temperature is not None else 0.2
                    return await self.groq.generate(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        response_schema=response_schema,
                        temperature=temp,
                        task_name=task_name
                    )

                elif provider == ProviderType.OLLAMA:
                    # Enforce quality boundary: Verify task is not high-reasoning document generation
                    if task_type in [TaskType.RESUME_GENERATION, TaskType.RESUME_TAILORING]:
                        raise CrossProviderLeakageViolation(
                            f"Quality policy violation: Attempted to route complex resume task '{task_type}' to local Ollama."
                        )

                    temp = temperature if temperature is not None else 0.7
                    return await self.ollama.generate(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        messages=messages,
                        response_schema=response_schema,
                        temperature=temp,
                        task_name=task_name
                    )

            except RateLimitError as rle:
                last_exception = rle
                if attempt < max_retries:
                    backoff = (rle.retry_after or 2.0) * (attempt + 1)
                    logger.warning(f"Rate limited on task '{task_name}'. Retrying in {backoff}s (attempt {attempt+1}/{max_retries})...")
                    await asyncio.sleep(backoff)
                else:
                    raise

            except (ProviderUnavailableError, CrossProviderLeakageViolation):
                # Non-retryable configuration or policy error
                raise

            except (GroqProviderError, OllamaProviderError) as pe:
                last_exception = pe
                if pe.retryable and attempt < max_retries:
                    backoff = 1.5 * (attempt + 1)
                    logger.warning(f"Transient error on task '{task_name}': {pe}. Retrying in {backoff}s...")
                    await asyncio.sleep(backoff)
                else:
                    raise

            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    await asyncio.sleep(1.0)
                else:
                    raise AIProviderError(f"Task '{task_name}' failed: {e}", provider=provider.value) from e

        if last_exception:
            raise last_exception

    async def stream(
        self,
        task_type: TaskType,
        messages: List[Dict[str, str]],
        system_prompt: str = "",
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """
        Streams conversational output.
        Strictly routes to local Ollama — never cloud Groq.
        """
        provider = self.get_designated_provider(task_type)
        if provider != ProviderType.OLLAMA:
            raise CrossProviderLeakageViolation(
                f"Streaming chat is restricted to local Ollama. Task '{task_type.value}' is designated for {provider.value}."
            )

        async for token in self.ollama.stream_chat(
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            task_name=task_type.value
        ):
            yield token


router = TaskRouter()
