"""
Sentry integration for error tracking and performance monitoring.
"""

import logging
import time
from typing import Any, Callable, Optional
from contextlib import contextmanager

try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    _has_sentry = True
except ImportError:
    _has_sentry = False

logger = logging.getLogger(__name__)


class SentryManager:
    """Manages Sentry integration with fallback for development."""
    
    _instance: Optional['SentryManager'] = None
    _initialized = False
    _dsn: Optional[str] = None
    
    def __new__(cls) -> 'SentryManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._enabled = False
        self._environment = "development"
        self._release = None
    
    def init(
        self,
        dsn: Optional[str] = None,
        environment: str = "development",
        release: Optional[str] = None,
        traces_sample_rate: float = 0.1,
        profiles_sample_rate: float = 0.1,
    ) -> bool:
        """
        Initialize Sentry SDK.
        
        Args:
            dsn: Sentry DSN (or None to disable)
            environment: Environment name (dev/staging/prod)
            release: Release version
            traces_sample_rate: APM tracing sample rate
            profiles_sample_rate: Profiling sample rate
        
        Returns:
            True if initialized successfully
        """
        if not _has_sentry:
            logger.warning("Sentry SDK not installed, error tracking disabled")
            return False
        
        if not dsn:
            logger.info("No Sentry DSN provided, error tracking disabled")
            return False
        
        try:
            sentry_sdk.init(
                dsn=dsn,
                environment=environment,
                release=release,
                traces_sample_rate=traces_sample_rate,
                profiles_sample_rate=profiles_sample_rate,
                integrations=[
                    FastApiIntegration(),
                    SqlalchemyIntegration(),
                    RedisIntegration(),
                ],
                enable_tracing=True,
                attach_stacktrace=True,
                send_default_pii=False,
                before_send=self._before_send,
            )
            self._enabled = True
            self._environment = environment
            self._release = release
            self._dsn = dsn
            logger.info(f"Sentry initialized for {environment} environment")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Sentry: {e}")
            return False
    
    def _before_send(self, event: dict, hint: dict) -> Optional[dict]:
        """Filter sensitive data before sending to Sentry."""
        # Sanitize user data
        if 'user' in event:
            user = event['user']
            # Keep only safe identifiers
            event['user'] = {
                'id': user.get('id'),
                'ip_address': '{{auto}}',
            }
        
        # Filter out specific errors we don't want to track
        if 'exception' in event:
            exc = event['exception']
            if 'values' in exc:
                for value in exc['values']:
                    if 'type' in value:
                        error_type = value['type']
                        # Filter expected errors
                        if error_type in ('ValidationError', 'HTTPException'):
                            return None
        
        return event
    
    def is_enabled(self) -> bool:
        """Check if Sentry is enabled."""
        return self._enabled and _has_sentry
    
    def capture_exception(self, exc_info: Any = None, **kwargs) -> Optional[str]:
        """
        Capture an exception.
        
        Args:
            exc_info: Exception info tuple or exception instance
            **kwargs: Additional context
        
        Returns:
            Event ID if captured
        """
        if not self.is_enabled():
            return None
        
        with sentry_sdk.push_scope() as scope:
            for key, value in kwargs.items():
                scope.set_extra(key, value)
            return sentry_sdk.capture_exception(exc_info)
    
    def capture_message(
        self,
        message: str,
        level: str = "info",
        **kwargs,
    ) -> Optional[str]:
        """
        Capture a message.
        
        Args:
            message: Message to capture
            level: Severity level
            **kwargs: Additional context
        
        Returns:
            Event ID if captured
        """
        if not self.is_enabled():
            return None
        
        with sentry_sdk.push_scope() as scope:
            for key, value in kwargs.items():
                scope.set_extra(key, value)
            return sentry_sdk.capture_message(message, level=level)
    
    def set_user(self, user_id: Optional[str], **kwargs) -> None:
        """
        Set user context for current scope.
        
        Args:
            user_id: User identifier
            **kwargs: Additional user attributes
        """
        if not self.is_enabled():
            return
        
        if user_id:
            sentry_sdk.set_user({"id": user_id, **kwargs})
        else:
            sentry_sdk.set_user(None)
    
    def set_tag(self, key: str, value: str) -> None:
        """Set a tag for current scope."""
        if self.is_enabled():
            sentry_sdk.set_tag(key, value)
    
    def set_context(self, key: str, value: dict) -> None:
        """Set context for current scope."""
        if self.is_enabled():
            sentry_sdk.set_context(key, value)
    
    @contextmanager
    def start_transaction(
        self,
        op: str,
        name: str,
        description: Optional[str] = None,
    ):
        """
        Start a performance transaction.
        
        Args:
            op: Operation type (e.g., 'http.request', 'db.query')
            name: Transaction name
            description: Optional description
        
        Yields:
            Transaction context
        """
        if not self.is_enabled():
            yield None
            return
        
        with sentry_sdk.start_transaction(op=op, name=name) as transaction:
            if description:
                transaction.description = description
            yield transaction


# Global instance
_sentry = SentryManager()


def init_sentry(**kwargs) -> bool:
    """Initialize Sentry with config from kwargs or environment."""
    from predict.core.config import get_config
    
    config = get_config()
    
    # Try to get DSN from config or environment
    dsn = kwargs.get('dsn')
    if not dsn:
        dsn = getattr(config, 'SENTRY_DSN', None)
    
    environment = kwargs.get('environment', 'development')
    release = kwargs.get('release', '3.0.0')
    
    return _sentry.init(
        dsn=dsn,
        environment=environment,
        release=release,
        traces_sample_rate=kwargs.get('traces_sample_rate', 0.1),
        profiles_sample_rate=kwargs.get('profiles_sample_rate', 0.1),
    )


def capture_exception(exc_info: Any = None, **kwargs) -> Optional[str]:
    """Capture an exception globally."""
    return _sentry.capture_exception(exc_info, **kwargs)


def capture_message(message: str, level: str = "info", **kwargs) -> Optional[str]:
    """Capture a message globally."""
    return _sentry.capture_message(message, level, **kwargs)


def set_user(user_id: Optional[str], **kwargs) -> None:
    """Set user context globally."""
    _sentry.set_user(user_id, **kwargs)


def set_tag(key: str, value: str) -> None:
    """Set tag globally."""
    _sentry.set_tag(key, value)


def set_context(key: str, value: dict) -> None:
    """Set context globally."""
    _sentry.set_context(key, value)


class Transaction:
    """Simple performance transaction tracker."""
    
    def __init__(self, name: str, op: str = "function"):
        self.name = name
        self.op = op
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration = self.end_time - self.start_time
        
        if exc_type:
            capture_exception(
                (exc_type, exc_val, exc_tb),
                transaction=self.name,
                duration_ms=duration * 1000,
            )
        
        # Log slow transactions
        if duration > 1.0:
            logger.warning(f"Slow transaction '{self.name}': {duration:.2f}s")
    
    @property
    def duration_ms(self) -> float:
        """Get duration in milliseconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0
