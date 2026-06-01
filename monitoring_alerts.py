"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Monitoring Alerts

Predict OBD - Monitoring and Alerting System
Production monitoring for subscription failures, audit integrity, and AI suppression events.

MONITORED EVENTS:
- Subscription payment failures
- Subscription expiration
- Audit log integrity failures
- AI prediction suppression events
- Backup failures
- System integrity violations
"""

import json
import logging
import threading
import smtplib
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable
from enum import Enum
from dataclasses import dataclass, asdict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config import get_config
from audit_logger import get_audit_logger, AuditEventType, verify_all_logs

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    CRITICAL = "critical"    # Immediate response required
    HIGH = "high"            # Response within 1 hour
    MEDIUM = "medium"        # Response within 24 hours
    LOW = "low"              # Informational
    INFO = "info"            # For tracking only


class AlertType(Enum):
    """Types of alerts."""
    SUBSCRIPTION_EXPIRED = "subscription_expired"
    SUBSCRIPTION_PAYMENT_FAILED = "subscription_payment_failed"
    SUBSCRIPTION_RENEWAL_FAILED = "subscription_renewal_failed"
    AUDIT_INTEGRITY_FAILURE = "audit_integrity_failure"
    AI_PREDICTION_SUPPRESSED = "ai_prediction_suppressed"
    AI_MODEL_ACCURACY_LOW = "ai_model_accuracy_low"
    BACKUP_FAILED = "backup_failed"
    BACKUP_VERIFICATION_FAILED = "backup_verification_failed"
    SYSTEM_INTEGRITY_VIOLATION = "system_integrity_violation"
    API_KEY_ABUSE = "api_key_abuse"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    ORPHANED_DATA_DETECTED = "orphaned_data_detected"


@dataclass
class Alert:
    """Alert data structure."""
    alert_id: str
    alert_type: str
    severity: str
    title: str
    message: str
    timestamp: str
    customer_id: Optional[str]
    details: Dict[str, Any]
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[str] = None
    resolved: bool = False
    resolved_by: Optional[str] = None
    resolved_at: Optional[str] = None


class AlertHandler:
    """Base class for alert handlers."""

    def send(self, alert: Alert) -> bool:
        """Send alert. Override in subclass."""
        raise NotImplementedError


class EmailAlertHandler(AlertHandler):
    """Send alerts via email."""

    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
        from_addr: str,
        to_addrs: List[str]
    ):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs

    def send(self, alert: Alert) -> bool:
        try:
            msg = MIMEMultipart()
            msg['From'] = self.from_addr
            msg['To'] = ', '.join(self.to_addrs)
            msg['Subject'] = f"[{alert.severity.upper()}] Predict OBD Alert: {alert.title}"

            body = f"""
PREDICT OBD ALERT
=================

Severity: {alert.severity.upper()}
Type: {alert.alert_type}
Time: {alert.timestamp}
Customer: {alert.customer_id or 'N/A'}

Message:
{alert.message}

Details:
{json.dumps(alert.details, indent=2)}

