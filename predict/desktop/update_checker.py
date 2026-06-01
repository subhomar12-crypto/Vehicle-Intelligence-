"""
Update checker for PREDICT Desktop application.

Runs in background thread to check for available updates.
"""

import logging
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

from PySide6.QtCore import QThread, Signal

from predict.core.version import APP_VERSION

logger = logging.getLogger(__name__)


try:
    import httpx
    _has_httpx = True
except ImportError:
    _has_httpx = False

try:
    import requests
    _has_requests = True
except ImportError:
    _has_requests = False


@dataclass
class UpdateInfo:
    """Information about available update."""
    version: str
    download_url: str
    changelog: str
    release_date: str
    is_critical: bool = False


class UpdateChecker(QThread):
    """
    Background thread for checking application updates.
    
    Signals:
        update_available: Emitted when an update is found
        check_complete: Emitted when check completes (with or without update)
        check_failed: Emitted when check fails
    """
    
    update_available = Signal(dict)  # UpdateInfo as dict
    check_complete = Signal(bool)    # True if update found
    check_failed = Signal(str)       # Error message
    
    # Default update endpoint
    UPDATE_URL = "https://api.predict-vehicle.com/v1/updates"
    
    def __init__(self, parent=None, custom_url: Optional[str] = None):
        super().__init__(parent)
        self.custom_url = custom_url
        self._is_running = False
        self._current_version = APP_VERSION
    
    def run(self) -> None:
        """Run update check in background thread."""
        self._is_running = True
        
        try:
            result = self.check_for_updates()
            
            if result:
                self.update_available.emit(result)
                self.check_complete.emit(True)
            else:
                self.check_complete.emit(False)
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Update check failed: {error_msg}")
            self.check_failed.emit(error_msg)
        
        finally:
            self._is_running = False
    
    def check_for_updates(self) -> Optional[Dict[str, Any]]:
        """
        Check for available updates synchronously.
        
        Returns:
            Update info dict if update available, None otherwise
        """
        url = self.custom_url or self.UPDATE_URL
        
        logger.info(f"Checking for updates from {url}")
        
        # Try HTTP client
        if _has_httpx:
            return self._check_with_httpx(url)
        elif _has_requests:
            return self._check_with_requests(url)
        else:
            logger.warning("No HTTP client available, cannot check for updates")
            return None
    
    def _check_with_httpx(self, url: str) -> Optional[Dict[str, Any]]:
        """Check updates using httpx."""
        try:
            response = httpx.get(
                url,
                params={
                    "version": self._current_version,
                    "platform": "windows",
                },
                timeout=10.0,
                follow_redirects=True,
            )
            response.raise_for_status()
            
            data = response.json()
            return self._parse_response(data)
        
        except Exception as e:
            logger.error(f"HTTP check failed: {e}")
            return None
    
    def _check_with_requests(self, url: str) -> Optional[Dict[str, Any]]:
        """Check updates using requests."""
        try:
            response = requests.get(
                url,
                params={
                    "version": self._current_version,
                    "platform": "windows",
                },
                timeout=10,
            )
            response.raise_for_status()
            
            data = response.json()
            return self._parse_response(data)
        
        except Exception as e:
            logger.error(f"HTTP check failed: {e}")
            return None
    
    def _parse_response(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse API response and check if update is available."""
        if not data.get("update_available", False):
            logger.info("No updates available")
            return None
        
        latest_version = data.get("latest_version", "")
        
        if not self._is_newer_version(latest_version, self._current_version):
            logger.info(f"Latest version {latest_version} is not newer than current {self._current_version}")
            return None
        
        update_info = {
            "version": latest_version,
            "download_url": data.get("download_url", ""),
            "changelog": data.get("changelog", ""),
            "release_date": data.get("release_date", ""),
            "is_critical": data.get("is_critical", False),
        }
        
        logger.info(f"Update available: {latest_version}")
        return update_info
    
    def _is_newer_version(self, latest: str, current: str) -> bool:
        """
        Compare version strings.
        
        Args:
            latest: Latest version string
            current: Current version string
        
        Returns:
            True if latest is newer than current
        """
        try:
            def parse_version(v: str) -> tuple:
                # Remove 'v' prefix if present
                v = v.lstrip('v')
                parts = v.split('.')
                return tuple(int(p) for p in parts if p.isdigit())
            
            latest_parts = parse_version(latest)
            current_parts = parse_version(current)
            
            return latest_parts > current_parts
        
        except Exception as e:
            logger.warning(f"Version comparison failed: {e}")
            # If we can't compare, assume update is available
            return latest != current
    
    def is_running(self) -> bool:
        """Check if update check is currently running."""
        return self._is_running
    
    def get_current_version(self) -> str:
        """Get current application version."""
        return self._current_version


def check_for_updates_sync(url: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Synchronous update check convenience function.
    
    Args:
        url: Optional custom update URL
    
    Returns:
        Update info if available, None otherwise
    """
    checker = UpdateChecker(custom_url=url)
    return checker.check_for_updates()
