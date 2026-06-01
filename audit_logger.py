"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Audit Logging System

Predict OBD - Audit Logging System
Comprehensive, tamper-resistant logging for security and compliance.

Features:
- Subscription lifecycle events
- Access control events
- Data modification events
- Prediction generation events
- Customer data access events
- Tamper-resistant logs with checksums
"""

import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
from dataclasses import dataclass, asdict

from config import get_config

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Audit event types"""
    # Subscription events
    SUBSCRIPTION_CREATED = "subscription_created"
    SUBSCRIPTION_ACTIVATED = "subscription_activated"
    SUBSCRIPTION_RENEWED = "subscription_renewed"
    SUBSCRIPTION_EXPIRED = "subscription_expired"
    SUBSCRIPTION_CANCELLED = "subscription_cancelled"
    RENEWAL_FAILED = "renewal_failed"

    # Access control events
    API_ACCESS = "api_access"
    ACCESS_DENIED = "access_denied"
    AUTHENTICATION_FAILED = "authentication_failed"
    LICENSE_VALIDATED = "license_validated"

    # Data events
    CUSTOMER_CREATED = "customer_created"
    CUSTOMER_DELETED = "customer_deleted"
    VEHICLE_ADDED = "vehicle_added"
    VEHICLE_REMOVED = "vehicle_removed"
    DATA_EXPORTED = "data_export"
    DATA_DELETED = "data_deleted"

    # AI/Prediction events
    PREDICTION_GENERATED = "prediction_generated"
    PREDICTION_FEEDBACK = "prediction_feedback"
    MODEL_DEPLOYED = "model_deployed"
    MODEL_ROLLBACK = "model_rollback"

    # Report events
    REPORT_GENERATED = "report_generated"
    REPORT_DOWNLOADED = "report_downloaded"

    # Consent/Legal events
    TERMS_ACCEPTED = "terms_accepted"
    CONSENT_GIVEN = "consent_given"
    CONSENT_REVOKED = "consent_revoked"

    # System events
    BACKUP_CREATED = "backup_created"
    BACKUP_RESTORED = "backup_restored"
    SYSTEM_ERROR = "system_error"