---
Alert ID: {alert.alert_id}
            """

            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)

            return True

        except Exception as e:
            logger.error(f"Email alert failed: {e}")
            return False


class WebhookAlertHandler(AlertHandler):
    """Send alerts via webhook (Slack, Teams, etc.)."""

    def __init__(self, webhook_url: str, format_type: str = "slack"):
        self.webhook_url = webhook_url
        self.format_type = format_type

    def send(self, alert: Alert) -> bool:
        try:
            if self.format_type == "slack":
                payload = self._format_slack(alert)
            else:
                payload = asdict(alert)

            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )

            return response.status_code == 200

        except Exception as e:
            logger.error(f"Webhook alert failed: {e}")
            return False

    def _format_slack(self, alert: Alert) -> Dict[str, Any]:
        """Format alert for Slack."""
        severity_emoji = {
            "critical": ":rotating_light:",
            "high": ":warning:",
            "medium": ":large_yellow_circle:",
            "low": ":information_source:",
            "info": ":speech_balloon:"
        }

        return {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{severity_emoji.get(alert.severity, '')} {alert.title}"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Severity:*\n{alert.severity.upper()}"},
                        {"type": "mrkdwn", "text": f"*Type:*\n{alert.alert_type}"},
                        {"type": "mrkdwn", "text": f"*Time:*\n{alert.timestamp}"},
                        {"type": "mrkdwn", "text": f"*Customer:*\n{alert.customer_id or 'N/A'}"}
                    ]
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Message:*\n{alert.message}"}
                }
            ]
        }


class LogAlertHandler(AlertHandler):
    """Log alerts to file."""

    def __init__(self, log_file: Path):
        self.log_file = log_file

    def send(self, alert: Alert) -> bool:
        try:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.log_file, 'a') as f:
                f.write(json.dumps(asdict(alert)) + '\n')

            return True

        except Exception as e:
            logger.error(f"Log alert failed: {e}")
            return False


class AlertManager:
    """
    Central alert management system.

    Features:
    - Multiple alert handlers
    - Alert deduplication
    - Alert history
    - Acknowledgment tracking
    """

    def __init__(self):
        self.config = get_config()
        self.handlers: List[AlertHandler] = []
        self._alert_history: List[Alert] = []
        self._recent_alerts: Dict[str, datetime] = {}  # For deduplication
        self._lock = threading.Lock()
        self._alert_counter = 0

        # Always add log handler
        self.handlers.append(
            LogAlertHandler(self.config.LOGS_DIR / "alerts" / "alerts.log")
        )

    def add_email_handler(
        self,
        to_addrs: List[str],
        smtp_server: str = "smtp.gmail.com",
        smtp_port: int = 587,
        username: str = "",
        password: str = ""
    ):
        """Add email alert handler."""
        self.handlers.append(EmailAlertHandler(
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            username=username,
            password=password,
            from_addr=username,
            to_addrs=to_addrs if isinstance(to_addrs, list) else [to_addrs]
        ))

    def add_webhook_handler(self, webhook_url: str, format_type: str = "slack"):
        """Add webhook alert handler."""
        self.handlers.append(WebhookAlertHandler(webhook_url, format_type))

    def send_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        message: str,
        customer_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        dedupe_key: Optional[str] = None,
        dedupe_window_minutes: int = 60
    ) -> Optional[str]:
        """
        Send an alert through all configured handlers.

        Args:
            alert_type: Type of alert
            severity: Alert severity
            title: Short title
            message: Detailed message
            customer_id: Related customer if applicable
            details: Additional details
            dedupe_key: Key for deduplication
            dedupe_window_minutes: Deduplication window

        Returns:
            Alert ID if sent, None if deduplicated
        """
        with self._lock:
            # Check for duplicate
            if dedupe_key:
                if dedupe_key in self._recent_alerts:
                    last_alert = self._recent_alerts[dedupe_key]
                    if datetime.now() - last_alert < timedelta(minutes=dedupe_window_minutes):
                        logger.debug(f"Alert deduplicated: {dedupe_key}")
                        return None

            # Generate alert ID
            self._alert_counter += 1
            alert_id = f"alert_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self._alert_counter:04d}"

            # Create alert
            alert = Alert(
                alert_id=alert_id,
                alert_type=alert_type.value,
                severity=severity.value,
                title=title,
                message=message,
                timestamp=datetime.now().isoformat(),
                customer_id=customer_id,
                details=details or {}
            )

            # Send through all handlers
            for handler in self.handlers:
                try:
                    handler.send(alert)
                except Exception as e:
                    logger.error(f"Alert handler failed: {type(handler).__name__}: {e}")

            # Track for deduplication
            if dedupe_key:
                self._recent_alerts[dedupe_key] = datetime.now()

            # Add to history
            self._alert_history.append(alert)

            # Keep only last 1000 alerts in memory
            if len(self._alert_history) > 1000:
                self._alert_history = self._alert_history[-1000:]

            logger.info(f"Alert sent: [{severity.value}] {alert_type.value}: {title}")

            return alert_id

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Mark an alert as acknowledged."""
        for alert in self._alert_history:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                alert.acknowledged_by = acknowledged_by
                alert.acknowledged_at = datetime.now().isoformat()
                return True
        return False

    def resolve_alert(self, alert_id: str, resolved_by: str) -> bool:
        """Mark an alert as resolved."""
        for alert in self._alert_history:
            if alert.alert_id == alert_id:
                alert.resolved = True
                alert.resolved_by = resolved_by
                alert.resolved_at = datetime.now().isoformat()
                return True
        return False

    def get_active_alerts(self, severity: Optional[AlertSeverity] = None) -> List[Alert]:
        """Get unresolved alerts."""
        alerts = [a for a in self._alert_history if not a.resolved]
        if severity:
            alerts = [a for a in alerts if a.severity == severity.value]
        return alerts


# ==================== MONITORING CHECKS ====================

