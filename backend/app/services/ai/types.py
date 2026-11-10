from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class ProviderType(str, Enum):
    GROQ = "groq"
    OLLAMA = "ollama"
    DETERMINISTIC = "deterministic"


class TaskType(str, Enum):
    # --- Complex Reasoning Tasks (Handled by Groq Cloud API) ---
    RESUME_GENERATION = "resume_generation"
    RESUME_TAILORING = "resume_tailoring"
    JD_ANALYSIS = "jd_analysis"
    COMPATIBILITY_EXPLANATION = "compatibility_explanation"
    PROJECT_ANALYSIS = "project_analysis"
    INTERVIEW_EVALUATION = "interview_evaluation"
    CAREER_RECOMMENDATION = "career_recommendation"

    # --- Everyday / Conversational Tasks (Handled by Local Ollama) ---
    CHAT = "chat"
    TEXT_CLASSIFICATION = "text_classification"
    SUMMARIZATION = "summarization"
    INFORMATION_EXTRACTION = "information_extraction"

    # --- Deterministic Operations (Zero LLM Invocation) ---
    DETERMINISTIC = "deterministic"


class ModelResponse(BaseModel):
    content: str
    parsed_json: Optional[Dict[str, Any]] = None
    provider: ProviderType
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    finish_reason: str = "stop"


# --- Typed Custom Exceptions ---

class AIProviderError(Exception):
    """Base exception for all AI provider and routing errors."""
    def __init__(self, message: str, provider: Optional[str] = None, retryable: bool = False):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.retryable = retryable


class GroqProviderError(AIProviderError):
    """Raised when Groq API encounters an operational failure."""
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message, provider=ProviderType.GROQ.value, retryable=retryable)


class OllamaProviderError(AIProviderError):
    """Raised when local Ollama daemon encounters a failure."""
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message, provider=ProviderType.OLLAMA.value, retryable=retryable)


class RateLimitError(AIProviderError):
    """Raised when provider rate limits or token limits are exceeded."""
    def __init__(self, message: str, retry_after: Optional[float] = None, provider: Optional[str] = None):
        super().__init__(message, provider=provider, retryable=True)
        self.retry_after = retry_after


class ProviderUnavailableError(AIProviderError):
    """Raised when a provider is unconfigured or unreachable (e.g., missing API key or offline daemon)."""
    def __init__(self, message: str, provider: Optional[str] = None):
        super().__init__(message, provider=provider, retryable=False)


class StructuredOutputValidationError(AIProviderError):
    """Raised when LLM output cannot be parsed into the required Pydantic schema."""
    def __init__(self, message: str, raw_output: str = "", provider: Optional[str] = None):
        super().__init__(message, provider=provider, retryable=True)
        self.raw_output = raw_output


class CrossProviderLeakageViolation(AIProviderError):
    """Security exception raised if a local task attempts to route to cloud or vice versa."""
    def __init__(self, message: str):
        super().__init__(message, provider="security_boundary", retryable=False)
