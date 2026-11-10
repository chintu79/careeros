import os
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import List, Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "interniq CareerOS Job Discovery Engine"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+psycopg://postgres:postgres@localhost:54322/interniq"
    )
    
    # GitHub Integration Token (optional global fallback)
    GITHUB_TOKEN: Optional[str] = os.getenv("GITHUB_TOKEN", None)
    
    # AI Provider Configuration: Cloud Groq (Complex Reasoning)
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    
    # AI Provider Configuration: Local Ollama (Everyday Interactions)
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", os.getenv("OLLAMA_HOST", "http://localhost:11434"))
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    OLLAMA_EMBED_MODEL: str = os.getenv("OLLAMA_EMBED_MODEL", "bge-m3")
    OLLAMA_CHAT_MODEL: str = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2:latest")
    
    # Adzuna credentials (can be overridden via UI Source Management)
    ADZUNA_APP_ID: str = os.getenv("ADZUNA_APP_ID", "")
    ADZUNA_APP_KEY: str = os.getenv("ADZUNA_APP_KEY", "")
    
    ALLOWED_ORIGINS: List[str] = []  # populated from CAREEROS_ALLOWED_ORIGINS below

    
    DEFAULT_SYNC_HOURS: int = 6
    
    # Environment & Deployment Mode: "development", "test", "production"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").lower()

    # Token version: bump to revoke all outstanding tokens (e.g., "1" -> "2").
    TOKEN_VERSION: str = os.getenv("TOKEN_VERSION", "1")


    # Trusted reverse-proxy hops for client-IP resolution (0 = never trust X-Forwarded-For).
    TRUST_PROXY_HOPS: int = int(os.getenv("TRUST_PROXY_HOPS", "0"))

    # Seed demo/fixture data on first boot. NEVER enable in production.
    SEED_DEMO_DATA: bool = os.getenv("SEED_DEMO_DATA", "false").lower() in ("1", "true", "yes")

    # Run schema migrations on application startup. Default false: explicit operator command required.
    RUN_MIGRATIONS: bool = os.getenv("CAREEROS_RUN_MIGRATIONS", "0").lower() in ("1", "true", "yes")

    # Security & Identity Resolution
    SECRET_KEY: str = os.getenv("SECRET_KEY", "careeros-secure-signing-secret-key-2026")
    INTERNAL_GATEWAY_SECRET: str = os.getenv("INTERNAL_GATEWAY_SECRET", "")
    AUTH_REQUIRED: bool = os.getenv(
        "AUTH_REQUIRED", 
        "true" if os.getenv("ENVIRONMENT", "").lower() in ("production", "prod") else "false"
    ).lower() in ("true", "1")
    DEFAULT_USER_ID: int = int(os.getenv("DEFAULT_USER_ID", "1"))
    
    # Provider Concurrency & Timeouts
    GROQ_TIMEOUT_SECONDS: float = float(os.getenv("GROQ_TIMEOUT_SECONDS", "30.0"))
    
    # Token Vault Encryption Secret
    CAREEROS_TOKEN_SECRET: Optional[str] = os.getenv("CAREEROS_TOKEN_SECRET", None)

    # Authoritative Matching Engine Release Settings
    MATCHING_ENGINE_VERSION: str = os.getenv("MATCHING_ENGINE_VERSION", "2.0.0")
    MATCHING_ENGINE_GENERATION: int = int(os.getenv("MATCHING_ENGINE_GENERATION", "2"))

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT in ("production", "prod")

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT in ("development", "dev", "local", "test")

    def validate_security_configuration(self):
        """
        Validates security settings and prevents startup in insecure configurations.
        Fails fast if production configuration violates security constraints.
        """
        if self.is_production:
            if not self.AUTH_REQUIRED:
                raise RuntimeError(
                    "FATAL SECURITY MISCONFIGURATION: Production cannot run with AUTH_REQUIRED=False. "
                    "Set AUTH_REQUIRED=true in production environment."
                )
            
            insecure_defaults = [
                "careeros-secure-signing-secret-key-2026",
                "secret",
                "changeme",
                "password",
                "default",
                "admin",
                "test",
                "12345678"
            ]
            if (
                not self.SECRET_KEY 
                or self.SECRET_KEY.strip() == "" 
                or self.SECRET_KEY.lower() in insecure_defaults 
                or len(self.SECRET_KEY) < 32
            ):
                raise RuntimeError(
                    "FATAL SECURITY MISCONFIGURATION: Missing or insecure SECRET_KEY in production. "
                    "SECRET_KEY must be set to a cryptographically strong secret with at least 32 characters."
                )

            if self.INTERNAL_GATEWAY_SECRET and len(self.INTERNAL_GATEWAY_SECRET) < 32:
                raise RuntimeError(
                    "FATAL SECURITY MISCONFIGURATION: Insecure INTERNAL_GATEWAY_SECRET in production. "
                    "If configured, INTERNAL_GATEWAY_SECRET must have at least 32 characters."
                )

            if (
                not self.CAREEROS_TOKEN_SECRET 
                or self.CAREEROS_TOKEN_SECRET.strip() == "" 
                or self.CAREEROS_TOKEN_SECRET.lower() in insecure_defaults 
                or len(self.CAREEROS_TOKEN_SECRET) < 32
            ):
                raise RuntimeError(
                    "FATAL SECURITY MISCONFIGURATION: Missing or insecure CAREEROS_TOKEN_SECRET in production. "
                    "CAREEROS_TOKEN_SECRET must be set to a cryptographically strong secret with at least 32 characters."
                )

    model_config = ConfigDict(
        env_file=".env",
        extra="allow"
    )

settings = Settings()


def _allowed_origins_env() -> List[str]:
    raw = os.getenv("CAREEROS_ALLOWED_ORIGINS", "http://localhost:5174,http://127.0.0.1:5174")
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


settings.ALLOWED_ORIGINS = _allowed_origins_env()  # type: ignore[assignment]