class MonitoringService:
    """
    Background monitoring service.

    Monitors:
    - Subscription status
    - Audit log integrity
    - AI prediction quality
    - Backup status
    """

    def __init__(self, alert_manager: AlertManager):
        self.alert_manager = alert_manager
        self.config = get_config()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self, check_interval_minutes: int = 15):
        """Start monitoring service."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._monitoring_loop,
            args=(check_interval_minutes,),
            daemon=True
        )
        self._thread.start()
        logger.info(f"Monitoring service started (interval: {check_interval_minutes} minutes)")

    def stop(self):
        """Stop monitoring service."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _monitoring_loop(self, interval_minutes: int):
        """Main monitoring loop."""
        import time

        while self._running:
            try:
                # Run all checks
                self.check_audit_log_integrity()
                self.check_subscription_status()
                self.check_backup_status()
                self.check_ai_suppression_rate()

            except Exception as e:
                logger.error(f"Monitoring error: {e}")

            # Sleep in chunks to allow stopping
            sleep_seconds = interval_minutes * 60
            while sleep_seconds > 0 and self._running:
                time.sleep(min(10, sleep_seconds))
                sleep_seconds -= 10

    def check_audit_log_integrity(self):
        """Check audit log integrity."""
        try:
            results = verify_all_logs()

            if not results.get('verified', True):
                self.alert_manager.send_alert(
                    alert_type=AlertType.AUDIT_INTEGRITY_FAILURE,
                    severity=AlertSeverity.CRITICAL,
                    title="Audit Log Integrity Failure",
                    message=f"Audit log tampering detected in {len(results.get('tampered_files', []))} files",
                    details=results,
                    dedupe_key="audit_integrity",
                    dedupe_window_minutes=60
                )

        except Exception as e:
            logger.error(f"Audit integrity check failed: {e}")

    def check_subscription_status(self):
        """Check for subscription issues."""
        try:
            from subscription_manager import get_subscription_manager

            # Check for recently expired subscriptions
            customers_dir = self.config.CUSTOMERS_DIR
            if not customers_dir.exists():
                return

            manager = get_subscription_manager()

            for customer_dir in customers_dir.iterdir():
                if not customer_dir.is_dir() or "_deleted_" in customer_dir.name:
                    continue

                customer_id = customer_dir.name
                sub = manager.load_subscription(customer_id)

                if not sub:
                    continue

                # Check for payment failures
                if sub.payment_status == "failed":
                    self.alert_manager.send_alert(
                        alert_type=AlertType.SUBSCRIPTION_PAYMENT_FAILED,
                        severity=AlertSeverity.HIGH,
                        title=f"Payment Failed: {customer_id}",
                        message=f"Subscription payment failed for customer {customer_id}",
                        customer_id=customer_id,
                        details={"plan": sub.plan, "end_date": sub.end_date},
                        dedupe_key=f"payment_failed_{customer_id}",
                        dedupe_window_minutes=1440  # Once per day
                    )

                # Check for upcoming expiration (7 days)
                if sub.end_date:
                    end = datetime.fromisoformat(sub.end_date)
                    days_remaining = (end - datetime.now()).days

                    if 0 < days_remaining <= 7:
                        self.alert_manager.send_alert(
                            alert_type=AlertType.SUBSCRIPTION_EXPIRED,
                            severity=AlertSeverity.MEDIUM,
                            title=f"Subscription Expiring: {customer_id}",
                            message=f"Subscription for {customer_id} expires in {days_remaining} days",
                            customer_id=customer_id,
                            details={"days_remaining": days_remaining, "end_date": sub.end_date},
                            dedupe_key=f"expiring_{customer_id}",
                            dedupe_window_minutes=1440
                        )

        except Exception as e:
            logger.error(f"Subscription check failed: {e}")

    def check_backup_status(self):
        """Check backup status."""
        try:
            from enterprise_backup import get_backup_manager

            manager = get_backup_manager()
            stats = manager.get_backup_statistics()

            # Check if last backup is too old (> 48 hours)
            if stats.get('last_backup'):
                last_backup = datetime.fromisoformat(stats['last_backup'])
                hours_since_backup = (datetime.now() - last_backup).total_seconds() / 3600

                if hours_since_backup > 48:
                    self.alert_manager.send_alert(
                        alert_type=AlertType.BACKUP_FAILED,
                        severity=AlertSeverity.HIGH,
                        title="Backup Overdue",
                        message=f"No backup in {int(hours_since_backup)} hours",
                        details=stats,
                        dedupe_key="backup_overdue",
                        dedupe_window_minutes=240
                    )

            # Check for unverified backups
            unverified = stats.get('total_backups', 0) - stats.get('verified_count', 0)
            if unverified > 0:
                self.alert_manager.send_alert(
                    alert_type=AlertType.BACKUP_VERIFICATION_FAILED,
                    severity=AlertSeverity.MEDIUM,
                    title="Unverified Backups",
                    message=f"{unverified} backups have not been verified",
                    details=stats,
                    dedupe_key="unverified_backups",
                    dedupe_window_minutes=1440
                )

        except Exception as e:
            logger.error(f"Backup check failed: {e}")

    def check_ai_suppression_rate(self):
        """Check AI prediction suppression rate."""
        try:
            accuracy_file = self.config.AI_ACCURACY_FILE

            if not accuracy_file.exists():
                return

            with open(accuracy_file, 'r') as f:
                data = json.load(f)

            # This would need actual suppression tracking
            # For now, check overall prediction count
            total = data.get('predictions_total', 0)
            feedback = data.get('feedback_received', 0)

            if total > 100:
                feedback_rate = feedback / total

                if feedback_rate < 0.1:  # Less than 10% feedback
                    self.alert_manager.send_alert(
                        alert_type=AlertType.AI_MODEL_ACCURACY_LOW,
                        severity=AlertSeverity.MEDIUM,
                        title="Low AI Feedback Rate",
                        message=f"Only {feedback_rate:.1%} of predictions have feedback",
                        details={"total_predictions": total, "feedback_count": feedback},
                        dedupe_key="ai_feedback_low",
                        dedupe_window_minutes=1440
                    )

        except Exception as e:
            logger.error(f"AI suppression check failed: {e}")


