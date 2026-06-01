"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: User Acknowledgment Tracker

User Acknowledgment Tracker
============================
Tracks user acknowledgments of warnings, disclaimers, and predictions.
Creates a tamper-evident audit trail for liability protection.

CRITICAL: This system provides legal protection by documenting that
users were properly informed of prediction limitations.
"""

import sqlite3
import hashlib
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


# =============================================================================
# ACKNOWLEDGMENT TYPES
# =============================================================================

class AcknowledgmentType(Enum):
    """Types of acknowledgments."""
    LEGAL_DISCLAIMER = "legal_disclaimer"          # Legal terms acceptance
    PREDICTION_WARNING = "prediction_warning"       # Warning about a prediction
    CRITICAL_ALERT = "critical_alert"              # Critical safety alert
    COVERAGE_WARNING = "coverage_warning"          # Vehicle coverage limitation
    PROFESSIONAL_ADVICE = "professional_advice"    # Professional inspection advice
    EXPERIMENTAL_FEATURE = "experimental_feature"  # Experimental feature warning
    DATA_CONSENT = "data_consent"                  # Data usage consent


class AcknowledgmentAction(Enum):
    """User actions for acknowledgments."""
    ACCEPTED = "accepted"            # User accepted/acknowledged
    DISMISSED = "dismissed"          # User dismissed without reading (logged)
    DEFERRED = "deferred"            # User chose to review later
    PRINTED = "printed"              # User printed/saved the information
    SHARED = "shared"                # User shared with mechanic/professional


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class Acknowledgment:
    """Record of a user acknowledgment."""
    acknowledgment_id: str
    user_id: str
    acknowledgment_type: AcknowledgmentType
    action: AcknowledgmentAction
    related_entity_id: Optional[str]  # prediction_id, disclaimer_id, etc.
    related_entity_type: Optional[str]
    content_hash: str  # Hash of content that was acknowledged
    timestamp: str
    expiry: Optional[str]  # When this acknowledgment expires
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Audit fields
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_fingerprint: Optional[str] = None

    # Verification
    signature: str = ""  # Cryptographic signature for tamper detection


@dataclass
class AcknowledgmentRequirement:
    """Requirement for user acknowledgment."""
    requirement_id: str
    acknowledgment_type: AcknowledgmentType
    entity_id: str
    entity_type: str
    content: str
    content_hash: str
    required_action: AcknowledgmentAction
    created_at: str
    expires_at: Optional[str]
    is_blocking: bool  # Blocks further action until acknowledged
    reminder_interval: Optional[int] = None  # Minutes between reminders


@dataclass
class AcknowledgmentStatus:
    """Status of an acknowledgment requirement."""
    requirement: AcknowledgmentRequirement
    is_acknowledged: bool
    acknowledgment: Optional[Acknowledgment]
    is_expired: bool
    needs_renewal: bool
    time_until_expiry: Optional[timedelta]


# =============================================================================
# USER ACKNOWLEDGMENT TRACKER
# =============================================================================

class UserAcknowledgmentTracker:
    """
    Tracks all user acknowledgments for liability protection.

    This system creates a complete, tamper-evident audit trail of:
    - What information users were shown
    - When they acknowledged it
    - What action they took
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize the tracker."""
        self.db_path = db_path or Path("ai_data/acknowledgments.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_database()

        # Expiry times for different acknowledgment types
        self.expiry_times = {
            AcknowledgmentType.LEGAL_DISCLAIMER: timedelta(days=365),
            AcknowledgmentType.PREDICTION_WARNING: timedelta(days=30),
            AcknowledgmentType.CRITICAL_ALERT: timedelta(days=7),
            AcknowledgmentType.COVERAGE_WARNING: timedelta(days=90),
            AcknowledgmentType.PROFESSIONAL_ADVICE: timedelta(days=14),
            AcknowledgmentType.EXPERIMENTAL_FEATURE: timedelta(days=30),
            AcknowledgmentType.DATA_CONSENT: timedelta(days=365),
        }

        logger.info("User Acknowledgment Tracker initialized")

    def _init_database(self):
        """Initialize SQLite database."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Main acknowledgments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS acknowledgments (
                acknowledgment_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                acknowledgment_type TEXT NOT NULL,
                action TEXT NOT NULL,
                related_entity_id TEXT,
                related_entity_type TEXT,
                content_hash TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                expiry TEXT,
                metadata TEXT,
                ip_address TEXT,
                user_agent TEXT,
                device_fingerprint TEXT,
                signature TEXT NOT NULL
            )
        """)

        # Requirements table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS acknowledgment_requirements (
                requirement_id TEXT PRIMARY KEY,
                acknowledgment_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                content TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                required_action TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                is_blocking INTEGER NOT NULL DEFAULT 1,
                reminder_interval INTEGER
            )
        """)

        # Pending acknowledgments (for tracking what needs to be shown)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_acknowledgments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                requirement_id TEXT NOT NULL,
                first_shown TEXT NOT NULL,
                last_reminded TEXT,
                reminder_count INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                FOREIGN KEY (requirement_id) REFERENCES acknowledgment_requirements(requirement_id)
            )
        """)

        # Audit log for all changes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS acknowledgment_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                user_id TEXT,
                acknowledgment_id TEXT,
                details TEXT,
                previous_hash TEXT,
                current_hash TEXT
            )
        """)

        # Create indexes for performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ack_user
            ON acknowledgments(user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ack_type
            ON acknowledgments(acknowledgment_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pending_user
            ON pending_acknowledgments(user_id, status)
        """)

        conn.commit()
        conn.close()

    def create_requirement(
        self,
        acknowledgment_type: AcknowledgmentType,
        entity_id: str,
        entity_type: str,
        content: str,
        is_blocking: bool = True,
        expires_at: Optional[datetime] = None,
        required_action: AcknowledgmentAction = AcknowledgmentAction.ACCEPTED
    ) -> AcknowledgmentRequirement:
        """
        Create a new acknowledgment requirement.

        Args:
            acknowledgment_type: Type of acknowledgment required
            entity_id: ID of related entity (prediction, disclaimer, etc.)
            entity_type: Type of entity
            content: The content user must acknowledge
            is_blocking: Whether this blocks further action
            expires_at: When this requirement expires
            required_action: What action is required

        Returns:
            AcknowledgmentRequirement object
        """
        requirement_id = str(uuid.uuid4())
        content_hash = self._hash_content(content)
        now = datetime.now()

        if expires_at is None:
            expiry = self.expiry_times.get(acknowledgment_type, timedelta(days=30))
            expires_at = now + expiry

        requirement = AcknowledgmentRequirement(
            requirement_id=requirement_id,
            acknowledgment_type=acknowledgment_type,
            entity_id=entity_id,
            entity_type=entity_type,
            content=content,
            content_hash=content_hash,
            required_action=required_action,
            created_at=now.isoformat(),
            expires_at=expires_at.isoformat() if expires_at else None,
            is_blocking=is_blocking
        )

        self._save_requirement(requirement)

        logger.info(f"Created acknowledgment requirement {requirement_id} "
                   f"for {acknowledgment_type.value}")

        return requirement

    def record_acknowledgment(
        self,
        user_id: str,
        requirement_id: str,
        action: AcknowledgmentAction,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_fingerprint: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Acknowledgment:
        """
        Record a user acknowledgment.

        Args:
            user_id: User identifier
            requirement_id: ID of requirement being acknowledged
            action: What action the user took
            ip_address: IP address for audit
            user_agent: User agent for audit
            device_fingerprint: Device fingerprint for audit
            metadata: Additional metadata

        Returns:
            Acknowledgment record
        """
        requirement = self._get_requirement(requirement_id)
        if not requirement:
            raise ValueError(f"Requirement {requirement_id} not found")

        acknowledgment_id = str(uuid.uuid4())
        now = datetime.now()

        # Calculate expiry
        expiry_delta = self.expiry_times.get(
            requirement.acknowledgment_type,
            timedelta(days=30)
        )
        expiry = now + expiry_delta

        # Create signature for tamper detection
        signature = self._create_signature(
            acknowledgment_id, user_id, requirement.content_hash, now.isoformat()
        )

        acknowledgment = Acknowledgment(
            acknowledgment_id=acknowledgment_id,
            user_id=user_id,
            acknowledgment_type=requirement.acknowledgment_type,
            action=action,
            related_entity_id=requirement.entity_id,
            related_entity_type=requirement.entity_type,
            content_hash=requirement.content_hash,
            timestamp=now.isoformat(),
            expiry=expiry.isoformat(),
            metadata=metadata or {},
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint,
            signature=signature
        )

        self._save_acknowledgment(acknowledgment)
        self._update_pending_status(user_id, requirement_id, 'completed')
        self._log_audit(
            'acknowledgment_recorded',
            user_id,
            acknowledgment_id,
            f"Type: {requirement.acknowledgment_type.value}, Action: {action.value}"
        )

        logger.info(f"Recorded acknowledgment {acknowledgment_id} "
                   f"from user {user_id}: {action.value}")

        return acknowledgment

    def check_acknowledgment_status(
        self,
        user_id: str,
        requirement_id: str
    ) -> AcknowledgmentStatus:
        """
        Check if a user has acknowledged a requirement.

        Args:
            user_id: User identifier
            requirement_id: Requirement to check

        Returns:
            AcknowledgmentStatus
        """
        requirement = self._get_requirement(requirement_id)
        if not requirement:
            raise ValueError(f"Requirement {requirement_id} not found")

        acknowledgment = self._get_user_acknowledgment(user_id, requirement.content_hash)

        is_acknowledged = acknowledgment is not None
        is_expired = False
        needs_renewal = False
        time_until_expiry = None

        if acknowledgment:
            if acknowledgment.expiry:
                expiry_time = datetime.fromisoformat(acknowledgment.expiry)
                now = datetime.now()

                is_expired = now > expiry_time
                time_until_expiry = expiry_time - now if not is_expired else None

                # Need renewal if less than 7 days remaining
                if time_until_expiry and time_until_expiry < timedelta(days=7):
                    needs_renewal = True

        return AcknowledgmentStatus(
            requirement=requirement,
            is_acknowledged=is_acknowledged and not is_expired,
            acknowledgment=acknowledgment,
            is_expired=is_expired,
            needs_renewal=needs_renewal,
            time_until_expiry=time_until_expiry
        )

    def get_pending_acknowledgments(
        self,
        user_id: str,
        blocking_only: bool = False
    ) -> List[AcknowledgmentRequirement]:
        """
        Get all pending acknowledgments for a user.

        Args:
            user_id: User identifier
            blocking_only: Only return blocking requirements

        Returns:
            List of pending requirements
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        query = """
            SELECT ar.* FROM acknowledgment_requirements ar
            LEFT JOIN acknowledgments a ON ar.content_hash = a.content_hash
                AND a.user_id = ?
                AND (a.expiry IS NULL OR a.expiry > ?)
            WHERE a.acknowledgment_id IS NULL
        """
        params = [user_id, datetime.now().isoformat()]

        if blocking_only:
            query += " AND ar.is_blocking = 1"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        requirements = []
        for row in rows:
            requirements.append(AcknowledgmentRequirement(
                requirement_id=row[0],
                acknowledgment_type=AcknowledgmentType(row[1]),
                entity_id=row[2],
                entity_type=row[3],
                content=row[4],
                content_hash=row[5],
                required_action=AcknowledgmentAction(row[6]),
                created_at=row[7],
                expires_at=row[8],
                is_blocking=bool(row[9]),
                reminder_interval=row[10]
            ))

        return requirements

    def has_blocking_acknowledgments(self, user_id: str) -> bool:
        """Check if user has any blocking acknowledgments pending."""
        pending = self.get_pending_acknowledgments(user_id, blocking_only=True)
        return len(pending) > 0

    def verify_acknowledgment_integrity(
        self,
        acknowledgment_id: str
    ) -> Tuple[bool, str]:
        """
        Verify an acknowledgment hasn't been tampered with.

        Args:
            acknowledgment_id: ID of acknowledgment to verify

        Returns:
            Tuple of (is_valid, message)
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM acknowledgments WHERE acknowledgment_id = ?
        """, (acknowledgment_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return False, "Acknowledgment not found"

        stored_signature = row[13]  # signature column

        # Recreate signature
        expected_signature = self._create_signature(
            row[0],  # acknowledgment_id
            row[1],  # user_id
            row[6],  # content_hash
            row[7]   # timestamp
        )

        if stored_signature == expected_signature:
            return True, "Acknowledgment verified"
        else:
            logger.warning(f"Acknowledgment {acknowledgment_id} failed integrity check!")
            return False, "Signature mismatch - possible tampering detected"

    def get_acknowledgment_history(
        self,
        user_id: str,
        acknowledgment_type: Optional[AcknowledgmentType] = None,
        limit: int = 100
    ) -> List[Acknowledgment]:
        """
        Get acknowledgment history for a user.

        Args:
            user_id: User identifier
            acknowledgment_type: Optional filter by type
            limit: Maximum records to return

        Returns:
            List of acknowledgments
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        query = "SELECT * FROM acknowledgments WHERE user_id = ?"
        params = [user_id]

        if acknowledgment_type:
            query += " AND acknowledgment_type = ?"
            params.append(acknowledgment_type.value)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        acknowledgments = []
        for row in rows:
            acknowledgments.append(Acknowledgment(
                acknowledgment_id=row[0],
                user_id=row[1],
                acknowledgment_type=AcknowledgmentType(row[2]),
                action=AcknowledgmentAction(row[3]),
                related_entity_id=row[4],
                related_entity_type=row[5],
                content_hash=row[6],
                timestamp=row[7],
                expiry=row[8],
                metadata=json.loads(row[9]) if row[9] else {},
                ip_address=row[10],
                user_agent=row[11],
                device_fingerprint=row[12],
                signature=row[13]
            ))

        return acknowledgments

    def generate_compliance_report(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate a compliance report for a user.

        This report can be used for legal/liability purposes.
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=365)
        if end_date is None:
            end_date = datetime.now()

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Get all acknowledgments in period
        cursor.execute("""
            SELECT acknowledgment_type, action, COUNT(*), MIN(timestamp), MAX(timestamp)
            FROM acknowledgments
            WHERE user_id = ? AND timestamp BETWEEN ? AND ?
            GROUP BY acknowledgment_type, action
        """, (user_id, start_date.isoformat(), end_date.isoformat()))

        type_stats = {}
        for row in cursor.fetchall():
            ack_type = row[0]
            if ack_type not in type_stats:
                type_stats[ack_type] = {}
            type_stats[ack_type][row[1]] = {
                'count': row[2],
                'first': row[3],
                'last': row[4]
            }

        # Get pending acknowledgments
        pending = self.get_pending_acknowledgments(user_id)

        # Get any expired acknowledgments
        cursor.execute("""
            SELECT COUNT(*) FROM acknowledgments
            WHERE user_id = ? AND expiry < ?
        """, (user_id, datetime.now().isoformat()))

        expired_count = cursor.fetchone()[0]

        conn.close()

        report = {
            'report_id': f"compliance_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'user_id': user_id,
            'generated_at': datetime.now().isoformat(),
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'summary': {
                'total_acknowledgments': sum(
                    sum(a['count'] for a in actions.values())
                    for actions in type_stats.values()
                ),
                'pending_count': len(pending),
                'expired_count': expired_count,
                'acknowledgment_types': list(type_stats.keys())
            },
            'by_type': type_stats,
            'pending': [
                {
                    'type': p.acknowledgment_type.value,
                    'entity_id': p.entity_id,
                    'created_at': p.created_at,
                    'is_blocking': p.is_blocking
                }
                for p in pending
            ],
            'compliance_status': 'compliant' if len(pending) == 0 else 'pending_acknowledgments'
        }

        return report

    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================

    def _hash_content(self, content: str) -> str:
        """Create hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()

    def _create_signature(
        self,
        ack_id: str,
        user_id: str,
        content_hash: str,
        timestamp: str
    ) -> str:
        """Create cryptographic signature for tamper detection."""
        # In production, use proper signing key
        signing_key = "acknowledgment_signing_key_v1"
        data = f"{ack_id}:{user_id}:{content_hash}:{timestamp}:{signing_key}"
        return hashlib.sha256(data.encode()).hexdigest()

    def _save_requirement(self, requirement: AcknowledgmentRequirement):
        """Save requirement to database."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO acknowledgment_requirements
            (requirement_id, acknowledgment_type, entity_id, entity_type, content,
             content_hash, required_action, created_at, expires_at, is_blocking, reminder_interval)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            requirement.requirement_id,
            requirement.acknowledgment_type.value,
            requirement.entity_id,
            requirement.entity_type,
            requirement.content,
            requirement.content_hash,
            requirement.required_action.value,
            requirement.created_at,
            requirement.expires_at,
            1 if requirement.is_blocking else 0,
            requirement.reminder_interval
        ))

        conn.commit()
        conn.close()

    def _get_requirement(self, requirement_id: str) -> Optional[AcknowledgmentRequirement]:
        """Get requirement by ID."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM acknowledgment_requirements WHERE requirement_id = ?
        """, (requirement_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return AcknowledgmentRequirement(
            requirement_id=row[0],
            acknowledgment_type=AcknowledgmentType(row[1]),
            entity_id=row[2],
            entity_type=row[3],
            content=row[4],
            content_hash=row[5],
            required_action=AcknowledgmentAction(row[6]),
            created_at=row[7],
            expires_at=row[8],
            is_blocking=bool(row[9]),
            reminder_interval=row[10]
        )

    def _save_acknowledgment(self, acknowledgment: Acknowledgment):
        """Save acknowledgment to database."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO acknowledgments
            (acknowledgment_id, user_id, acknowledgment_type, action, related_entity_id,
             related_entity_type, content_hash, timestamp, expiry, metadata,
             ip_address, user_agent, device_fingerprint, signature)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            acknowledgment.acknowledgment_id,
            acknowledgment.user_id,
            acknowledgment.acknowledgment_type.value,
            acknowledgment.action.value,
            acknowledgment.related_entity_id,
            acknowledgment.related_entity_type,
            acknowledgment.content_hash,
            acknowledgment.timestamp,
            acknowledgment.expiry,
            json.dumps(acknowledgment.metadata),
            acknowledgment.ip_address,
            acknowledgment.user_agent,
            acknowledgment.device_fingerprint,
            acknowledgment.signature
        ))

        conn.commit()
        conn.close()

    def _get_user_acknowledgment(
        self,
        user_id: str,
        content_hash: str
    ) -> Optional[Acknowledgment]:
        """Get user's acknowledgment for specific content."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM acknowledgments
            WHERE user_id = ? AND content_hash = ?
            ORDER BY timestamp DESC LIMIT 1
        """, (user_id, content_hash))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return Acknowledgment(
            acknowledgment_id=row[0],
            user_id=row[1],
            acknowledgment_type=AcknowledgmentType(row[2]),
            action=AcknowledgmentAction(row[3]),
            related_entity_id=row[4],
            related_entity_type=row[5],
            content_hash=row[6],
            timestamp=row[7],
            expiry=row[8],
            metadata=json.loads(row[9]) if row[9] else {},
            ip_address=row[10],
            user_agent=row[11],
            device_fingerprint=row[12],
            signature=row[13]
        )

    def _update_pending_status(self, user_id: str, requirement_id: str, status: str):
        """Update pending acknowledgment status."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE pending_acknowledgments
            SET status = ?
            WHERE user_id = ? AND requirement_id = ?
        """, (status, user_id, requirement_id))

        conn.commit()
        conn.close()

    def _log_audit(
        self,
        action: str,
        user_id: Optional[str],
        acknowledgment_id: Optional[str],
        details: str
    ):
        """Log to audit trail."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO acknowledgment_audit_log
            (timestamp, action, user_id, acknowledgment_id, details)
            VALUES (?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            action,
            user_id,
            acknowledgment_id,
            details
        ))

        conn.commit()
        conn.close()


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_tracker_instance: Optional[UserAcknowledgmentTracker] = None


def get_acknowledgment_tracker() -> UserAcknowledgmentTracker:
    """Get or create singleton tracker instance."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = UserAcknowledgmentTracker()
    return _tracker_instance


def require_acknowledgment(
    user_id: str,
    acknowledgment_type: AcknowledgmentType,
    entity_id: str,
    entity_type: str,
    content: str,
    is_blocking: bool = True
) -> AcknowledgmentRequirement:
    """Convenience function to create an acknowledgment requirement."""
    tracker = get_acknowledgment_tracker()
    return tracker.create_requirement(
        acknowledgment_type=acknowledgment_type,
        entity_id=entity_id,
        entity_type=entity_type,
        content=content,
        is_blocking=is_blocking
    )


def record_user_acknowledgment(
    user_id: str,
    requirement_id: str,
    action: AcknowledgmentAction = AcknowledgmentAction.ACCEPTED
) -> Acknowledgment:
    """Convenience function to record an acknowledgment."""
    tracker = get_acknowledgment_tracker()
    return tracker.record_acknowledgment(user_id, requirement_id, action)
