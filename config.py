"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Central Configuration Module

Predict OBD - Central Configuration Module
Single source of truth for all application paths and settings.

This module determines the application root directory and provides
all paths as properties derived from that root.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class ExternalAPIKeys:
    """
    Manages external API keys (OpenAI, Anthropic, etc.)
    with environment variable fallback.

    Priority:
    1. Environment variable (e.g., OPENAI_API_KEY)
    2. Config file (api_keys.json -> external_apis section)
    3. None (disabled)
    """

    # Environment variable names
    ENV_VARS = {
        'openai': 'OPENAI_API_KEY',
        'anthropic': 'ANTHROPIC_API_KEY',
    }

    def __init__(self, config_file: Optional[Path] = None):
        self._config_file = config_file
        self._cached_keys: Dict[str, Optional[str]] = {}
        self._loaded = False

    def _load_from_file(self) -> Dict[str, Any]:
        """Load external API config from file"""
        if not self._config_file or not self._config_file.exists():
            return {}

        try:
            with open(self._config_file, 'r') as f:
                data = json.load(f)
                return data.get('external_apis', {})
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load external API keys from file: {e}")
            return {}

    def get_key(self, provider: str) -> Optional[str]:
        """
        Get API key for a provider.

        Args:
            provider: 'openai' or 'anthropic'

        Returns:
            API key string or None if not configured
        """
        # Check cache
        if provider in self._cached_keys:
            return self._cached_keys[provider]

        # Priority 1: Environment variable
        env_var = self.ENV_VARS.get(provider)
        if env_var:
            env_value = os.environ.get(env_var)
            if env_value:
                logger.info(f"Using {provider} API key from environment variable")
                self._cached_keys[provider] = env_value
                return env_value

        # Priority 2: Config file
        file_config = self._load_from_file()
        provider_config = file_config.get(provider, {})

        if provider_config.get('enabled', False):
            api_key = provider_config.get('api_key')
            if api_key and not api_key.startswith('YOUR_') and not api_key.startswith('sk-YOUR'):
                logger.info(f"Using {provider} API key from config file")
                self._cached_keys[provider] = api_key
                return api_key

        # Not configured
        self._cached_keys[provider] = None
        return None

    def is_configured(self, provider: str) -> bool:
        """Check if a provider is configured"""
        return self.get_key(provider) is not None

    def get_model(self, provider: str) -> Optional[str]:
        """Get configured model for a provider"""
        file_config = self._load_from_file()
        provider_config = file_config.get(provider, {})
        return provider_config.get('model')

    def clear_cache(self):
        """Clear cached keys (useful for testing)"""
        self._cached_keys = {}


def _get_application_root() -> Path:
    """
    Determine the application root directory.

    Priority:
    1. PREDICT_DATA_DIR environment variable
    2. Directory containing the executable (for frozen apps)
    3. Directory containing this config.py file (for development)
    """
    # Check environment variable first
    env_path = os.environ.get('PREDICT_DATA_DIR')
    if env_path:
        path = Path(env_path)
        if path.exists() and path.is_dir():
            logger.info(f"Using PREDICT_DATA_DIR: {path}")
            return path
        else:
            logger.warning(f"PREDICT_DATA_DIR set but invalid: {env_path}")

    # Check if running as frozen executable (PyInstaller)
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        root = Path(sys.executable).parent
        logger.info(f"Running as frozen app, root: {root}")
        return root

    # Development mode - use this file's directory
    root = Path(__file__).parent.resolve()
    logger.info(f"Running in development mode, root: {root}")
    return root