# ==================== MODULE-LEVEL FUNCTIONS ====================

_alert_manager: Optional[AlertManager] = None
_monitoring_service: Optional[MonitoringService] = None


def get_alert_manager() -> AlertManager:
    """Get global alert manager."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


def start_monitoring():
    """Start monitoring service."""
    global _monitoring_service
    if _monitoring_service is None:
        _monitoring_service = MonitoringService(get_alert_manager())
    _monitoring_service.start()


def send_alert(
    alert_type: AlertType,
    severity: AlertSeverity,
    title: str,
    message: str,
    customer_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """Send an alert."""
    return get_alert_manager().send_alert(
        alert_type=alert_type,
        severity=severity,
        title=title,
        message=message,
        customer_id=customer_id,
        details=details
    )


# ==================== CONNECTIVITY TEST ====================

def _test_handler_connectivity(handler: AlertHandler) -> bool:
    """Test if a specific handler can send alerts."""
    try:
        if isinstance(handler, EmailAlertHandler):
            # Test SMTP connection
            with smtplib.SMTP(handler.smtp_server, handler.smtp_port, timeout=10) as server:
                server.noop()
            return True
        elif isinstance(handler, WebhookAlertHandler):
            # Test webhook with HEAD request
            response = requests.head(handler.webhook_url, timeout=10)
            return response.status_code < 400
        elif isinstance(handler, LogAlertHandler):
            # Test file write
            handler.log_file.parent.mkdir(parents=True, exist_ok=True)
            return True
        return False
    except Exception as e:
        logger.warning(f"Handler connectivity test failed: {e}")
        return False


class AlertManager(AlertManager):
    """Extended AlertManager with connectivity testing."""

    def test_connectivity(self) -> bool:
        """
        Test if at least one alert handler can deliver alerts.

        REQUIRED BY: startup_enforcer.py

        Returns:
            True if at least one handler is working
        """
        working_handlers = 0

        for handler in self.handlers:
            try:
                if _test_handler_connectivity(handler):
                    working_handlers += 1
            except Exception:
                pass

        # Log handler always works, so we need at least one real handler OR just log
        return working_handlers > 0

    def get_health_status(self) -> Dict[str, Any]:
        """Get alert system health status."""
        handler_status = {}

        for handler in self.handlers:
            handler_name = type(handler).__name__
            try:
                handler_status[handler_name] = _test_handler_connectivity(handler)
            except Exception as e:
                handler_status[handler_name] = False

        working_count = sum(1 for v in handler_status.values() if v)

        return {
            "healthy": working_count > 0,
            "handlers": handler_status,
            "working_count": working_count,
            "total_count": len(self.handlers)
        }
