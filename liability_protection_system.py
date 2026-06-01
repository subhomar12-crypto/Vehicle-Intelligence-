"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Liability Protection System

Liability Protection System
============================
Comprehensive legal and liability protection for the AI prediction system.
Creates defensible documentation and audit trails.

CRITICAL: This system protects both users and operators by ensuring:
1. Clear communication of limitations
2. Documentation of all interactions
3. Evidence of proper warnings
4. Compliance with best practices
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
# LIABILITY CATEGORIES
# =============================================================================

class LiabilityCategory(Enum):
    """Categories of liability concerns."""
    PREDICTION_ACCURACY = "prediction_accuracy"
    SAFETY_CRITICAL = "safety_critical"
    USER_RELIANCE = "user_reliance"
    DELAYED_ACTION = "delayed_action"
    MISINTERPRETATION = "misinterpretation"
    SYSTEM_FAILURE = "system_failure"
    DATA_QUALITY = "data_quality"


class ProtectionMeasure(Enum):
    """Types of protection measures."""
    DISCLAIMER = "disclaimer"
    WARNING = "warning"
    CONFIRMATION = "confirmation"
    DOCUMENTATION = "documentation"
    AUDIT_TRAIL = "audit_trail"
    USER_EDUCATION = "user_education"
    PROFESSIONAL_REFERRAL = "professional_referral"


class ComplianceStatus(Enum):
    """Compliance status levels."""
    COMPLIANT = "compliant"
    PARTIAL = "partial"
    NON_COMPLIANT = "non_compliant"
    UNKNOWN = "unknown"


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class LiabilityEvent:
    """Record of a liability-relevant event."""
    event_id: str
    timestamp: str
    category: LiabilityCategory
    description: str
    user_id: Optional[str]
    prediction_id: Optional[str]
    protections_applied: List[ProtectionMeasure]
    evidence_hash: str
    additional_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProtectionRecord:
    """Record of a protection measure applied."""
    record_id: str
    timestamp: str
    protection_type: ProtectionMeasure
    category: LiabilityCategory
    user_id: str
    entity_id: str
    entity_type: str
    content_shown: str
    content_hash: str
    user_response: Optional[str]
    evidence_preserved: bool


@dataclass
class ComplianceCheck:
    """Result of a compliance check."""
    check_id: str
    timestamp: str
    check_type: str
    status: ComplianceStatus
    details: str
    recommendations: List[str]
    evidence_refs: List[str]


@dataclass
class LiabilityReport:
    """Comprehensive liability report."""
    report_id: str
    generated_at: str
    period_start: str
    period_end: str
    overall_status: ComplianceStatus
    events_summary: Dict[str, int]
    protections_summary: Dict[str, int]
    compliance_checks: List[ComplianceCheck]
    risk_assessment: Dict[str, Any]
    recommendations: List[str]


# =============================================================================
# LIABILITY PROTECTION SYSTEM
# =============================================================================

