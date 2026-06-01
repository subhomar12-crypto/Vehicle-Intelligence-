"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Cloudflare Tunnel

Cloudflare Tunnel Manager
Manages cloudflared tunnel for remote access to OBD servers

Features:
- Self-healing watchdog with auto-restart
- Connection health monitoring
- Exponential backoff on failures
- Graceful recovery from network issues
"""

import subprocess
import logging
import psutil
import time
import requests
from typing import Optional
from datetime import datetime, timedelta
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QThread, QTimer

logger = logging.getLogger(__name__)

# Import portable config
try:
    from config import get_config
    _config = get_config()
    LOGS_DIR = _config.LOGS_DIR
except ImportError:
    LOGS_DIR = Path(__file__).parent / "logs"


class CloudflareTunnel(QObject):
    """
    Manages cloudflared tunnel process with self-healing watchdog.

    Features:
    - Automatic restart on failure
    - Exponential backoff to prevent rapid restart loops
    - Health check monitoring via HTTP
    - Connection state tracking and logging
    """

    status_changed = Signal(bool, str)  # (is_running, message)
    health_check_failed = Signal(str)  # error message
    watchdog_restarted = Signal(int)  # restart count

    def __init__(self, parent=None, auto_restart=True):
        super().__init__(parent)
        self.process: Optional[subprocess.Popen] = None

        # Find cloudflared location - check standard Windows path first
        cloudflare_dir = self._find_cloudflared_dir()
        self.config_path = str(cloudflare_dir / "config.yml")
        self.cloudflared_path = str(cloudflare_dir / "cloudflared.exe")
        self.tunnel_name = "obd-tunnel"

        logger.info(f"Cloudflare tunnel initialized with path: {self.cloudflared_path}")

        # Public URLs
        self.main_url = "https://predict.previlium.com"
        self.pdf_url = "https://pdf.previlium.com"

        # Watchdog settings
        self.auto_restart_enabled = auto_restart
        self.max_restart_attempts = 10
        self.restart_count = 0
        self.last_restart_time: Optional[datetime] = None
        self.consecutive_failures = 0

        # Exponential backoff settings
        self.base_backoff_seconds = 5
        self.max_backoff_seconds = 300  # 5 minutes max
        self.current_backoff = self.base_backoff_seconds

        # Health check settings
        self.health_check_timeout = 10  # seconds
        self.health_check_interval = 30  # seconds
        self.last_health_check: Optional[datetime] = None
        self.last_successful_health_check: Optional[datetime] = None

        # Status check timer (basic process check)
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._check_status)
        self.status_timer.start(5000)  # Check every 5 seconds

        # Health check timer (HTTP connectivity test)
        self.health_timer = QTimer()
        self.health_timer.timeout.connect(self._perform_health_check)
        self.health_timer.start(self.health_check_interval * 1000)

        # Watchdog timer (auto-restart logic)
        self.watchdog_timer = QTimer()
        self.watchdog_timer.timeout.connect(self._watchdog_check)
        if self.auto_restart_enabled:
            self.watchdog_timer.start(10000)  # Check every 10 seconds

        logger.info(f"CloudflareTunnel initialized (auto_restart={auto_restart})")

    def _find_cloudflared_dir(self) -> Path:
        """
        Find cloudflared installation directory.
        Priority:
        1. C:\\cloudflared (standard Windows location)
        2. Config CLOUDFLARE_DIR
        3. App directory fallback
        """
        import os

        # Check standard Windows location FIRST
        standard_path = Path(r"C:\cloudflared")
        if standard_path.exists() and (standard_path / "cloudflared.exe").exists():
            logger.info(f"Found cloudflared at standard location: {standard_path}")
            return standard_path

        # Check environment variable
        env_path = os.environ.get("CLOUDFLARE_DIR")
        if env_path:
            env_dir = Path(env_path)
            if env_dir.exists() and (env_dir / "cloudflared.exe").exists():
                logger.info(f"Found cloudflared from env: {env_dir}")
                return env_dir

        # Try config path
        try:
            if _config and _config.CLOUDFLARE_DIR.exists():
                if (_config.CLOUDFLARE_DIR / "cloudflared.exe").exists():
                    logger.info(f"Found cloudflared from config: {_config.CLOUDFLARE_DIR}")
                    return _config.CLOUDFLARE_DIR
        except:
            pass

        # Fallback to app directory
        fallback = Path(__file__).parent / "cloudflared"
        logger.warning(f"Using fallback cloudflared path: {fallback}")
        return fallback

    def start_tunnel(self) -> bool:
        """Start the cloudflared tunnel"""
        try:
            if self.is_running():
                logger.info("Tunnel already running")
                self.status_changed.emit(True, "Tunnel already running")
                return True

            logger.info("Starting cloudflared tunnel...")

            # Start cloudflared process
            self.process = subprocess.Popen(
                [
                    self.cloudflared_path,
                    "tunnel",
                    "--config", self.config_path,
                    "run",
                    self.tunnel_name
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            # Give it a moment to start
            QThread.msleep(2000)

            if self.is_running():
                logger.info("Tunnel started successfully")
                self.status_changed.emit(True, "Tunnel started successfully")
                return True
            else:
                logger.error("Tunnel failed to start")
                self.status_changed.emit(False, "Tunnel failed to start")
                return False

        except FileNotFoundError:
            error_msg = f"cloudflared.exe not found at {self.cloudflared_path}"
            logger.error(error_msg)
            self.status_changed.emit(False, error_msg)
            return False
        except Exception as e:
            error_msg = f"Failed to start tunnel: {str(e)}"
            logger.error(error_msg)
            self.status_changed.emit(False, error_msg)
            return False

    def stop_tunnel(self) -> bool:
        """Stop the cloudflared tunnel"""
        try:
            if not self.is_running():
                logger.info("Tunnel not running")
                self.status_changed.emit(False, "Tunnel not running")
                return True

            logger.info("Stopping cloudflared tunnel...")

            # Kill the process
            if self.process:
                self.process.terminate()
                self.process.wait(timeout=5)
                self.process = None

            # Also kill any orphaned cloudflared processes
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'] == 'cloudflared.exe':
                        proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            logger.info("Tunnel stopped")
            self.status_changed.emit(False, "Tunnel stopped")
            return True

        except Exception as e:
            error_msg = f"Failed to stop tunnel: {str(e)}"
            logger.error(error_msg)
            return False

    def is_running(self) -> bool:
        """Check if cloudflared tunnel is running"""
        try:
            # Check if our process is alive
            if self.process and self.process.poll() is None:
                return True

            # Check for any cloudflared processes
            for proc in psutil.process_iter(['name', 'cmdline']):
                try:
                    if proc.info['name'] == 'cloudflared.exe':
                        cmdline = proc.info.get('cmdline', [])
                        if cmdline and self.tunnel_name in ' '.join(cmdline):
                            return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            return False

        except Exception as e:
            logger.error(f"Error checking tunnel status: {e}")
            return False

    def _check_status(self):
        """Periodically check tunnel status"""
        is_running = self.is_running()
        if is_running:
            self.status_changed.emit(True, "Tunnel running")
        else:
            if self.process:
                # Process died unexpectedly
                self.process = None
                self.consecutive_failures += 1
                self.status_changed.emit(False, "Tunnel stopped unexpectedly")
                logger.warning(f"Tunnel stopped unexpectedly (failures: {self.consecutive_failures})")

    def _perform_health_check(self):
        """Perform HTTP health check to verify tunnel connectivity"""
        self.last_health_check = datetime.now()

        try:
            # Try to reach the health endpoint through the tunnel
            response = requests.get(
                f"{self.main_url}/health",
                timeout=self.health_check_timeout
            )

            if response.status_code == 200:
                self.last_successful_health_check = datetime.now()
                self.consecutive_failures = 0
                self.current_backoff = self.base_backoff_seconds
                logger.debug("Health check passed")
            else:
                self.consecutive_failures += 1
                error_msg = f"Health check failed: HTTP {response.status_code}"
                logger.warning(error_msg)
                self.health_check_failed.emit(error_msg)

        except requests.exceptions.Timeout:
            self.consecutive_failures += 1
            error_msg = "Health check timeout - tunnel may be down"
            logger.warning(error_msg)
            self.health_check_failed.emit(error_msg)

        except requests.exceptions.ConnectionError:
            self.consecutive_failures += 1
            error_msg = "Health check connection error - tunnel unreachable"
            logger.warning(error_msg)
            self.health_check_failed.emit(error_msg)

        except Exception as e:
            self.consecutive_failures += 1
            error_msg = f"Health check error: {str(e)}"
            logger.error(error_msg)
            self.health_check_failed.emit(error_msg)

    def _watchdog_check(self):
        """Watchdog logic - auto-restart tunnel if needed"""
        if not self.auto_restart_enabled:
            return

        # Check if tunnel should be restarted
        should_restart = False
        reason = ""

        # Case 1: Process not running
        if not self.is_running():
            should_restart = True
            reason = "Process not running"

        # Case 2: Too many consecutive health check failures
        elif self.consecutive_failures >= 3:
            should_restart = True
            reason = f"Health check failures: {self.consecutive_failures}"

        # Case 3: No successful health check for too long
        elif self.last_successful_health_check:
            time_since_success = datetime.now() - self.last_successful_health_check
            if time_since_success > timedelta(minutes=5):
                should_restart = True
                reason = f"No successful health check for {time_since_success.seconds}s"

        if should_restart:
            self._attempt_restart(reason)

    def _attempt_restart(self, reason: str):
        """Attempt to restart the tunnel with exponential backoff"""
        # Check if we've exceeded max restart attempts
        if self.restart_count >= self.max_restart_attempts:
            logger.error(f"Max restart attempts ({self.max_restart_attempts}) exceeded")
            self.auto_restart_enabled = False
            self.status_changed.emit(False, "Auto-restart disabled: max attempts exceeded")
            return

        # Check backoff timing
        if self.last_restart_time:
            time_since_restart = (datetime.now() - self.last_restart_time).total_seconds()
            if time_since_restart < self.current_backoff:
                # Still in backoff period
                remaining = self.current_backoff - time_since_restart
                logger.debug(f"Backoff: waiting {remaining:.0f}s before restart")
                return

        # Perform restart
        logger.warning(f"Watchdog restarting tunnel (reason: {reason})")

        # Stop existing process
        self.stop_tunnel()

        # Wait a moment
        time.sleep(2)

        # Start tunnel
        success = self.start_tunnel()

        # Update counters
        self.restart_count += 1
        self.last_restart_time = datetime.now()

        if success:
            logger.info(f"Watchdog restart #{self.restart_count} successful")
            self.watchdog_restarted.emit(self.restart_count)
            # Reset backoff on success after a few seconds
            # (backoff will fully reset after successful health check)
        else:
            # Increase backoff on failure
            self.current_backoff = min(
                self.current_backoff * 2,
                self.max_backoff_seconds
            )
            logger.warning(f"Restart failed, backoff increased to {self.current_backoff}s")

    def reset_watchdog(self):
        """Reset watchdog counters (call after manual intervention)"""
        self.restart_count = 0
        self.consecutive_failures = 0
        self.current_backoff = self.base_backoff_seconds
        self.auto_restart_enabled = True
        logger.info("Watchdog counters reset")

    def get_watchdog_status(self) -> dict:
        """Get current watchdog status"""
        return {
            'auto_restart_enabled': self.auto_restart_enabled,
            'restart_count': self.restart_count,
            'max_restart_attempts': self.max_restart_attempts,
            'consecutive_failures': self.consecutive_failures,
            'current_backoff': self.current_backoff,
            'last_restart': self.last_restart_time.isoformat() if self.last_restart_time else None,
            'last_health_check': self.last_health_check.isoformat() if self.last_health_check else None,
            'last_successful_health_check': self.last_successful_health_check.isoformat() if self.last_successful_health_check else None,
            'tunnel_running': self.is_running()
        }

    def get_main_url(self) -> str:
        """Get the main API public URL"""
        return self.main_url

    def get_pdf_url(self) -> str:
        """Get the PDF API public URL"""
        return self.pdf_url

    def cleanup(self):
        """Cleanup on exit"""
        # Stop all timers
        self.status_timer.stop()
        self.health_timer.stop()
        self.watchdog_timer.stop()

        # Terminate process
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except:
                pass

        logger.info("CloudflareTunnel cleanup complete")


# =============================================================================
# STANDALONE WATCHDOG SERVICE (for running without GUI)
# =============================================================================

class CloudflareTunnelWatchdog:
    """
    Standalone watchdog service for running without PyQt GUI.
    Can be run as a Windows service or background process.
    """

    def __init__(self, auto_start=True):
        self.config_path = str(_config.CLOUDFLARE_DIR / "config.yml")
        self.cloudflared_path = str(_config.CLOUDFLARE_DIR / "cloudflared.exe")
        self.tunnel_name = "obd-tunnel"
        self.main_url = "https://predict.previlium.com"

        # Watchdog settings
        self.check_interval = 30  # seconds
        self.max_restart_attempts = 10
        self.restart_count = 0
        self.consecutive_failures = 0
        self.base_backoff = 5
        self.current_backoff = self.base_backoff
        self.max_backoff = 300

        self.running = False
        self.process: Optional[subprocess.Popen] = None

        if auto_start:
            self.start()

    def start(self):
        """Start the watchdog service"""
        self.running = True
        logger.info("Starting standalone tunnel watchdog")

        # Initial tunnel start
        self._start_tunnel()

        # Main watchdog loop
        while self.running:
            try:
                self._watchdog_loop()
                time.sleep(self.check_interval)
            except KeyboardInterrupt:
                logger.info("Watchdog interrupted")
                break
            except Exception as e:
                logger.error(f"Watchdog error: {e}")
                time.sleep(self.check_interval)

        self.stop()

    def stop(self):
        """Stop the watchdog service"""
        self.running = False
        self._stop_tunnel()
        logger.info("Watchdog stopped")

    def _start_tunnel(self) -> bool:
        """Start cloudflared tunnel"""
        try:
            if self._is_running():
                return True

            logger.info("Starting cloudflared tunnel...")

            self.process = subprocess.Popen(
                [
                    self.cloudflared_path,
                    "tunnel",
                    "--config", self.config_path,
                    "run",
                    self.tunnel_name
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            time.sleep(3)
            return self._is_running()

        except Exception as e:
            logger.error(f"Failed to start tunnel: {e}")
            return False

    def _stop_tunnel(self):
        """Stop cloudflared tunnel"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except:
                pass
            self.process = None

        # Kill any orphaned processes
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] == 'cloudflared.exe':
                    proc.kill()
            except:
                pass

    def _is_running(self) -> bool:
        """Check if tunnel is running"""
        if self.process and self.process.poll() is None:
            return True

        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                if proc.info['name'] == 'cloudflared.exe':
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and self.tunnel_name in ' '.join(cmdline):
                        return True
            except:
                pass

        return False

    def _health_check(self) -> bool:
        """Perform HTTP health check"""
        try:
            response = requests.get(f"{self.main_url}/health", timeout=10)
            return response.status_code == 200
        except:
            return False

    def _watchdog_loop(self):
        """Main watchdog logic"""
        is_running = self._is_running()
        is_healthy = self._health_check() if is_running else False

        if is_running and is_healthy:
            # Everything OK
            self.consecutive_failures = 0
            self.current_backoff = self.base_backoff
            return

        # Need restart
        self.consecutive_failures += 1

        if self.consecutive_failures >= 3:
            if self.restart_count >= self.max_restart_attempts:
                logger.error("Max restart attempts exceeded, giving up")
                self.running = False
                return

            # Backoff check
            time.sleep(self.current_backoff)

            logger.warning(f"Restarting tunnel (attempt {self.restart_count + 1})")
            self._stop_tunnel()
            time.sleep(2)

            if self._start_tunnel():
                self.restart_count += 1
                logger.info(f"Restart successful (#{self.restart_count})")
            else:
                self.current_backoff = min(self.current_backoff * 2, self.max_backoff)
                logger.warning(f"Restart failed, backoff: {self.current_backoff}s")
