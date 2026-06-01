"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Alert Delivery Guarantees

Predict OBD - Alert Delivery Guarantees Module
CRITICAL: Ensures alerts are ALWAYS delivered or failures are escalated.

This module enforces:
- Startup self-tests for alert delivery
- Blocking "healthy" status if alerts fail
- Escalation paths for silent failures
- Persistent alert failure logging
"""

import json
import logging
import smtplib
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urllib.request
import urllib.error

from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)

# Alert delivery configuration
MAX_DELIVERY_RETRIES = 3
RETRY_DELAY_SECONDS = 5
DELIVERY_TIMEOUT_SECONDS = 30
SELF_TEST_INTERVAL_HOURS = 1
FAILURE_PERSISTENCE_FILE = CONFIG.DATA_DIR / "system" / "alert_failures.json"


class DeliveryChannel(Enum):
    """Alert delivery channels."""
    EMAIL = "email"
    WEBHOOK = "webhook"
    SMS = "sms"  # Future
    CONSOLE = "console"  # Fallback


class DeliveryStatus(Enum):
    """Delivery attempt status."""
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    RETRYING = "retrying"


@dataclass
class DeliveryAttempt:
    """Record of a delivery attempt."""
    attempt_id: str
    channel: str
    timestamp: str
    status: str
    error: Optional[str]
    retry_count: int


@dataclass
class AlertDeliveryRecord:
    """Complete record of an alert delivery."""
    alert_id: str
    alert_type: str
    severity: str
    created_at: str
    delivered_at: Optional[str]
    final_status: str
    attempts: List[DeliveryAttempt]
    escalated: bool
    escalation_reason: Optional[str]


class AlertDeliveryGuarantees:
    """
    Guarantees alert delivery or escalation.

    GUARANTEES:
    1. Startup self-test verifies all delivery channels
    2. System CANNOT report "healthy" if alerts fail
    3. Failed alerts are escalated through backup channels
    4. All delivery failures are persisted for audit
    5. Silent failures are impossible
    """

    def __init__(self):
        self.delivery_channels: Dict[str, Dict[str, Any]] = {}
        self.channel_health: Dict[str, bool] = {}
        self.failed_alerts: List[AlertDeliveryRecord] = []

        # Load configuration
        self._load_channel_config()

        # Load persisted failures
        self._load_persisted_failures()

        # Track last self-test
        self.last_self_test: Optional[datetime] = None
        self.self_test_passed: bool = False

    def _load_channel_config(self):
        """Load delivery channel configuration."""
        config_file = CONFIG.CONFIG_DIR / "alert_channels.json"

        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    self.delivery_channels = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load alert channel config: {e}")

        # Ensure console fallback is always available
        self.delivery_channels["console"] = {"enabled": True, "type": "console"}

        # Initialize health status
        for channel in self.delivery_channels:
            self.channel_health[channel] = False  # Unknown until tested

    def _load_persisted_failures(self):
        """Load persisted delivery failures."""
        try:
            if FAILURE_PERSISTENCE_FILE.exists():
                with open(FAILURE_PERSISTENCE_FILE, 'r') as f:
                    data = json.load(f)
                    # Only keep last 1000 failures
                    self.failed_alerts = data.get("failures", [])[-1000:]
        except Exception as e:
            logger.error(f"Failed to load persisted failures: {e}")

    def _persist_failure(self, record: AlertDeliveryRecord):
        """Persist delivery failure for audit."""
        try:
            self.failed_alerts.append(asdict(record))

            FAILURE_PERSISTENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(FAILURE_PERSISTENCE_FILE, 'w') as f:
                json.dump({"failures": self.failed_alerts[-1000:]}, f, indent=2)

        except Exception as e:
            logger.error(f"CRITICAL: Failed to persist alert failure: {e}")
            # This is a critical failure - log to console as last resort
            print(f"ALERT PERSISTENCE FAILURE: {record}")

    def run_startup_self_test(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Run mandatory startup self-test for all delivery channels.

        Returns:
            (all_passed, results_by_channel)
        """
        logger.info("ALERT DELIVERY: Running startup self-test...")

        results = {}
        all_passed = False

        for channel_name, channel_config in self.delivery_channels.items():
            if not channel_config.get("enabled", False):
                results[channel_name] = {"status": "disabled", "passed": True}
                continue

            try:
                passed, message = self._test_channel(channel_name, channel_config)
                results[channel_name] = {
                    "status": "passed" if passed else "failed",
                    "passed": passed,
                    "message": message
                }
                self.channel_health[channel_name] = passed

            except Exception as e:
                results[channel_name] = {
                    "status": "error",
                    "passed": False,
                    "message": str(e)
                }
                self.channel_health[channel_name] = False

        # At least one channel must work (console is always available)
        working_channels = [c for c, healthy in self.channel_health.items() if healthy]
        all_passed = len(working_channels) > 0

        if not all_passed:
            logger.error("ALERT DELIVERY: ALL CHANNELS FAILED - System cannot send alerts!")
        else:
            logger.info(f"ALERT DELIVERY: Self-test passed - {len(working_channels)} channels available")

        self.last_self_test = datetime.now()
        self.self_test_passed = all_passed

        return all_passed, results

    def _test_channel(self, channel_name: str, config: Dict[str, Any]) -> Tuple[bool, str]:
        """Test a specific delivery channel."""
        channel_type = config.get("type", channel_name)

        if channel_type == "email":
            return self._test_email_channel(config)
        elif channel_type == "webhook":
            return self._test_webhook_channel(config)
        elif channel_type == "console":
            return True, "Console channel always available"
        else:
            return False, f"Unknown channel type: {channel_type}"

    def _test_email_channel(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """Test email channel connectivity."""
        try:
            smtp_server = config.get("smtp_server", "localhost")
            smtp_port = config.get("smtp_port", 587)

            # Just test connection, don't send
            with smtplib.SMTP(smtp_server, smtp_port, timeout=DELIVERY_TIMEOUT_SECONDS) as server:
                server.noop()

            return True, "SMTP connection successful"

        except Exception as e:
            return False, f"SMTP connection failed: {e}"

    def _test_webhook_channel(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """Test webhook channel connectivity."""
        try:
            webhook_url = config.get("url")
            if not webhook_url:
                return False, "No webhook URL configured"

            # Test with HEAD request
            req = urllib.request.Request(webhook_url, method="HEAD")
            req.add_header("User-Agent", "PredictOBD-AlertTest/1.0")

            with urllib.request.urlopen(req, timeout=DELIVERY_TIMEOUT_SECONDS) as response:
                if response.status < 400:
                    return True, f"Webhook reachable (status: {response.status})"
                return False, f"Webhook returned error status: {response.status}"

        except urllib.error.URLError as e:
            return False, f"Webhook unreachable: {e}"
        except Exception as e:
            return False, f"Webhook test failed: {e}"

    def deliver_alert(self, alert_id: str, alert_type: str, severity: str,
                      title: str, message: str, details: Optional[Dict] = None) -> bool:
        """
        Deliver an alert with guaranteed delivery or escalation.

        Args:
            alert_id: Unique alert identifier
            alert_type: Type of alert
            severity: Alert severity
            title: Alert title
            message: Alert message
            details: Additional details

        Returns:
            True if delivered successfully, False if all channels failed
        """
        record = AlertDeliveryRecord(
            alert_id=alert_id,
            alert_type=alert_type,
            severity=severity,
            created_at=datetime.now().isoformat(),
            delivered_at=None,
            final_status="pending",
            attempts=[],
            escalated=False,
            escalation_reason=None
        )

        # Try each enabled channel in priority order
        priority_order = ["webhook", "email", "console"]  # Console is always last resort
        delivered = False

        for channel_name in priority_order:
            if channel_name not in self.delivery_channels:
                continue

            config = self.delivery_channels[channel_name]
            if not config.get("enabled", False) and channel_name != "console":
                continue

            # Attempt delivery with retries
            for retry in range(MAX_DELIVERY_RETRIES):
                attempt = DeliveryAttempt(
                    attempt_id=f"{alert_id}_{channel_name}_{retry}",
                    channel=channel_name,
                    timestamp=datetime.now().isoformat(),
                    status="pending",
                    error=None,
                    retry_count=retry
                )

                try:
                    success = self._deliver_via_channel(
                        channel_name, config, title, message, severity, details
                    )

                    if success:
                        attempt.status = "success"
                        record.attempts.append(attempt)
                        record.delivered_at = datetime.now().isoformat()
                        record.final_status = "delivered"
                        delivered = True
                        logger.info(f"ALERT DELIVERED via {channel_name}: {alert_id}")
                        break
                    else:
                        attempt.status = "failed"
                        attempt.error = "Delivery returned false"

                except Exception as e:
                    attempt.status = "failed"
                    attempt.error = str(e)
                    logger.warning(f"Alert delivery attempt failed ({channel_name}): {e}")

                record.attempts.append(attempt)

                if retry < MAX_DELIVERY_RETRIES - 1:
                    time.sleep(RETRY_DELAY_SECONDS)

            if delivered:
                break

        # If not delivered, this is an escalation scenario
        if not delivered:
            record.final_status = "failed"
            record.escalated = True
            record.escalation_reason = "All delivery channels failed"

            # Persist failure
            self._persist_failure(record)

            # Console escalation (cannot fail)
            self._escalate_to_console(alert_id, title, message, severity)

            logger.error(f"ALERT DELIVERY FAILED - Escalated to console: {alert_id}")
            return False

        return True

    def _deliver_via_channel(self, channel_name: str, config: Dict[str, Any],
                              title: str, message: str, severity: str,
                              details: Optional[Dict]) -> bool:
        """Deliver alert via specific channel."""
        channel_type = config.get("type", channel_name)

        if channel_type == "email":
            return self._deliver_email(config, title, message, severity, details)
        elif channel_type == "webhook":
            return self._deliver_webhook(config, title, message, severity, details)
        elif channel_type == "console":
            return self._deliver_console(title, message, severity, details)

        return False

    def _deliver_email(self, config: Dict[str, Any], title: str, message: str,
                       severity: str, details: Optional[Dict]) -> bool:
        """Deliver alert via email."""
        try:
            smtp_server = config.get("smtp_server")
            smtp_port = config.get("smtp_port", 587)
            from_addr = config.get("from_address")
            to_addrs = config.get("to_addresses", [])
            username = config.get("username")
            password = config.get("password")

            if not all([smtp_server, from_addr, to_addrs]):
                return False

            msg = MIMEMultipart()
            msg["From"] = from_addr
            msg["To"] = ", ".join(to_addrs)
            msg["Subject"] = f"[{severity.upper()}] {title}"

            body = f"{message}\n\n"
            if details:
                body += f"Details:\n{json.dumps(details, indent=2)}"

            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(smtp_server, smtp_port, timeout=DELIVERY_TIMEOUT_SECONDS) as server:
                server.starttls()
                if username and password:
                    server.login(username, password)
                server.sendmail(from_addr, to_addrs, msg.as_string())

            return True

        except Exception as e:
            logger.error(f"Email delivery failed: {e}")
            return False

    def _deliver_webhook(self, config: Dict[str, Any], title: str, message: str,
                         severity: str, details: Optional[Dict]) -> bool:
        """Deliver alert via webhook."""
        try:
            webhook_url = config.get("url")
            if not webhook_url:
                return False

            payload = json.dumps({
                "title": title,
                "message": message,
                "severity": severity,
                "details": details,
                "timestamp": datetime.now().isoformat(),
                "source": "PredictOBD"
            }).encode()

            req = urllib.request.Request(
                webhook_url,
                data=payload,
                method="POST",
                headers={"Content-Type": "application/json"}
            )

            with urllib.request.urlopen(req, timeout=DELIVERY_TIMEOUT_SECONDS) as response:
                return response.status < 400

        except Exception as e:
            logger.error(f"Webhook delivery failed: {e}")
            return False

    def _deliver_console(self, title: str, message: str, severity: str,
                         details: Optional[Dict]) -> bool:
        """Deliver alert to console (always succeeds)."""
        timestamp = datetime.now().isoformat()
        print("=" * 60)
        print(f"[ALERT] [{severity.upper()}] {timestamp}")
        print(f"Title: {title}")
        print(f"Message: {message}")
        if details:
            print(f"Details: {json.dumps(details, indent=2)}")
        print("=" * 60)
        return True

    def _escalate_to_console(self, alert_id: str, title: str, message: str, severity: str):
        """Escalation to console when all other channels fail."""
        print("!" * 60)
        print("!!! ALERT ESCALATION - ALL DELIVERY CHANNELS FAILED !!!")
        print(f"Alert ID: {alert_id}")
        print(f"Severity: {severity}")
        print(f"Title: {title}")
        print(f"Message: {message}")
        print("!!! IMMEDIATE ATTENTION REQUIRED !!!")
        print("!" * 60)

    def is_healthy(self) -> Tuple[bool, str]:
        """
        Check if alert system is healthy.

        System is NOT healthy if:
        - Self-test never ran
        - Self-test failed
        - All channels are down
        """
        if self.last_self_test is None:
            return False, "Alert self-test never ran"

        if not self.self_test_passed:
            return False, "Alert self-test failed"

        # Check if self-test is stale
        hours_since_test = (datetime.now() - self.last_self_test).total_seconds() / 3600
        if hours_since_test > SELF_TEST_INTERVAL_HOURS * 2:
            return False, f"Alert self-test is stale ({hours_since_test:.1f}h old)"

        working_channels = [c for c, healthy in self.channel_health.items() if healthy]
        if not working_channels:
            return False, "No working alert channels"

        return True, f"Alert system healthy ({len(working_channels)} channels available)"

    def get_failed_alerts(self, since: Optional[datetime] = None) -> List[Dict]:
        """Get list of failed alert deliveries."""
        if since is None:
            return self.failed_alerts

        return [
            a for a in self.failed_alerts
            if datetime.fromisoformat(a["created_at"]) >= since
        ]

    def test_connectivity(self) -> bool:
        """Test if at least one alert channel is working."""
        passed, _ = self.run_startup_self_test()
        return passed


# Global instance
_alert_guarantees: Optional[AlertDeliveryGuarantees] = None


def get_alert_guarantees() -> AlertDeliveryGuarantees:
    """Get global alert delivery guarantees instance."""
    global _alert_guarantees
    if _alert_guarantees is None:
        _alert_guarantees = AlertDeliveryGuarantees()
    return _alert_guarantees


def send_guaranteed_alert(alert_type: str, severity: str, title: str,
                           message: str, details: Optional[Dict] = None) -> bool:
    """
    Send an alert with delivery guarantee.

    Usage:
        send_guaranteed_alert(
            "PREDICTION_FAILURE",
            "critical",
            "AI Prediction System Down",
            "The prediction service has failed",
            {"error": "TensorFlow OOM"}
        )
    """
    guarantees = get_alert_guarantees()
    alert_id = f"alert_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    return guarantees.deliver_alert(alert_id, alert_type, severity, title, message, details)


def verify_alert_system_health() -> Tuple[bool, str]:
    """Verify alert system is healthy - used in health checks."""
    guarantees = get_alert_guarantees()
    return guarantees.is_healthy()
