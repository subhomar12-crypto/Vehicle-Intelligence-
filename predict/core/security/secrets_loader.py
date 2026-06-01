"""
Fail-fast secrets validation.
App will NOT start if required secrets are missing.
"""

import sys
import logging
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field, model_validator

logger = logging.getLogger(__name__)

# Find .env file: check project root (2 levels up from this file)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Secrets(BaseSettings):
    """All application secrets. Loaded from .env file and environment variables."""

    # Database
    DATABASE_URL: str = Field(description="PostgreSQL async connection string")

    # Redis (optional - graceful degradation)
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # Security
    SECRET_KEY: str = Field(description="App-wide signing key")
    ADMIN_API_KEY: str = Field(default="", description="Admin API key for management endpoints")
    FIELD_ENCRYPTION_KEY: str = Field(
        default="",
        description=(
            "AES-256-GCM key for field-level encryption (VIN, phone). "
            "Generate with: python -c \"import secrets, base64; "
            "print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())\""
        ),
    )

    # Email
    SMTP_HOST: str = Field(default="")
    SMTP_PORT: int = Field(default=587)
    SMTP_USER: str = Field(default="")
    SMTP_PASSWORD: str = Field(default="")
    EMAIL_FROM: str = Field(default="noreply@previlium.com")
    EMAIL_FROM_NAME: str = Field(default="PREDICT")

    # Firebase
    FCM_CREDENTIALS_PATH: str = Field(default="")

    # Billing
    FATORA_API_KEY: str = Field(default="")
    FATORA_WEBHOOK_SECRET: str = Field(default="")

    # Monitoring
    SENTRY_DSN: str = Field(default="")
    SENTRY_ENVIRONMENT: str = Field(default="production")

    # LLM
    LLM_MODEL_PATH: str = Field(default="models/gguf/Qwen3.5-4B-Q5_K_M.gguf")
    LLM_CONTEXT_SIZE: int = Field(default=4096)
    LLM_GPU_LAYERS: int = Field(default=0)

    # External APIs
    OPENAI_API_KEY: str = Field(default="")
    ANTHROPIC_API_KEY: str = Field(default="")

    # Server
    SERVER_HOST: str = Field(default="0.0.0.0")
    SERVER_PORT: int = Field(default=8000)
    PUBLIC_API_URL: str = Field(default="https://predict.previlium.com")

    # Cloudflare
    CLOUDFLARE_TUNNEL_TOKEN: str = Field(default="")

    model_config = {
        "env_file": str(_ENV_FILE) if _ENV_FILE.exists() else None,
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @model_validator(mode="after")
    def validate_required(self) -> "Secrets":
        """Fail fast if critical secrets are missing or set to placeholder values."""
        errors = []

        if not self.DATABASE_URL or "YOUR_PASSWORD" in self.DATABASE_URL:
            errors.append("DATABASE_URL is not configured (set in .env)")

        if not self.SECRET_KEY or self.SECRET_KEY == "CHANGE_ME_GENERATE_A_RANDOM_KEY":
            errors.append("SECRET_KEY is not configured (generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\")")

        if errors:
            for err in errors:
                logger.critical(f"MISSING SECRET: {err}")
            print("\n=== PREDICT STARTUP FAILED ===", file=sys.stderr)
            print("Required secrets are missing. Fix these in .env:", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            print(f"\nSee {_PROJECT_ROOT / '.env.example'} for template.", file=sys.stderr)
            print("===============================\n", file=sys.stderr)
            sys.exit(1)

        return self


_secrets_instance: Optional[Secrets] = None


def get_secrets() -> Secrets:
    """Get or create the secrets singleton. Validates on first call."""
    global _secrets_instance
    if _secrets_instance is None:
        _secrets_instance = Secrets()
        logger.info("Secrets loaded and validated successfully")
    return _secrets_instance