class LiabilityProtectionSystem:
    """
    Comprehensive liability protection system.

    This system ensures legal defensibility by:
    1. Documenting all liability-relevant events
    2. Tracking protection measures applied
    3. Preserving evidence of proper disclosure
    4. Generating compliance reports
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize liability protection system."""
        self.db_path = db_path or Path("ai_data/liability.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_database()

        # Required protections by category
        self.required_protections = {
            LiabilityCategory.PREDICTION_ACCURACY: [
                ProtectionMeasure.DISCLAIMER,
                ProtectionMeasure.PROFESSIONAL_REFERRAL,
            ],
            LiabilityCategory.SAFETY_CRITICAL: [
                ProtectionMeasure.WARNING,
                ProtectionMeasure.CONFIRMATION,
                ProtectionMeasure.PROFESSIONAL_REFERRAL,
                ProtectionMeasure.DOCUMENTATION,
            ],
            LiabilityCategory.USER_RELIANCE: [
                ProtectionMeasure.DISCLAIMER,
                ProtectionMeasure.USER_EDUCATION,
            ],
            LiabilityCategory.DELAYED_ACTION: [
                ProtectionMeasure.WARNING,
                ProtectionMeasure.DOCUMENTATION,
            ],
            LiabilityCategory.MISINTERPRETATION: [
                ProtectionMeasure.USER_EDUCATION,
                ProtectionMeasure.DISCLAIMER,
            ],
            LiabilityCategory.SYSTEM_FAILURE: [
                ProtectionMeasure.AUDIT_TRAIL,
                ProtectionMeasure.DOCUMENTATION,
            ],
            LiabilityCategory.DATA_QUALITY: [
                ProtectionMeasure.WARNING,
                ProtectionMeasure.DISCLAIMER,
            ],
        }

        logger.info("Liability Protection System initialized")

    def _init_database(self):
        """Initialize SQLite database."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Liability events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS liability_events (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                user_id TEXT,
                prediction_id TEXT,
                protections_applied TEXT,
                evidence_hash TEXT NOT NULL,
                additional_data TEXT
            )
        """)

        # Protection records table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS protection_records (
                record_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                protection_type TEXT NOT NULL,
                category TEXT NOT NULL,
                user_id TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                content_shown TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                user_response TEXT,
                evidence_preserved INTEGER NOT NULL DEFAULT 1
            )
        """)

        # Compliance checks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS compliance_checks (
                check_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                check_type TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT NOT NULL,
                recommendations TEXT,
                evidence_refs TEXT
            )
        """)

        # Evidence storage table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence_storage (
                evidence_id TEXT PRIMARY KEY,
                event_id TEXT,
                record_id TEXT,
                evidence_type TEXT NOT NULL,
                content TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                preserved_until TEXT
            )
        """)

        # Audit log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS liability_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                entity_type TEXT,
                entity_id TEXT,
                details TEXT,
                chain_hash TEXT
            )
        """)

        conn.commit()
        conn.close()

    def record_liability_event(
        self,
        category: LiabilityCategory,
        description: str,
        user_id: Optional[str] = None,
        prediction_id: Optional[str] = None,
        protections_applied: Optional[List[ProtectionMeasure]] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> LiabilityEvent:
        """
        Record a liability-relevant event.

        Args:
            category: Type of liability concern
            description: Description of the event
            user_id: Associated user
            prediction_id: Associated prediction
            protections_applied: Protections that were applied
            additional_data: Any additional context

        Returns:
            LiabilityEvent record
        """
        event_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        protections = protections_applied or []

        # Create evidence hash
        evidence_data = f"{event_id}:{timestamp}:{category.value}:{description}:{user_id}:{prediction_id}"
        evidence_hash = hashlib.sha256(evidence_data.encode()).hexdigest()

        event = LiabilityEvent(
            event_id=event_id,
            timestamp=timestamp,
            category=category,
            description=description,
            user_id=user_id,
            prediction_id=prediction_id,
            protections_applied=protections,
            evidence_hash=evidence_hash,
            additional_data=additional_data or {}
        )

        self._save_event(event)
        self._log_audit('event_recorded', 'liability_event', event_id,
                       f"Category: {category.value}")

        logger.info(f"Recorded liability event {event_id}: {category.value}")

        return event

    def record_protection(
        self,
        protection_type: ProtectionMeasure,
        category: LiabilityCategory,
        user_id: str,
        entity_id: str,
        entity_type: str,
        content_shown: str,
        user_response: Optional[str] = None
    ) -> ProtectionRecord:
        """
        Record a protection measure that was applied.

        Args:
            protection_type: Type of protection measure
            category: Liability category being addressed
            user_id: User who received the protection
            entity_id: ID of related entity (prediction, disclaimer, etc.)
            entity_type: Type of entity
            content_shown: The actual content shown to user
            user_response: User's response if any

        Returns:
            ProtectionRecord
        """
        record_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        content_hash = hashlib.sha256(content_shown.encode()).hexdigest()

        record = ProtectionRecord(
            record_id=record_id,
            timestamp=timestamp,
            protection_type=protection_type,
            category=category,
            user_id=user_id,
            entity_id=entity_id,
            entity_type=entity_type,
            content_shown=content_shown,
            content_hash=content_hash,
            user_response=user_response,
            evidence_preserved=True
        )

        self._save_protection_record(record)

        # Store evidence
        self._store_evidence(
            event_id=None,
            record_id=record_id,
            evidence_type='protection_content',
            content=content_shown
        )

        self._log_audit('protection_recorded', 'protection_record', record_id,
                       f"Type: {protection_type.value}, Category: {category.value}")

        logger.info(f"Recorded protection {record_id}: {protection_type.value}")

        return record

    def check_compliance(
        self,
        user_id: str,
        prediction_id: str,
        category: LiabilityCategory
    ) -> ComplianceCheck:
        """
        Check if all required protections have been applied.

        Args:
            user_id: User to check
            prediction_id: Prediction to check
            category: Liability category to check

        Returns:
            ComplianceCheck result
        """
        check_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        required = self.required_protections.get(category, [])
        applied = self._get_applied_protections(user_id, prediction_id, category)

        missing = [p for p in required if p not in applied]

        if not missing:
            status = ComplianceStatus.COMPLIANT
            details = f"All {len(required)} required protections applied"
            recommendations = []
        elif len(missing) < len(required) / 2:
            status = ComplianceStatus.PARTIAL
            details = f"Missing {len(missing)} of {len(required)} required protections"
            recommendations = [f"Apply {m.value} protection" for m in missing]
        else:
            status = ComplianceStatus.NON_COMPLIANT
            details = f"Missing {len(missing)} of {len(required)} required protections"
            recommendations = [
                f"CRITICAL: Apply {m.value} protection immediately"
                for m in missing
            ]

        check = ComplianceCheck(
            check_id=check_id,
            timestamp=timestamp,
            check_type=f"protection_compliance_{category.value}",
            status=status,
            details=details,
            recommendations=recommendations,
            evidence_refs=[r.record_id for r in self._get_protection_records(user_id, prediction_id)]
        )

        self._save_compliance_check(check)

        logger.info(f"Compliance check {check_id}: {status.value}")

        return check

    def generate_liability_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> LiabilityReport:
        """
        Generate comprehensive liability report.

        Args:
            start_date: Start of reporting period
            end_date: End of reporting period

        Returns:
            LiabilityReport
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now()

        report_id = f"liability_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Events summary
        cursor.execute("""
            SELECT category, COUNT(*) FROM liability_events
            WHERE timestamp BETWEEN ? AND ?
            GROUP BY category
        """, (start_date.isoformat(), end_date.isoformat()))

        events_summary = {row[0]: row[1] for row in cursor.fetchall()}

        # Protections summary
        cursor.execute("""
            SELECT protection_type, COUNT(*) FROM protection_records
            WHERE timestamp BETWEEN ? AND ?
            GROUP BY protection_type
        """, (start_date.isoformat(), end_date.isoformat()))

        protections_summary = {row[0]: row[1] for row in cursor.fetchall()}

        # Recent compliance checks
        cursor.execute("""
            SELECT * FROM compliance_checks
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp DESC LIMIT 100
        """, (start_date.isoformat(), end_date.isoformat()))

        compliance_checks = []
        for row in cursor.fetchall():
            compliance_checks.append(ComplianceCheck(
                check_id=row[0],
                timestamp=row[1],
                check_type=row[2],
                status=ComplianceStatus(row[3]),
                details=row[4],
                recommendations=json.loads(row[5]) if row[5] else [],
                evidence_refs=json.loads(row[6]) if row[6] else []
            ))

        conn.close()

        # Calculate risk assessment
        risk_assessment = self._calculate_risk_assessment(
            events_summary, protections_summary, compliance_checks
        )

        # Determine overall status
        non_compliant_count = sum(
            1 for c in compliance_checks
            if c.status == ComplianceStatus.NON_COMPLIANT
        )
        partial_count = sum(
            1 for c in compliance_checks
            if c.status == ComplianceStatus.PARTIAL
        )

        if non_compliant_count > 0:
            overall_status = ComplianceStatus.NON_COMPLIANT
        elif partial_count > len(compliance_checks) / 4:
            overall_status = ComplianceStatus.PARTIAL
        else:
            overall_status = ComplianceStatus.COMPLIANT

        # Generate recommendations
        recommendations = self._generate_recommendations(
            events_summary, protections_summary, compliance_checks
        )

        report = LiabilityReport(
            report_id=report_id,
            generated_at=datetime.now().isoformat(),
            period_start=start_date.isoformat(),
            period_end=end_date.isoformat(),
            overall_status=overall_status,
            events_summary=events_summary,
            protections_summary=protections_summary,
            compliance_checks=compliance_checks,
            risk_assessment=risk_assessment,
            recommendations=recommendations
        )

        logger.info(f"Generated liability report {report_id}: {overall_status.value}")

        return report

    def verify_evidence_integrity(self) -> Dict[str, Any]:
        """
        Verify integrity of all stored evidence.

        Returns:
            Verification results
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT evidence_id, content, content_hash FROM evidence_storage")
        rows = cursor.fetchall()
        conn.close()

        results = {
            'total_evidence': len(rows),
            'verified': 0,
            'corrupted': 0,
            'corrupted_ids': []
        }

        for row in rows:
            evidence_id, content, stored_hash = row
            computed_hash = hashlib.sha256(content.encode()).hexdigest()

            if computed_hash == stored_hash:
                results['verified'] += 1
            else:
                results['corrupted'] += 1
                results['corrupted_ids'].append(evidence_id)
                logger.warning(f"Evidence integrity check failed for {evidence_id}")

        results['integrity_status'] = 'PASSED' if results['corrupted'] == 0 else 'FAILED'

        return results

    def get_protection_evidence(
        self,
        user_id: str,
        prediction_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all protection evidence for a specific prediction.

        Used to demonstrate proper disclosure was made.
        """
        records = self._get_protection_records(user_id, prediction_id)

        evidence = []
        for record in records:
            evidence.append({
                'record_id': record.record_id,
                'timestamp': record.timestamp,
                'protection_type': record.protection_type.value,
                'content_hash': record.content_hash,
                'user_response': record.user_response,
                'evidence_preserved': record.evidence_preserved
            })

        return evidence

    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================

    def _save_event(self, event: LiabilityEvent):
        """Save liability event to database."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO liability_events
            (event_id, timestamp, category, description, user_id, prediction_id,
             protections_applied, evidence_hash, additional_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.event_id,
            event.timestamp,
            event.category.value,
            event.description,
            event.user_id,
            event.prediction_id,
            json.dumps([p.value for p in event.protections_applied]),
            event.evidence_hash,
            json.dumps(event.additional_data)
        ))

        conn.commit()
        conn.close()

    def _save_protection_record(self, record: ProtectionRecord):
        """Save protection record to database."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO protection_records
            (record_id, timestamp, protection_type, category, user_id, entity_id,
             entity_type, content_shown, content_hash, user_response, evidence_preserved)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.record_id,
            record.timestamp,
            record.protection_type.value,
            record.category.value,
            record.user_id,
            record.entity_id,
            record.entity_type,
            record.content_shown,
            record.content_hash,
            record.user_response,
            1 if record.evidence_preserved else 0
        ))

        conn.commit()
        conn.close()

    def _save_compliance_check(self, check: ComplianceCheck):
        """Save compliance check to database."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO compliance_checks
            (check_id, timestamp, check_type, status, details, recommendations, evidence_refs)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            check.check_id,
            check.timestamp,
            check.check_type,
            check.status.value,
            check.details,
            json.dumps(check.recommendations),
            json.dumps(check.evidence_refs)
        ))

        conn.commit()
        conn.close()

    def _store_evidence(
        self,
        event_id: Optional[str],
        record_id: Optional[str],
        evidence_type: str,
        content: str
    ):
        """Store evidence for future retrieval."""
        evidence_id = str(uuid.uuid4())
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO evidence_storage
            (evidence_id, event_id, record_id, evidence_type, content, content_hash,
             created_at, preserved_until)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            evidence_id,
            event_id,
            record_id,
            evidence_type,
            content,
            content_hash,
            datetime.now().isoformat(),
            (datetime.now() + timedelta(days=365 * 7)).isoformat()  # 7 year retention
        ))

        conn.commit()
        conn.close()

    def _get_applied_protections(
        self,
        user_id: str,
        prediction_id: str,
        category: LiabilityCategory
    ) -> List[ProtectionMeasure]:
        """Get protections applied for a specific prediction."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT protection_type FROM protection_records
            WHERE user_id = ? AND entity_id = ? AND category = ?
        """, (user_id, prediction_id, category.value))

        rows = cursor.fetchall()
        conn.close()

        return [ProtectionMeasure(row[0]) for row in rows]

    def _get_protection_records(
        self,
        user_id: str,
        prediction_id: str
    ) -> List[ProtectionRecord]:
        """Get all protection records for a prediction."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM protection_records
            WHERE user_id = ? AND entity_id = ?
            ORDER BY timestamp ASC
        """, (user_id, prediction_id))

        rows = cursor.fetchall()
        conn.close()

        records = []
        for row in rows:
            records.append(ProtectionRecord(
                record_id=row[0],
                timestamp=row[1],
                protection_type=ProtectionMeasure(row[2]),
                category=LiabilityCategory(row[3]),
                user_id=row[4],
                entity_id=row[5],
                entity_type=row[6],
                content_shown=row[7],
                content_hash=row[8],
                user_response=row[9],
                evidence_preserved=bool(row[10])
            ))

        return records

    def _calculate_risk_assessment(
        self,
        events: Dict[str, int],
        protections: Dict[str, int],
        checks: List[ComplianceCheck]
    ) -> Dict[str, Any]:
        """Calculate risk assessment from data."""
        # Count high-risk events
        high_risk_categories = [
            LiabilityCategory.SAFETY_CRITICAL.value,
            LiabilityCategory.USER_RELIANCE.value,
            LiabilityCategory.DELAYED_ACTION.value
        ]
        high_risk_events = sum(events.get(c, 0) for c in high_risk_categories)

        # Calculate protection coverage
        total_protections = sum(protections.values())
        total_events = sum(events.values())
        coverage = total_protections / total_events if total_events > 0 else 1.0

        # Compliance rate
        compliant_checks = sum(1 for c in checks if c.status == ComplianceStatus.COMPLIANT)
        compliance_rate = compliant_checks / len(checks) if checks else 1.0

        # Risk score (lower is better)
        risk_score = (
            (high_risk_events * 0.3) +
            ((1 - coverage) * 30) +
            ((1 - compliance_rate) * 40)
        )

        if risk_score < 10:
            risk_level = "LOW"
        elif risk_score < 30:
            risk_level = "MODERATE"
        elif risk_score < 50:
            risk_level = "HIGH"
        else:
            risk_level = "CRITICAL"

        return {
            'risk_score': round(risk_score, 2),
            'risk_level': risk_level,
            'high_risk_events': high_risk_events,
            'protection_coverage': round(coverage, 2),
            'compliance_rate': round(compliance_rate, 2)
        }

    def _generate_recommendations(
        self,
        events: Dict[str, int],
        protections: Dict[str, int],
        checks: List[ComplianceCheck]
    ) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []

        # Check for missing protections
        total_protections = sum(protections.values())
        total_events = sum(events.values())

        if total_events > 0 and total_protections / total_events < 0.8:
            recommendations.append(
                "CRITICAL: Protection coverage is below 80%. "
                "Ensure all predictions have appropriate disclaimers and warnings."
            )

        # Check compliance rate
        non_compliant = [c for c in checks if c.status == ComplianceStatus.NON_COMPLIANT]
        if non_compliant:
            recommendations.append(
                f"Address {len(non_compliant)} non-compliant items immediately."
            )

        # Category-specific recommendations
        if events.get(LiabilityCategory.SAFETY_CRITICAL.value, 0) > 0:
            recommendations.append(
                "Ensure all safety-critical predictions require user confirmation "
                "and include professional referral recommendations."
            )

        if events.get(LiabilityCategory.USER_RELIANCE.value, 0) > 10:
            recommendations.append(
                "High user reliance detected. Consider additional user education "
                "about prediction limitations."
            )

        # Always include best practice reminders
        recommendations.append(
            "Regularly review and update disclaimers to reflect current capabilities."
        )
        recommendations.append(
            "Maintain evidence storage for at least 7 years for liability protection."
        )

        return recommendations

    def _log_audit(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        details: str
    ):
        """Log to audit trail with chain hash."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Get previous hash for chain
        cursor.execute("""
            SELECT chain_hash FROM liability_audit_log
            ORDER BY id DESC LIMIT 1
        """)
        row = cursor.fetchone()
        previous_hash = row[0] if row else "genesis"

        # Create chain hash
        chain_data = f"{previous_hash}:{action}:{entity_type}:{entity_id}:{datetime.now().isoformat()}"
        chain_hash = hashlib.sha256(chain_data.encode()).hexdigest()

        cursor.execute("""
            INSERT INTO liability_audit_log
            (timestamp, action, entity_type, entity_id, details, previous_hash, chain_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            action,
            entity_type,
            entity_id,
            details,
            previous_hash,
            chain_hash
        ))

        conn.commit()
        conn.close()


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_system_instance: Optional[LiabilityProtectionSystem] = None


def get_liability_system() -> LiabilityProtectionSystem:
    """Get or create singleton system instance."""
    global _system_instance
    if _system_instance is None:
        _system_instance = LiabilityProtectionSystem()
    return _system_instance


def record_prediction_liability(
    prediction_id: str,
    user_id: str,
    category: LiabilityCategory,
    description: str,
    protections: List[ProtectionMeasure]
) -> LiabilityEvent:
    """Convenience function to record prediction liability event."""
    system = get_liability_system()
    return system.record_liability_event(
        category=category,
        description=description,
        user_id=user_id,
        prediction_id=prediction_id,
        protections_applied=protections
    )