@dataclass
class AuditEvent:
    """Audit event data model"""
    event_id: str
    event_type: str
    timestamp: str
    customer_id: Optional[str]
    user_id: Optional[str]
    ip_address: Optional[str]
    details: Dict[str, Any]
    checksum: str  # Tamper detection

    @staticmethod
    def calculate_checksum(event_data: Dict[str, Any]) -> str:
        """Calculate checksum for tamper detection"""
        # Create deterministic string from event data
        data_str = json.dumps(event_data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()


class AuditLogger:
    """
    Tamper-resistant audit logger.

    Logs are:
    - Append-only (never modified)
    - Checksummed for tamper detection
    - Retained for compliance periods
    - Organized by date for efficiency
    """

    def __init__(self):
        self.config = get_config()
        self._event_counter = 0

    def log_event(
        self,
        event_type: AuditEventType,
        customer_id: Optional[str] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log an audit event.

        Args:
            event_type: Type of event
            customer_id: Customer identifier
            user_id: User who triggered event
            ip_address: Source IP address
            details: Additional event details

        Returns:
            Event ID
        """
        try:
            # Generate event ID
            event_id = self._generate_event_id()

            # Create event data
            event_data = {
                "event_id": event_id,
                "event_type": event_type.value,
                "timestamp": datetime.now().isoformat(),
                "customer_id": customer_id,
                "user_id": user_id,
                "ip_address": ip_address,
                "details": details or {}
            }

            # Calculate checksum
            checksum = AuditEvent.calculate_checksum(event_data)
            event_data["checksum"] = checksum

            # Create event object
            event = AuditEvent(**event_data)

            # Write to log file
            self._write_event(event)

            # Also log to standard logger for real-time monitoring
            logger.info(f"[AUDIT] {event_type.value} | Customer: {customer_id} | EventID: {event_id}")

            return event_id

        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
            # Audit logging failure is critical - raise exception
            raise

    def verify_log_integrity(self, log_file: Path) -> Tuple[bool, List[str]]:
        """
        Verify integrity of audit log file.

        Returns:
            (is_valid, list_of_tampered_events)
        """
        tampered_events = []

        try:
            if not log_file.exists():
                return True, []

            with open(log_file, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        event_data = json.loads(line)
                        stored_checksum = event_data.get("checksum")

                        # Recalculate checksum
                        event_data_without_checksum = {k: v for k, v in event_data.items() if k != "checksum"}
                        calculated_checksum = AuditEvent.calculate_checksum(event_data_without_checksum)

                        if stored_checksum != calculated_checksum:
                            tampered_events.append(f"Line {line_num}: Event {event_data.get('event_id')}")

                    except json.JSONDecodeError:
                        tampered_events.append(f"Line {line_num}: Corrupted JSON")

            is_valid = len(tampered_events) == 0
            return is_valid, tampered_events

        except Exception as e:
            logger.error(f"Error verifying log integrity: {e}")
            return False, [f"Verification error: {str(e)}"]

    def query_events(
        self,
        customer_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """
        Query audit events with filters.

        Args:
            customer_id: Filter by customer
            event_type: Filter by event type
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum events to return

        Returns:
            List of matching events
        """
        events = []

        try:
            # Determine which log files to search
            log_files = self._get_log_files_in_range(start_date, end_date)

            for log_file in log_files:
                if not log_file.exists():
                    continue

                with open(log_file, 'r') as f:
                    for line in f:
                        try:
                            event_data = json.loads(line)
                            event = AuditEvent(**event_data)

                            # Apply filters
                            if customer_id and event.customer_id != customer_id:
                                continue

                            if event_type and event.event_type != event_type.value:
                                continue

                            if start_date:
                                event_time = datetime.fromisoformat(event.timestamp)
                                if event_time < start_date:
                                    continue

                            if end_date:
                                event_time = datetime.fromisoformat(event.timestamp)
                                if event_time > end_date:
                                    continue

                            events.append(event)

                            # Check limit
                            if len(events) >= limit:
                                return events

                        except (json.JSONDecodeError, TypeError):
                            continue

            return events

        except Exception as e:
            logger.error(f"Error querying audit events: {e}")
            return []

    def get_customer_audit_trail(
        self,
        customer_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get complete audit trail for a customer"""
        events = self.query_events(customer_id=customer_id, limit=limit)
        return [asdict(event) for event in events]

    def export_audit_log(
        self,
        customer_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        output_file: Optional[Path] = None
    ) -> Path:
        """
        Export audit log to file for compliance.

        Args:
            customer_id: Export specific customer's events
            start_date: Start date filter
            end_date: End date filter
            output_file: Optional output file path

        Returns:
            Path to exported file
        """
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"audit_export_{customer_id or 'all'}_{timestamp}.json"
            output_file = self.config.LOGS_AUDIT_DIR / "exports" / filename

        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Query events
        events = self.query_events(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            limit=10000  # High limit for exports
        )

        # Export to file
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "customer_id": customer_id,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "event_count": len(events),
            "events": [asdict(event) for event in events]
        }

        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Audit log exported: {output_file} ({len(events)} events)")

        return output_file

    def _write_event(self, event: AuditEvent):
        """Write event to log file (append-only)"""
        # Organize logs by date for efficiency
        log_file = self._get_log_file_for_date(datetime.now())
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Append event as JSON line
        with open(log_file, 'a') as f:
            f.write(json.dumps(asdict(event)) + '\n')

    def _get_log_file_for_date(self, date: datetime) -> Path:
        """Get log file path for a specific date"""
        date_str = date.strftime("%Y-%m-%d")
        return self.config.LOGS_AUDIT_DIR / f"{date_str}.log"

    def _get_log_files_in_range(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> List[Path]:
        """Get all log files in date range"""
        audit_dir = self.config.LOGS_AUDIT_DIR

        if not audit_dir.exists():
            return []

        log_files = sorted(audit_dir.glob("*.log"))

        if not start_date and not end_date:
            return log_files

        # Filter by date range
        filtered_files = []
        for log_file in log_files:
            try:
                # Extract date from filename (YYYY-MM-DD.log)
                date_str = log_file.stem
                file_date = datetime.strptime(date_str, "%Y-%m-%d")

                if start_date and file_date < start_date.replace(hour=0, minute=0, second=0):
                    continue

                if end_date and file_date > end_date.replace(hour=23, minute=59, second=59):
                    continue

                filtered_files.append(log_file)

            except ValueError:
                # Skip files that don't match date format
                continue

        return filtered_files

    def _generate_event_id(self) -> str:
        """Generate unique event ID"""
        self._event_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"evt_{timestamp}_{self._event_counter:06d}"


# ==================== MODULE-LEVEL FUNCTIONS ====================

_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def log_audit_event(
    event_type: AuditEventType,
    customer_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> str:
    """Convenience function for logging audit events"""
    audit_logger = get_audit_logger()
    return audit_logger.log_event(event_type, customer_id=customer_id, details=details)


# ==================== UTILITY FUNCTIONS ====================

def verify_all_logs() -> Dict[str, Any]:
    """Verify integrity of all audit logs"""
    audit_logger = get_audit_logger()
    audit_dir = audit_logger.config.LOGS_AUDIT_DIR

    if not audit_dir.exists():
        return {"status": "no_logs", "verified": True, "tampered_files": []}

    results = {
        "status": "verified",
        "total_files": 0,
        "verified_files": 0,
        "tampered_files": [],
        "tampered_events": []
    }

    for log_file in sorted(audit_dir.glob("*.log")):
        results["total_files"] += 1

        is_valid, tampered_events = audit_logger.verify_log_integrity(log_file)

        if is_valid:
            results["verified_files"] += 1
        else:
            results["tampered_files"].append(str(log_file))
            results["tampered_events"].extend([f"{log_file.name}: {event}" for event in tampered_events])

    results["verified"] = len(results["tampered_files"]) == 0

    return results
