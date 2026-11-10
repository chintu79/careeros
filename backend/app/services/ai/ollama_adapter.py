import time
import json
import logging
import httpx
from typing import Dict, Any, Optional, Tuple, Type, List, AsyncGenerator
from pydantic import BaseModel, ValidationError

from backend.app.config import settings
from backend.app.services.ai.types import (
    ProviderType,
    ModelResponse,
    OllamaProviderError,
    ProviderUnavailableError,
    StructuredOutputValidationError
)
from backend.app.services.ai.telemetry import telemetry

logger = logging.getLogger(__name__)


class OllamaAdapter:
    """
    Local Ollama inference adapter.
    Handles everyday conversational interactions (AI Assistant, basic classification, summarization)
    at zero cloud cost with full streaming support and complete privacy boundaries.
    """
    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0
    ):
        self._base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self._model = model or settings.OLLAMA_CHAT_MODEL
        self._timeout = timeout

    @property
    def model_name(self) -> str:
        return self._model or settings.OLLAMA_CHAT_MODEL

    @property
    def base_url(self) -> str:
        return self._base_url

    async def is_available(self) -> Tuple[bool, str]:
        """Checks if local Ollama daemon is reachable and whether the configured model is installed."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    target = self.model_name
                    # Check exact or partial match (e.g. llama3.2:latest vs llama3.2)
                    has_model = any(target in m or m.startswith(target.split(":")[0]) for m in models)
                    if has_model:
                        return True, f"Running locally (Model: {target} found, {len(models)} installed)"
                    return True, f"Daemon running, but model '{target}' not yet pulled. Available: {', '.join(models[:3])}"
                return False, f"Ollama returned unexpected HTTP {resp.status_code}"
        except httpx.ConnectError:
            return False, f"Ollama daemon not reachable at {self.base_url}. Start via 'ollama serve'."
        except Exception as e:
            return False, f"Ollama health check error: {e}"

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        messages: Optional[List[Dict[str, str]]] = None,
        response_schema: Optional[Type[BaseModel]] = None,
        temperature: float = 0.7,
        task_name: str = "ollama_task"
    ) -> ModelResponse:
        """
        Executes a standard non-streaming Ollama request.
        If response_schema is provided, requests JSON format and validates against the Pydantic schema.
        """
        start_time = time.time()
        
        # Build message history
        chat_messages: List[Dict[str, str]] = []
        if system_prompt:
            chat_messages.append({"role": "system", "content": system_prompt})
        
        if messages:
            chat_messages.extend(messages)
        else:
            chat_messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": chat_messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }

        if response_schema:
            payload["format"] = "json"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                latency_ms = (time.time() - start_time) * 1000

                if resp.status_code != 200:
                    err_msg = f"Ollama API returned HTTP {resp.status_code}: {resp.text}"
                    telemetry.record_failure(ProviderType.OLLAMA.value, task_name, latency_ms, err_msg)
                    raise OllamaProviderError(err_msg, retryable=True)

                data = resp.json()
                msg = data.get("message", {})
                raw_content = msg.get("content", "")
                
                prompt_tokens = data.get("prompt_eval_count", 0)
                completion_tokens = data.get("eval_count", 0)
                total_tokens = prompt_tokens + completion_tokens

                parsed_json = None
                if response_schema:
                    try:
                        clean_content = raw_content.strip()
                        if clean_content.startswith("```json"):
                            clean_content = clean_content[7:]
                        if clean_content.startswith("```"):
                            clean_content = clean_content[3:]
                        if clean_content.endswith("```"):
                            clean_content = clean_content[:-3]
                        clean_content = clean_content.strip()

                        parsed_dict = json.loads(clean_content)
                        validated_obj = response_schema.model_validate(parsed_dict)
                        parsed_json = validated_obj.model_dump()
                    except (json.JSONDecodeError, ValidationError) as ve:
                        err_msg = f"Ollama response failed schema validation: {ve}"
                        telemetry.record_failure(ProviderType.OLLAMA.value, task_name, latency_ms, err_msg)
                        raise StructuredOutputValidationError(
                            err_msg, raw_output=raw_content, provider=ProviderType.OLLAMA.value
                        ) from ve

                telemetry.record_success(
                    provider=ProviderType.OLLAMA.value,
                    task_name=task_name,
                    latency_ms=latency_ms,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens
                )

                return ModelResponse(
                    content=raw_content,
                    parsed_json=parsed_json,
                    provider=ProviderType.OLLAMA,
                    model=self.model_name,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    latency_ms=round(latency_ms, 2),
                    finish_reason="stop"
                )

        except httpx.ConnectError as ce:
            latency_ms = (time.time() - start_time) * 1000
            err_msg = f"Ollama connection refused at {self.base_url}. Ensure daemon is running ('ollama serve')."
            telemetry.record_failure(ProviderType.OLLAMA.value, task_name, latency_ms, err_msg)
            raise ProviderUnavailableError(err_msg, provider=ProviderType.OLLAMA.value) from ce

        except httpx.TimeoutException as te:
            latency_ms = (time.time() - start_time) * 1000
            err_msg = f"Ollama request timed out after {self._timeout}s."
            telemetry.record_failure(ProviderType.OLLAMA.value, task_name, latency_ms, err_msg)
            raise OllamaProviderError(err_msg, retryable=True) from te

        except (ProviderUnavailableError, StructuredOutputValidationError):
            raise

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            err_msg = f"Unexpected error communicating with local Ollama: {e}"
            telemetry.record_failure(ProviderType.OLLAMA.value, task_name, latency_ms, err_msg)
            raise OllamaProviderError(err_msg, retryable=True) from e

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = "",
        temperature: float = 0.7,
        task_name: str = "ollama_chat_stream"
    ) -> AsyncGenerator[str, None]:
        """
        Yields tokens in real-time as an asynchronous generator.
        Strictly local — never redirected to any cloud API.
        """
        start_time = time.time()
        chat_messages: List[Dict[str, str]] = []
        if system_prompt:
            chat_messages.append({"role": "system", "content": system_prompt})
        chat_messages.extend(messages)

        payload = {
            "model": self.model_name,
            "messages": chat_messages,
            "stream": True,
            "options": {"temperature": temperature}
        }

        accumulated_tokens = 0
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                    if response.status_code != 200:
                        err_text = await response.aread()
                        raise OllamaProviderError(f"Ollama stream error {response.status_code}: {err_text.decode('utf-8')}")

                    async for line in response.aiter_lines():
                        if not line or not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                            msg = chunk.get("message", {})
                            token = msg.get("content", "")
                            if token:
                                accumulated_tokens += 1
                                yield token
                            if chunk.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue

            latency_ms = (time.time() - start_time) * 1000
            telemetry.record_success(
                provider=ProviderType.OLLAMA.value,
                task_name=task_name,
                latency_ms=latency_ms,
                completion_tokens=accumulated_tokens
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            err_msg = f"Streaming failed on local Ollama: {e}"
            telemetry.record_failure(ProviderType.OLLAMA.value, task_name, latency_ms, err_msg)
            # Re-raise explicit error so UI can display local connection trouble
            raise OllamaProviderError(err_msg, retryable=True) from e