@dataclass
class PredictConfig:
    """
    Central configuration for Predict OBD application.
    All paths are derived from ROOT_DIR.
    """

    # Root directory - determined at initialization
    ROOT_DIR: Path = field(default_factory=_get_application_root)

    # Schema version for migration tracking
    SCHEMA_VERSION: str = "1"

    # Application version
    APP_VERSION: str = "1.0.0"

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

    # External API keys manager (lazy initialized)
    _external_apis: Optional[ExternalAPIKeys] = field(default=None, repr=False)

    def __post_init__(self):
        """
        Called after dataclass initialization.
        Auto-create all required directories on first initialization.
        """
        # Auto-create all required directories on first initialization
        self.ensure_directories()

    @property
    def external_apis(self) -> ExternalAPIKeys:
        """Get external API keys manager"""
        if self._external_apis is None:
            self._external_apis = ExternalAPIKeys(self.API_KEYS_FILE)
        return self._external_apis

    # ==================== DERIVED PATHS ====================

    @property
    def DATA_DIR(self) -> Path:
        """Main data directory - PredictData under root"""
        return self.ROOT_DIR / "PredictData"

    # --- Top-level directories ---

    @property
    def SYSTEM_DIR(self) -> Path:
        """System configuration and metadata"""
        return self.DATA_DIR / "system"

    @property
    def CUSTOMERS_DIR(self) -> Path:
        """All customer data"""
        return self.DATA_DIR / "customers"

    @property
    def AI_DIR(self) -> Path:
        """AI training data, models, predictions"""
        return self.DATA_DIR / "ai"

    @property
    def REPORTS_DIR(self) -> Path:
        """Generated PDF reports"""
        return self.DATA_DIR / "reports"

    @property
    def LOGS_DIR(self) -> Path:
        """Application logs"""
        return self.DATA_DIR / "logs"

    @property
    def CACHE_DIR(self) -> Path:
        """Regenerable cache data"""
        return self.DATA_DIR / "cache"

    @property
    def TEMP_DIR(self) -> Path:
        """Temporary files (safe to delete)"""
        return self.DATA_DIR / "temp"

    # --- System subdirectories ---

    @property
    def CONFIG_DIR(self) -> Path:
        """Configuration files"""
        return self.SYSTEM_DIR / "config"

    @property
    def INSTALLATION_FILE(self) -> Path:
        """Installation metadata file"""
        return self.SYSTEM_DIR / "installation.json"

    @property
    def SETTINGS_FILE(self) -> Path:
        """Application settings"""
        return self.CONFIG_DIR / "settings.json"

    @property
    def API_KEYS_FILE(self) -> Path:
        """API keys configuration (hashed)"""
        return self.CONFIG_DIR / "api_keys.json"

    @property
    def API_KEYS_TEMPLATE(self) -> Path:
        """API keys template (no real keys)"""
        return self.CONFIG_DIR / "api_keys.template.json"

    # --- AI subdirectories ---

    @property
    def AI_RAW_DIR(self) -> Path:
        """Raw unprocessed AI training data"""
        return self.AI_DIR / "raw"

    @property
    def AI_RAW_OBD_DIR(self) -> Path:
        """Raw OBD snapshots for training"""
        return self.AI_RAW_DIR / "obd_snapshots"

    @property
    def AI_RAW_FEEDBACK_DIR(self) -> Path:
        """Raw feedback data"""
        return self.AI_RAW_DIR / "feedback"

    @property
    def AI_CLEANED_DIR(self) -> Path:
        """Cleaned and validated training data"""
        return self.AI_DIR / "cleaned"

    @property
    def AI_TRAINING_SETS_DIR(self) -> Path:
        """Ready-to-use training datasets"""
        return self.AI_CLEANED_DIR / "training_sets"

    @property
    def AI_FEATURE_STORE_DIR(self) -> Path:
        """Computed feature files"""
        return self.AI_CLEANED_DIR / "feature_store"

    @property
    def AI_MODELS_DIR(self) -> Path:
        """Trained model artifacts"""
        return self.AI_DIR / "models"

    @property
    def MODELS_DIR(self) -> Path:
        """Legacy alias for AI_MODELS_DIR for backward compatibility"""
        return self.AI_MODELS_DIR

    @property
    def SERVER_DIR(self) -> Path:
        """
        OBD Server directory with auto-detection.
        Priority order:
        1. OBD_SERVER_DIR environment variable
        2. C:\OBDserver\Previlium_OBD_Server (default Windows location)
        3. ../OBDserver/Previlium_OBD_Server (relative path)
        4. server subdirectory in app root
        """
        # 1. Check environment variable
        server_path = os.environ.get("OBD_SERVER_DIR")
        if server_path:
            path = Path(server_path)
            if path.exists():
                return path
            logger.warning(f"OBD_SERVER_DIR set but path doesn't exist: {server_path}")

        # 2. Check default Windows location
        default_windows_path = Path(r"C:\OBDserver\Previlium_OBD_Server")  # noqa: E605
        if default_windows_path.exists():
            return default_windows_path

        # 3. Check relative path (for development)
        relative_path = self.ROOT_DIR.parent / "OBDserver" / "Previlium_OBD_Server"
        if relative_path.exists():
            return relative_path

        # 4. Fallback to local server directory
        return self.ROOT_DIR / "server"

    @property
    def SERVER_DB_PATH(self) -> Path:
        """
        OBD Server database file path.
        Checks multiple possible database locations.
        """
        # First try the standard location
        db_path = self.SERVER_DIR / "data" / "obd_data.db"
        if db_path.exists():
            return db_path

        # Check if database exists directly in server directory
        alt_path = self.SERVER_DIR / "obd_data.db"
        if alt_path.exists():
            return alt_path

        # Return the standard path even if it doesn't exist yet
        # (will be created when server starts)
        return db_path

    @property
    def PROFILES_DB_PATH(self) -> Path:
        """
        Vehicle profiles database file path.
        Now points to server database for automatic sync with Android app.
        """
        # Use server database for unified profile storage
        server_db = self.SERVER_DIR / "data" / "vehicle_data.db"
        if server_db.exists():
            return server_db

        # Fallback to local database if server database doesn't exist
        return self.DATA_DIR / "vehicle_profiles.db"

    @property
    def BACKUPS_DIR(self) -> Path:
        """Backup storage directory"""
        return self.ROOT_DIR / "backups"

    @property
    def RESOURCES_DIR(self) -> Path:
        """Application resources (icons, images, etc.)"""
        return self.ROOT_DIR / "resources"
    
    @property
    def CLOUDFLARE_DIR(self) -> Path:
        """
        Cloudflare tunnel directory for cloudflared executable and config.
        Priority:
        1. CLOUDFLARE_DIR environment variable
        2. C:\\cloudflared (standard Windows location)
        3. ROOT_DIR/cloudflared (development fallback)
        """
        # Check environment variable first
        cloudflare_path = os.environ.get("CLOUDFLARE_DIR")
        if cloudflare_path:
            path = Path(cloudflare_path)
            if path.exists():
                return path

        # Check standard Windows location
        standard_path = Path(r"C:\cloudflared")
        if standard_path.exists() and (standard_path / "cloudflared.exe").exists():
            return standard_path

        # Fallback to app directory
        return self.ROOT_DIR / "cloudflared"

    @property
    def AI_MODELS_REGISTRY(self) -> Path:
        """Model registry file"""
        return self.AI_MODELS_DIR / "registry.json"

    @property
    def AI_PREDICTIONS_DIR(self) -> Path:
        """Prediction audit logs"""
        return self.AI_DIR / "predictions"

    @property
    def AI_ACCURACY_FILE(self) -> Path:
        """Accuracy tracking file"""
        return self.AI_PREDICTIONS_DIR / "accuracy_tracking.json"

    @property
    def AI_EXPERIMENTS_DIR(self) -> Path:
        """Experimental models"""
        return self.AI_DIR / "experiments"

    # --- Advanced AI Model directories ---

    @property
    def AI_CNN_LSTM_DIR(self) -> Path:
        """CNN-LSTM hybrid models"""
        return self.AI_MODELS_DIR / "cnn_lstm"

    @property
    def AI_ATTENTION_LSTM_DIR(self) -> Path:
        """Attention-LSTM models"""
        return self.AI_MODELS_DIR / "attention_lstm"

    @property
    def AI_AUTOENCODER_DIR(self) -> Path:
        """LSTM Autoencoder models"""
        return self.AI_MODELS_DIR / "autoencoder"

    @property
    def AI_ENSEMBLE_DIR(self) -> Path:
        """Ensemble model configurations"""
        return self.AI_MODELS_DIR / "ensemble"

    @property
    def PHYSICS_CONFIG_DIR(self) -> Path:
        """Physics constraints configurations"""
        return self.CONFIG_DIR / "physics"

    # --- Reports subdirectories ---

    @property
    def REPORTS_QUEUE_DIR(self) -> Path:
        """Report generation queue"""
        return self.REPORTS_DIR / "queue"

    @property
    def REPORTS_QUEUE_FILE(self) -> Path:
        """Pending reports queue file"""
        return self.REPORTS_QUEUE_DIR / "pending.json"

    @property
    def REPORTS_METADATA_DIR(self) -> Path:
        """Report metadata"""
        return self.REPORTS_DIR / "metadata"

    @property
    def REPORTS_INDEX_FILE(self) -> Path:
        """Reports index file"""
        return self.REPORTS_METADATA_DIR / "reports_index.json"

    # --- Logs subdirectories ---

    @property
    def LOGS_APP_DIR(self) -> Path:
        """Application logs"""
        return self.LOGS_DIR / "app"

    @property
    def LOGS_API_DIR(self) -> Path:
        """API request/response logs"""
        return self.LOGS_DIR / "api"

    @property
    def LOGS_ERROR_DIR(self) -> Path:
        """Error-only logs"""
        return self.LOGS_DIR / "error"

    @property
    def LOGS_AUDIT_DIR(self) -> Path:
        """Security/compliance audit logs"""
        return self.LOGS_DIR / "audit"

    @property
    def LOGS_ARCHIVE_DIR(self) -> Path:
        """Compressed log archives"""
        return self.LOGS_DIR / "archive"

    # --- Cache subdirectories ---

    @property
    def CACHE_API_DIR(self) -> Path:
        """Cached API responses"""
        return self.CACHE_DIR / "api_responses"

    @property
    def CACHE_COMPUTED_DIR(self) -> Path:
        """Computed statistics cache"""
        return self.CACHE_DIR / "computed"

    @property
    def CACHE_SESSION_DIR(self) -> Path:
        """Session data cache"""
        return self.CACHE_DIR / "session"

    # --- Temp subdirectories ---

    @property
    def TEMP_UPLOADS_DIR(self) -> Path:
        """Incoming file uploads"""
        return self.TEMP_DIR / "uploads"

    @property
    def TEMP_PROCESSING_DIR(self) -> Path:
        """Files being processed"""
        return self.TEMP_DIR / "processing"

    @property
    def TEMP_DOWNLOADS_DIR(self) -> Path:
        """Prepared downloads"""
        return self.TEMP_DIR / "downloads"

    # ==================== HELPER METHODS ====================

    def ensure_directories(self) -> None:
        """
        Create all required application directories on first run.
        This method is idempotent - safe to call multiple times.
        Called automatically during PredictConfig initialization.
        """
        directories_to_create = [
            # Core data directories
            self.DATA_DIR,
            self.DATA_DIR / "ai_alerts",
            self.DATA_DIR / "custom_alerts",
            self.DATA_DIR / "fuel_data",
            self.DATA_DIR / "geofences",
            self.DATA_DIR / "historical_data",
            self.DATA_DIR / "service_history",
            self.DATA_DIR / "maintenance_schedules",
            self.DATA_DIR / "exports",
            self.DATA_DIR / "reports",
            self.DATA_DIR / "vehicle_profiles",
            self.DATA_DIR / "server",
            self.DATA_DIR / "pdf_queue",
            
            # Configuration directory
            self.CONFIG_DIR,
            
            # Logging directories
            self.LOGS_DIR,
            self.LOGS_DIR / "training",
            self.LOGS_DIR / "app",
            self.LOGS_DIR / "error",
            
            # AI/ML directories
            self.MODELS_DIR,
            self.MODELS_DIR / "lstm",
            self.MODELS_DIR / "ensemble",
            
            # Cache and temp
            self.CACHE_DIR,
            self.TEMP_DIR,
            
            # Backups and resources
            self.BACKUPS_DIR,
            self.RESOURCES_DIR,
            
            # Cloudflare tunnel
            self.CLOUDFLARE_DIR,
            
            # Additional data directories
            self.DATA_DIR / "pid_profiles",
            self.AI_DIR / "datasets",
            self.DATA_DIR / "cloudflare",
            
            # Additional AI directories for modules
            self.AI_DIR / "feature_engineering",
            self.AI_DIR / "failure_correlations",
            self.AI_DIR / "confidence_data",
            self.AI_DIR / "rul_data",
            self.DATA_DIR / "feedback",
            self.DATA_DIR / "external_sensors",
            self.DATA_DIR / "vehicle_baselines",

            # Advanced AI model directories
            self.AI_CNN_LSTM_DIR,
            self.AI_ATTENTION_LSTM_DIR,
            self.AI_AUTOENCODER_DIR,
            self.AI_ENSEMBLE_DIR,
            self.PHYSICS_CONFIG_DIR,
        ]
        
        for directory in directories_to_create:
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                # Log warning but don't crash - directory might be created later
                print(f"Warning: Could not create directory {directory}")
            except Exception as e:
                print(f"Warning: Error creating directory {directory}: {e}")

    def get_customer_dir(self, customer_id: str) -> Path:
        """Get directory for a specific customer"""
        return self.CUSTOMERS_DIR / customer_id

    def get_customer_profile(self, customer_id: str) -> Path:
        """Get customer profile file path"""
        return self.get_customer_dir(customer_id) / "profile.json"

    def get_customer_subscription(self, customer_id: str) -> Path:
        """Get customer subscription file path"""
        return self.get_customer_dir(customer_id) / "subscription.json"

    def get_customer_vehicles_dir(self, customer_id: str) -> Path:
        """Get vehicles directory for a customer"""
        return self.get_customer_dir(customer_id) / "vehicles"

    def get_customer_api_keys_dir(self, customer_id: str) -> Path:
        """Get API keys directory for a customer"""
        return self.get_customer_dir(customer_id) / "api_keys"

    def get_customer_exports_dir(self, customer_id: str) -> Path:
        """Get exports directory for a customer"""
        return self.get_customer_dir(customer_id) / "exports"

    def get_vehicle_dir(self, customer_id: str, vehicle_id: str) -> Path:
        """Get directory for a specific vehicle"""
        return self.get_customer_vehicles_dir(customer_id) / vehicle_id

    def get_vehicle_obd_dir(self, customer_id: str, vehicle_id: str) -> Path:
        """Get OBD data directory for a vehicle"""
        return self.get_vehicle_dir(customer_id, vehicle_id) / "obd_data"

    def get_vehicle_trips_dir(self, customer_id: str, vehicle_id: str) -> Path:
        """Get trips directory for a vehicle"""
        return self.get_vehicle_dir(customer_id, vehicle_id) / "trips"

    def get_vehicle_service_dir(self, customer_id: str, vehicle_id: str) -> Path:
        """Get service history directory for a vehicle"""
        return self.get_vehicle_dir(customer_id, vehicle_id) / "service"

    def get_vehicle_predictions_dir(self, customer_id: str, vehicle_id: str) -> Path:
        """Get predictions directory for a vehicle"""
        return self.get_vehicle_dir(customer_id, vehicle_id) / "predictions"

    def get_vehicle_feedback_dir(self, customer_id: str, vehicle_id: str) -> Path:
        """Get feedback directory for a vehicle"""
        return self.get_vehicle_dir(customer_id, vehicle_id) / "feedback"

    def get_customer_reports_dir(self, customer_id: str) -> Path:
        """Get reports directory for a customer"""
        return self.REPORTS_DIR / customer_id

    def get_vehicle_reports_dir(self, customer_id: str, vehicle_id: str) -> Path:
        """Get reports directory for a specific vehicle"""
        return self.get_customer_reports_dir(customer_id) / vehicle_id

    # ==================== REQUIRED DIRECTORIES LIST ====================

    def get_required_directories(self) -> list:
        """
        Get list of all directories that must exist.
        Used for first-run setup and integrity verification.
        """
        return [
            # Top-level
            self.DATA_DIR,
            self.SYSTEM_DIR,
            self.CUSTOMERS_DIR,
            self.AI_DIR,
            self.REPORTS_DIR,
            self.LOGS_DIR,
            self.CACHE_DIR,
            self.TEMP_DIR,

            # System
            self.CONFIG_DIR,

            # AI
            self.AI_RAW_DIR,
            self.AI_RAW_OBD_DIR,
            self.AI_RAW_FEEDBACK_DIR,
            self.AI_CLEANED_DIR,
            self.AI_TRAINING_SETS_DIR,
            self.AI_FEATURE_STORE_DIR,
            self.AI_MODELS_DIR,
            self.AI_PREDICTIONS_DIR,
            self.AI_EXPERIMENTS_DIR,

            # Reports
            self.REPORTS_QUEUE_DIR,
            self.REPORTS_METADATA_DIR,

            # Logs
            self.LOGS_APP_DIR,
            self.LOGS_API_DIR,
            self.LOGS_ERROR_DIR,
            self.LOGS_AUDIT_DIR,
            self.LOGS_ARCHIVE_DIR,

            # Cache
            self.CACHE_API_DIR,
            self.CACHE_COMPUTED_DIR,
            self.CACHE_SESSION_DIR,

            # Temp
            self.TEMP_UPLOADS_DIR,
            self.TEMP_PROCESSING_DIR,
            self.TEMP_DOWNLOADS_DIR,
        ]

    def get_required_files(self) -> Dict[Path, dict]:
        """
        Get dictionary of files that must exist with their default content.
        Used for first-run setup.
        """
        return {
            self.INSTALLATION_FILE: {
                "installed_at": None,  # Will be set during installation
                "version": self.APP_VERSION,
                "schema_version": self.SCHEMA_VERSION,
                "installation_complete": False
            },
            self.SETTINGS_FILE: {
                "server": {
                    "host": self.SERVER_HOST,
                    "port": self.SERVER_PORT
                },
                "logging": {
                    "level": "INFO",
                    "retention_days": self.LOG_RETENTION_DAYS
                },
                "cache": {
                    "ttl_seconds": self.CACHE_TTL_SECONDS,
                    "max_size_mb": self.MAX_CACHE_SIZE_MB
                }
            },
            self.API_KEYS_TEMPLATE: {
                "_comment": "Copy this file to api_keys.json and replace with real keys",
                "openai": "YOUR_OPENAI_KEY_HERE",
                "anthropic": "YOUR_ANTHROPIC_KEY_HERE"
            },
            self.AI_MODELS_REGISTRY: {
                "models": [],
                "active_model": None
            },
            self.REPORTS_INDEX_FILE: {
                "reports": []
            },
            self.REPORTS_QUEUE_FILE: {
                "pending": [],
                "processing": [],
                "completed": [],
                "failed": []
            },
            self.AI_ACCURACY_FILE: {
                "predictions_total": 0,
                "feedback_received": 0,
                "accuracy_by_type": {}
            },
            self.PHYSICS_CONFIG_DIR / "vehicle_models.json": {
                "default_vehicle": {
                    "battery_capacity_ah": 50.0,
                    "engine_displacement_l": 2.0,
                    "fuel_tank_capacity_l": 50.0
                }
            },
            self.AI_ENSEMBLE_DIR / "ensemble_config.json": {
                "weights": {
                    "lstm_baseline": 0.2,
                    "cnn_lstm_hybrid": 0.3,
                    "attention_lstm": 0.4,
                    "lstm_autoencoder": 0.1
                },
                "task_mappings": {
                    "failure_prediction": "attention_lstm",
                    "anomaly_detection": "lstm_autoencoder",
                    "health_assessment": "ensemble"
                }
            }
        }

    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary for debugging"""
        return {
            "root_dir": str(self.ROOT_DIR),
            "data_dir": str(self.DATA_DIR),
            "app_version": self.APP_VERSION,
            "schema_version": self.SCHEMA_VERSION,
            "server_port": self.SERVER_PORT,
            "public_api_url": self.PUBLIC_API_URL
        }


# ==================== GLOBAL INSTANCE ====================

# Singleton configuration instance
_config: Optional[PredictConfig] = None


def get_config() -> PredictConfig:
    """Get the global configuration instance"""
    global _config
    if _config is None:
        _config = PredictConfig()
    return _config


def initialize_config(root_dir: Optional[Path] = None) -> PredictConfig:
    """
    Initialize configuration with optional custom root directory.
    Call this at application startup.
    """
    global _config
    if root_dir:
        _config = PredictConfig(ROOT_DIR=root_dir)
    else:
        _config = PredictConfig()

    logger.info(f"Configuration initialized: {_config.to_dict()}")
    return _config


# ==================== LEGACY PATH COMPATIBILITY ====================
# These provide backward compatibility during migration
# Remove after all files are updated

def get_legacy_paths() -> Dict[str, Path]:
    """
    Map old hardcoded paths to new config paths.
    For use during migration.
    """
    cfg = get_config()
    return {
        # Old desktop paths
        "c:/D Drive/Predict/config/api_keys.json": cfg.API_KEYS_FILE,
        "c:/D Drive/Predict/data/": cfg.DATA_DIR,
        "c:/D Drive/Predict/logs/": cfg.LOGS_DIR,

        # Old server paths
        "C:/OBDserver/API_KEYS": cfg.get_customer_api_keys_dir("default"),
        "C:/D Drive/Predict/data/pdf_queue.json": cfg.REPORTS_QUEUE_FILE,

        # Cloudflare paths (external, keep as-is)
        "C:\\cloudflared\\config.yml": Path("C:/cloudflared/config.yml"),
        "C:\\cloudflared\\cloudflared.exe": Path("C:/cloudflared/cloudflared.exe"),
    }
