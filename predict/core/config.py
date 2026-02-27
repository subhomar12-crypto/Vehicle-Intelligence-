"""
PREDICT - Unified Configuration

Merges Desktop PredictConfig and Server paths.py into a single source of truth.
All paths are derived from PROJECT_ROOT. Environment variables can override defaults.
"""

import os
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Project root: the directory containing the predict/ package
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _detect_project_root() -> Path:
    """Detect project root with environment variable override."""
    env_path = os.environ.get("PREDICT_ROOT")
    if env_path:
        path = Path(env_path).resolve()
        if path.is_dir():
            return path
        logger.warning(f"PREDICT_ROOT set but invalid: {env_path}, using default")
    return PROJECT_ROOT


@dataclass
class PredictConfig:
    """
    Central configuration for the PREDICT platform.
    Merges Desktop config.py + Server config/paths.py into one.
    """

    # Root directory
    ROOT_DIR: Path = field(default_factory=_detect_project_root)

    # App info
    APP_NAME: str = "PREDICT"
    APP_VERSION: str = "3.0.0"

    # Server settings
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    PDF_SERVER_PORT: int = 8001

    # Public URLs (Cloudflare tunnel)
    PUBLIC_API_URL: str = "https://predict.previlium.com"
    PUBLIC_PDF_URL: str = "https://pdf.previlium.com"

    # Timeouts and limits
    ONLINE_TIMEOUT_SECONDS: int = 30
    CACHE_TTL_SECONDS: int = 300
    MAX_CACHE_SIZE_MB: int = 500

    # Log retention
    LOG_RETENTION_DAYS: int = 7
    AUDIT_LOG_RETENTION_DAYS: int = 90

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://predict_admin:password@localhost:5432/predict"
    
    # Database pool
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 15
    DB_POOL_PRE_PING: bool = True

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_KEY_TTL_SECONDS: int = 300  # 5 minutes for API key cache

    # Email SMTP settings
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = "noreply@previlium.com"
    FROM_NAME: str = "PREDICT"

    # Debug mode
    debug: bool = False

    # CORS origins
    cors_origins: list = None

    def __post_init__(self):
        """Create required directories and load .env overrides."""
        # Load .env file if python-dotenv is available
        try:
            from dotenv import load_dotenv
            env_path = self.ROOT_DIR / ".env"
            if env_path.exists():
                load_dotenv(env_path, override=False)
        except ImportError:
            pass

        # Override config fields from environment variables
        env_overrides = {
            "DATABASE_URL": os.environ.get("DATABASE_URL"),
            "REDIS_URL": os.environ.get("REDIS_URL"),
            "SERVER_HOST": os.environ.get("SERVER_HOST"),
            "SERVER_PORT": os.environ.get("SERVER_PORT"),
            "PUBLIC_API_URL": os.environ.get("PUBLIC_API_URL"),
            "SMTP_HOST": os.environ.get("SMTP_HOST"),
            "SMTP_PORT": os.environ.get("SMTP_PORT"),
            "SMTP_USER": os.environ.get("SMTP_USER"),
            "SMTP_PASSWORD": os.environ.get("SMTP_PASSWORD"),
            "FROM_EMAIL": os.environ.get("EMAIL_FROM"),
            "FROM_NAME": os.environ.get("EMAIL_FROM_NAME"),
        }
        for key, value in env_overrides.items():
            if value is not None:
                if key in ("SERVER_PORT", "SMTP_PORT"):
                    value = int(value)
                object.__setattr__(self, key, value)

        if self.cors_origins is None:
            # Environment-based CORS: load from CORS_ORIGINS env var or use defaults
            env_cors = os.environ.get("CORS_ORIGINS")
            if env_cors:
                # Comma-separated list from environment
                self.cors_origins = [o.strip() for o in env_cors.split(",") if o.strip()]
            elif self.debug or os.environ.get("PREDICT_ENV", "dev").lower() in ("dev", "development", "local"):
                # Development: allow localhost + production domains
                self.cors_origins = [
                    "http://localhost:3000",
                    "http://localhost:5173",
                    "http://localhost:4173",
                    "http://localhost:8000",
                    "http://localhost:8080",
                    "https://predict.previlium.com",
                    "https://app.predict.previlium.com",
                    "https://predict-pp.com",
                    "https://www.predict-pp.com",
                    "https://predictapp.com",
                    "https://www.predictapp.com",
                ]
            else:
                # Production: only HTTPS production domains
                self.cors_origins = [
                    "https://predict.previlium.com",
                    "https://app.predict.previlium.com",
                    "https://predict-pp.com",
                    "https://www.predict-pp.com",
                    "https://predictapp.com",
                    "https://www.predictapp.com",
                ]
        self.ensure_directories()

    # ==================== DERIVED PATHS ====================

    @property
    def DATA_DIR(self) -> Path:
        return self.ROOT_DIR / "data"

    @property
    def PREDICT_DATA_DIR(self) -> Path:
        """Legacy PredictData directory (Desktop compatibility)."""
        return self.ROOT_DIR / "PredictData"

    @property
    def LOGS_DIR(self) -> Path:
        return self.DATA_DIR / "logs"

    @property
    def BACKUPS_DIR(self) -> Path:
        return self.DATA_DIR / "backups"

    @property
    def EXPORTS_DIR(self) -> Path:
        return self.DATA_DIR / "exports"

    @property
    def PARQUET_DIR(self) -> Path:
        return self.DATA_DIR / "parquet"

    @property
    def MODELS_DIR(self) -> Path:
        return self.ROOT_DIR / "models"

    @property
    def GGUF_DIR(self) -> Path:
        return self.MODELS_DIR / "gguf"

    @property
    def LSTM_MODELS_DIR(self) -> Path:
        return self.MODELS_DIR / "lstm"

    @property
    def CONFIG_DIR(self) -> Path:
        return self.ROOT_DIR / "config"

    @property
    def REPORTS_DIR(self) -> Path:
        return self.PREDICT_DATA_DIR / "reports"

    @property
    def AI_DIR(self) -> Path:
        return self.PREDICT_DATA_DIR / "ai"

    @property
    def AI_MODELS_DIR(self) -> Path:
        return self.AI_DIR / "models"

    @property
    def AI_RAW_DIR(self) -> Path:
        return self.AI_DIR / "raw"

    @property
    def AI_TRAINING_SETS_DIR(self) -> Path:
        return self.AI_DIR / "cleaned" / "training_sets"

    @property
    def CUSTOMERS_DIR(self) -> Path:
        return self.PREDICT_DATA_DIR / "customers"

    @property
    def CACHE_DIR(self) -> Path:
        return self.DATA_DIR / "cache"

    def ensure_directories(self) -> None:
        """Create all required directories if they don't exist."""
        dirs = [
            self.DATA_DIR,
            self.LOGS_DIR,
            self.BACKUPS_DIR,
            self.EXPORTS_DIR,
            self.PARQUET_DIR,
            self.CACHE_DIR,
            self.MODELS_DIR,
            self.GGUF_DIR,
            self.LSTM_MODELS_DIR,
            self.PREDICT_DATA_DIR,
            self.REPORTS_DIR,
            self.AI_DIR,
            self.AI_MODELS_DIR,
            self.AI_RAW_DIR,
            self.AI_TRAINING_SETS_DIR,
            self.CUSTOMERS_DIR,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)


# Singleton
_config: Optional[PredictConfig] = None


def get_config() -> PredictConfig:
    """Get or create the config singleton."""
    global _config
    if _config is None:
        _config = PredictConfig()
        logger.info(f"Config initialized: ROOT_DIR={_config.ROOT_DIR}")
    return _config
