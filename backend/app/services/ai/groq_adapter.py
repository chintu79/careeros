import time
import json
import logging
from typing import Dict, Any, Optional, Tuple, Type
from pydantic import BaseModel, ValidationError

try:
    from groq import AsyncGroq, RateLimitError as GroqRateLimitError, APITimeoutError as GroqTimeoutError, APIError as GroqAPIError
except ImportError:
    AsyncGroq = None
    GroqRateLimitError = Exception
    GroqTimeoutError = Exception
    GroqAPIError = Exception

from backend.app.config import settings
from backend.app.services.ai.types import (
    ProviderType,
    ModelResponse,
    GroqProviderError,
    RateLimitError,
    ProviderUnavailableError,
    StructuredOutputValidationError
)
from backend.app.services.ai.telemetry import telemetry

logger = logging.getLogger(__name__)


class GroqAdapter:
    """
    Official Groq Cloud API adapter.
    Handles high-reasoning, complex generative tasks (resumes, tailoring, JDs, technical evaluations)
    with strict JSON schema validation, rate limit handling, and latency/token telemetry.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        self._api_key = api_key if api_key is not None else settings.GROQ_API_KEY
        self._model = model or settings.GROQ_MODEL
        self._client: Optional[Any] = None

    @property
    def model_name(self) -> str:
        return self._model or settings.GROQ_MODEL

    def _get_client(self) -> Any:
        if not self._api_key or self._api_key.startswith("your_groq_api_key"):
            raise ProviderUnavailableError(
                "GROQ_API_KEY is not configured. Set GROQ_API_KEY in .env to enable Groq cloud reasoning.",
                provider=ProviderType.GROQ.value
            )
        if AsyncGroq is None:
            raise ProviderUnavailableError(
                "Groq Python SDK is not installed. Install via 'pip install groq'.",
                provider=ProviderType.GROQ.value
            )
        if self._client is None:
            self._client = AsyncGroq(api_key=self._api_key, timeout=settings.GROQ_TIMEOUT_SECONDS)
        return self._client

    def is_available(self) -> Tuple[bool, str]:
        """Checks if Groq API credentials are configured without exposing keys."""
        if not self._api_key or self._api_key.strip() == "" or self._api_key.startswith("your_groq_api_key"):
            return False, "GROQ_API_KEY is not configured in backend environment."
        if AsyncGroq is None:
            return False, "Groq Python SDK is not installed."
        return True, f"Configured (Model: {self.model_name})"

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        response_schema: Optional[Type[BaseModel]] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = 4096,
        task_name: str = "groq_task"
    ) -> ModelResponse:
        """
        Executes a Groq chat completion.
        If response_schema is provided, enforces JSON format and validates output against the Pydantic model.
        """
        client = self._get_client()
        start_time = time.time()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # If schema is provided, instruct JSON generation
        if response_schema and "json" not in prompt.lower() and "json" not in system_prompt.lower():
            prompt = f"{prompt}\n\nIMPORTANT: Respond with a valid JSON object matching the requested schema."

        messages.append({"role": "user", "content": prompt})

        request_kwargs: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        if response_schema:
            request_kwargs["response_format"] = {"type": "json_object"}

        try:
            resp = await client.chat.completions.create(**request_kwargs)
            latency_ms = (time.time() - start_time) * 1000

            choice = resp.choices[0]
            raw_content = choice.message.content or ""
            finish_reason = choice.finish_reason or "stop"

            usage = getattr(resp, "usage", None)
            prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
            completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
            total_tokens = getattr(usage, "total_tokens", 0) if usage else (prompt_tokens + completion_tokens)

            parsed_json = None
            if response_schema:
                try:
                    # Clean markdown codeblocks if wrapped
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
                    err_msg = f"Groq response failed schema validation: {ve}"
                    telemetry.record_failure(ProviderType.GROQ.value, task_name, latency_ms, err_msg)
                    raise StructuredOutputValidationError(
                        err_msg, raw_output=raw_content, provider=ProviderType.GROQ.value
                    ) from ve

            telemetry.record_success(
                provider=ProviderType.GROQ.value,
                task_name=task_name,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens
            )

            return ModelResponse(
                content=raw_content,
                parsed_json=parsed_json,
                provider=ProviderType.GROQ,
                model=self.model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=round(latency_ms, 2),
                finish_reason=finish_reason
            )

        except GroqRateLimitError as rle:
            latency_ms = (time.time() - start_time) * 1000
            err_msg = f"Groq Rate Limit Exceeded: {rle}"
            telemetry.record_failure(ProviderType.GROQ.value, task_name, latency_ms, err_msg)
            retry_after = getattr(rle, "retry_after", None) or 5.0
            raise RateLimitError(err_msg, retry_after=retry_after, provider=ProviderType.GROQ.value) from rle

        except GroqTimeoutError as te:
            latency_ms = (time.time() - start_time) * 1000
            err_msg = f"Groq Request Timed Out: {te}"
            telemetry.record_failure(ProviderType.GROQ.value, task_name, latency_ms, err_msg)
            raise GroqProviderError(err_msg, retryable=True) from te

        except GroqAPIError as ge:
            latency_ms = (time.time() - start_time) * 1000
            err_msg = f"Groq API Error: {ge}"
            telemetry.record_failure(ProviderType.GROQ.value, task_name, latency_ms, err_msg)
            raise GroqProviderError(err_msg, retryable=False) from ge

        except (ProviderUnavailableError, StructuredOutputValidationError):
            raise

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            err_msg = f"Unexpected error during Groq generation: {e}"
            telemetry.record_failure(ProviderType.GROQ.value, task_name, latency_ms, err_msg)
            raise GroqProviderError(err_msg, retryable=True) from e
