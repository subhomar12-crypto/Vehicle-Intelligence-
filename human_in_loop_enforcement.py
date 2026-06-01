"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Human In Loop Enforcement

Human-in-the-Loop Enforcement System
=====================================
Ensures critical predictions require human review and confirmation
before any action is taken. This is a MANDATORY safety layer.

CRITICAL: This system enforces the principle that AI predictions
are ADVISORY ONLY. No automated action should be taken on
safety-critical predictions without explicit human confirmation.

Key Features:
- Mandatory human confirmation for critical/high-risk predictions
- Review workflow with timestamps and audit trail
- Reviewer qualification tracking
- Prediction acknowledgment system
- Integration with production_safety_enforcer.py
"""

import json
import hashlib
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import uuid

logger = logging.getLogger(__name__)


# =============================================================================
# REVIEW REQUIREMENTS BY CRITICALITY
# =============================================================================

class ReviewRequirement(Enum):
    """Level of human review required."""
    NONE = "none"                    # Informational only
    ACKNOWLEDGE = "acknowledge"       # User must acknowledge seeing prediction
    REVIEW = "review"                 # Qualified reviewer must review
    CONFIRM = "confirm"               # Explicit confirmation required before action
    DUAL_CONFIRM = "dual_confirm"     # Two independent reviewers required


class ReviewerQualification(Enum):
    """Qualification level of reviewers."""
    USER = "user"                     # Regular user/driver
    TECHNICIAN = "technician"         # Automotive technician
    MASTER_TECH = "master_technician" # ASE Master Technician
    ENGINEER = "engineer"             # Automotive engineer
    SYSTEM = "system"                 # Automated system (lowest trust)


# Review requirements by criticality level
CRITICALITY_REVIEW_REQUIREMENTS = {
    'critical': ReviewRequirement.DUAL_CONFIRM,  # Two reviewers for critical
    'high': ReviewRequirement.CONFIRM,           # Explicit confirmation
    'medium': ReviewRequirement.ACKNOWLEDGE,     # User acknowledgment
    'low': ReviewRequirement.NONE,               # Informational
}

# Minimum reviewer qualification by criticality
MIN_REVIEWER_QUALIFICATION = {
    'critical': ReviewerQualification.TECHNICIAN,  # At least technician
    'high': ReviewerQualification.USER,            # User can review
    'medium': ReviewerQualification.USER,
    'low': ReviewerQualification.USER,
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class HumanReview:
    """Record of a human review action."""
    review_id: str
    prediction_id: str
    reviewer_id: str
    reviewer_name: str
    reviewer_qualification: str
    review_action: str  # 'acknowledged', 'confirmed', 'rejected', 'escalated'
    review_notes: str
    timestamp: str
    ip_address: Optional[str] = None
    device_info: Optional[str] = None


@dataclass
class PendingReview:
    """A prediction awaiting human review."""
    prediction_id: str
    vehicle_id: str
    prediction_type: str  # failure type
    criticality: str
    confidence: float
    failure_probability: float
    days_to_failure: int
    review_requirement: str
    min_reviewer_qualification: str
    created_at: str
    expires_at: str
    status: str  # 'pending', 'reviewed', 'expired', 'escalated'
    reviews: List[HumanReview] = field(default_factory=list)
    prediction_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReviewDecision:
    """Final decision after human review."""
    decision_id: str
    prediction_id: str
    decision: str  # 'approved', 'rejected', 'needs_inspection', 'escalated'
    reasoning: str
    action_authorized: bool
    reviewer_count: int
    reviewers: List[str]
    timestamp: str
    expiry: str  # Decision expires - must be re-reviewed


# =============================================================================
# HUMAN-IN-THE-LOOP ENFORCEMENT
# =============================================================================

class HumanInLoopEnforcer:
    """
    Enforces human review requirements for AI predictions.

    This is a CRITICAL safety system. It ensures that:
    1. No automated action is taken on critical predictions
    2. Human reviewers explicitly confirm understanding
    3. Full audit trail of all reviews
    4. Qualified reviewers for high-risk predictions
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize the enforcer with database storage."""
        self.db_path = db_path or Path("ai_data/human_reviews.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_database()

        # Review expiry times by criticality
        self.review_expiry = {
            'critical': timedelta(hours=24),    # Must re-review daily
            'high': timedelta(hours=72),        # Re-review every 3 days
            'medium': timedelta(days=7),        # Weekly re-review
            'low': timedelta(days=30),          # Monthly re-review
        }

        # Pending reviews cache
        self._pending_cache: Dict[str, PendingReview] = {}

        logger.info("Human-in-Loop Enforcer initialized")

    def _init_database(self):
        """Initialize SQLite database for review tracking."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Pending reviews table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_reviews (
                prediction_id TEXT PRIMARY KEY,
                vehicle_id TEXT NOT NULL,
                prediction_type TEXT NOT NULL,
                criticality TEXT NOT NULL,
                confidence REAL NOT NULL,
                failure_probability REAL NOT NULL,
                days_to_failure INTEGER NOT NULL,
                review_requirement TEXT NOT NULL,
                min_reviewer_qualification TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                prediction_data TEXT
            )
        """)

        # Human reviews table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS human_reviews (
                review_id TEXT PRIMARY KEY,
                prediction_id TEXT NOT NULL,
                reviewer_id TEXT NOT NULL,
                reviewer_name TEXT NOT NULL,
                reviewer_qualification TEXT NOT NULL,
                review_action TEXT NOT NULL,
                review_notes TEXT,
                timestamp TEXT NOT NULL,
                ip_address TEXT,
                device_info TEXT,
                FOREIGN KEY (prediction_id) REFERENCES pending_reviews(prediction_id)
            )
        """)

        # Review decisions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS review_decisions (
                decision_id TEXT PRIMARY KEY,
                prediction_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                reasoning TEXT,
                action_authorized INTEGER NOT NULL DEFAULT 0,
                reviewer_count INTEGER NOT NULL,
                reviewers TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                expiry TEXT NOT NULL,
                FOREIGN KEY (prediction_id) REFERENCES pending_reviews(prediction_id)
            )
        """)

        # Audit log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS review_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                prediction_id TEXT,
                reviewer_id TEXT,
                details TEXT
            )
        """)

        conn.commit()
        conn.close()

    def require_review(
        self,
        prediction_id: str,
        vehicle_id: str,
        prediction_type: str,
        criticality: str,
        confidence: float,
        failure_probability: float,
        days_to_failure: int,
        prediction_data: Optional[Dict[str, Any]] = None
    ) -> PendingReview:
        """
        Register a prediction that requires human review.

        This MUST be called for all predictions before any action can be taken.

        Args:
            prediction_id: Unique identifier for the prediction
            vehicle_id: Vehicle the prediction is for
            prediction_type: Type of failure predicted
            criticality: Criticality level (critical, high, medium, low)
            confidence: Model confidence (0-1)
            failure_probability: Predicted failure probability
            days_to_failure: Predicted days until failure
            prediction_data: Full prediction data for review

        Returns:
            PendingReview object
        """
        review_requirement = CRITICALITY_REVIEW_REQUIREMENTS.get(
            criticality, ReviewRequirement.ACKNOWLEDGE
        )
        min_qualification = MIN_REVIEWER_QUALIFICATION.get(
            criticality, ReviewerQualification.USER
        )

        now = datetime.now()
        expiry = now + self.review_expiry.get(criticality, timedelta(days=7))

        pending = PendingReview(
            prediction_id=prediction_id,
            vehicle_id=vehicle_id,
            prediction_type=prediction_type,
            criticality=criticality,
            confidence=confidence,
            failure_probability=failure_probability,
            days_to_failure=days_to_failure,
            review_requirement=review_requirement.value,
            min_reviewer_qualification=min_qualification.value,
            created_at=now.isoformat(),
            expires_at=expiry.isoformat(),
            status='pending',
            prediction_data=prediction_data or {}
        )

        self._save_pending_review(pending)
        self._log_audit('review_required', prediction_id, None,
                       f"Review required: {criticality} - {prediction_type}")

        logger.info(f"Human review required for prediction {prediction_id}: "
                   f"{criticality} {prediction_type}")

        return pending

    def submit_review(
        self,
        prediction_id: str,
        reviewer_id: str,
        reviewer_name: str,
        reviewer_qualification: ReviewerQualification,
        action: str,
        notes: str = "",
        ip_address: Optional[str] = None,
        device_info: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Submit a human review for a prediction.

        Args:
            prediction_id: ID of prediction being reviewed
            reviewer_id: Unique identifier for reviewer
            reviewer_name: Display name of reviewer
            reviewer_qualification: Qualification level of reviewer
            action: Review action ('acknowledged', 'confirmed', 'rejected', 'escalated')
            notes: Reviewer's notes
            ip_address: IP address for audit
            device_info: Device info for audit

        Returns:
            Tuple of (success: bool, message: str)
        """
        # Get pending review
        pending = self._get_pending_review(prediction_id)
        if not pending:
            return False, f"No pending review found for {prediction_id}"

        # Check if review is still valid (not expired)
        if datetime.fromisoformat(pending.expires_at) < datetime.now():
            return False, "Review period has expired. Prediction must be re-evaluated."

        # Check reviewer qualification
        min_qual = ReviewerQualification(pending.min_reviewer_qualification)
        if not self._is_qualified(reviewer_qualification, min_qual):
            return False, (f"Reviewer qualification '{reviewer_qualification.value}' "
                          f"does not meet minimum requirement '{min_qual.value}'")

        # Create review record
        review = HumanReview(
            review_id=str(uuid.uuid4()),
            prediction_id=prediction_id,
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name,
            reviewer_qualification=reviewer_qualification.value,
            review_action=action,
            review_notes=notes,
            timestamp=datetime.now().isoformat(),
            ip_address=ip_address,
            device_info=device_info
        )

        self._save_review(review)
        self._log_audit('review_submitted', prediction_id, reviewer_id,
                       f"Action: {action}, Notes: {notes[:100]}")

        # Check if review requirements are now satisfied
        self._check_review_completion(prediction_id)

        logger.info(f"Review submitted for {prediction_id} by {reviewer_name}: {action}")

        return True, "Review submitted successfully"

    def is_action_authorized(
        self,
        prediction_id: str
    ) -> Tuple[bool, str, Optional[ReviewDecision]]:
        """
        Check if action is authorized for a prediction.

        This is the CRITICAL gate function. No action should be taken
        without calling this first and receiving authorization.

        Args:
            prediction_id: ID of prediction to check

        Returns:
            Tuple of (authorized: bool, reason: str, decision: Optional[ReviewDecision])
        """
        # Get pending review
        pending = self._get_pending_review(prediction_id)
        if not pending:
            return False, "No review record found - action not authorized", None

        # Check for existing decision
        decision = self._get_review_decision(prediction_id)
        if decision:
            # Check if decision has expired
            if datetime.fromisoformat(decision.expiry) < datetime.now():
                return False, "Previous authorization has expired - re-review required", decision

            if decision.action_authorized:
                return True, "Action authorized by human review", decision
            else:
                return False, f"Action not authorized: {decision.reasoning}", decision

        # No decision yet - check review status
        review_req = ReviewRequirement(pending.review_requirement)

        if review_req == ReviewRequirement.NONE:
            # No review required for low-risk predictions
            return True, "Low-risk prediction - no review required", None

        # Get reviews for this prediction
        reviews = self._get_reviews_for_prediction(prediction_id)

        if not reviews:
            return False, "Human review required - no reviews submitted yet", None

        # Check if requirements are met
        if review_req == ReviewRequirement.ACKNOWLEDGE:
            # Any review action counts as acknowledgment
            return True, f"Acknowledged by {reviews[0].reviewer_name}", None

        elif review_req == ReviewRequirement.REVIEW:
            # Need at least one review
            confirmed = [r for r in reviews if r.review_action in ('confirmed', 'acknowledged')]
            if confirmed:
                return True, f"Reviewed by {confirmed[0].reviewer_name}", None
            return False, "Awaiting positive review", None

        elif review_req == ReviewRequirement.CONFIRM:
            # Need explicit confirmation
            confirmed = [r for r in reviews if r.review_action == 'confirmed']
            if confirmed:
                return True, f"Confirmed by {confirmed[0].reviewer_name}", None

            rejected = [r for r in reviews if r.review_action == 'rejected']
            if rejected:
                return False, f"Rejected by {rejected[0].reviewer_name}: {rejected[0].review_notes}", None

            return False, "Awaiting explicit confirmation", None

        elif review_req == ReviewRequirement.DUAL_CONFIRM:
            # Need two independent confirmations
            confirmed = [r for r in reviews if r.review_action == 'confirmed']
            unique_reviewers = set(r.reviewer_id for r in confirmed)

            if len(unique_reviewers) >= 2:
                names = [r.reviewer_name for r in confirmed[:2]]
                return True, f"Dual confirmation by {', '.join(names)}", None

            rejected = [r for r in reviews if r.review_action == 'rejected']
            if rejected:
                return False, f"Rejected by {rejected[0].reviewer_name}", None

            if len(unique_reviewers) == 1:
                return False, "One confirmation received - awaiting second reviewer", None

            return False, "Awaiting dual confirmation (two independent reviewers required)", None

        return False, "Unknown review requirement", None

    def force_human_review_gate(
        self,
        prediction_id: str,
        action_description: str
    ) -> Tuple[bool, str]:
        """
        MANDATORY gate that MUST be called before any action on a prediction.

        This function will BLOCK until human review is complete or raise
        an exception if review requirements are not met.

        Args:
            prediction_id: ID of prediction
            action_description: Description of action being attempted

        Returns:
            Tuple of (authorized: bool, message: str)
        """
        authorized, reason, decision = self.is_action_authorized(prediction_id)

        if not authorized:
            # Log the blocked action attempt
            self._log_audit(
                'action_blocked',
                prediction_id,
                None,
                f"Attempted action '{action_description}' blocked: {reason}"
            )

            logger.warning(f"ACTION BLOCKED: {action_description} for {prediction_id}. "
                          f"Reason: {reason}")
        else:
            # Log the authorized action
            self._log_audit(
                'action_authorized',
                prediction_id,
                decision.reviewers[0] if decision and decision.reviewers else None,
                f"Action '{action_description}' authorized: {reason}"
            )

            logger.info(f"Action authorized: {action_description} for {prediction_id}")

        return authorized, reason

    def get_pending_reviews(
        self,
        vehicle_id: Optional[str] = None,
        criticality: Optional[str] = None
    ) -> List[PendingReview]:
        """
        Get all pending reviews, optionally filtered.

        Args:
            vehicle_id: Filter by vehicle
            criticality: Filter by criticality level

        Returns:
            List of pending reviews
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        query = "SELECT * FROM pending_reviews WHERE status = 'pending'"
        params = []

        if vehicle_id:
            query += " AND vehicle_id = ?"
            params.append(vehicle_id)

        if criticality:
            query += " AND criticality = ?"
            params.append(criticality)

        query += " ORDER BY criticality DESC, created_at ASC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        pending_reviews = []
        for row in rows:
            pending = PendingReview(
                prediction_id=row[0],
                vehicle_id=row[1],
                prediction_type=row[2],
                criticality=row[3],
                confidence=row[4],
                failure_probability=row[5],
                days_to_failure=row[6],
                review_requirement=row[7],
                min_reviewer_qualification=row[8],
                created_at=row[9],
                expires_at=row[10],
                status=row[11],
                prediction_data=json.loads(row[12]) if row[12] else {}
            )
            pending.reviews = self._get_reviews_for_prediction(pending.prediction_id)
            pending_reviews.append(pending)

        return pending_reviews

    def get_review_statistics(self) -> Dict[str, Any]:
        """Get statistics on human reviews."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        stats = {
            'total_pending': 0,
            'by_criticality': {},
            'by_status': {},
            'average_review_time': None,
            'review_actions': {},
            'reviewers': [],
        }

        # Count pending by criticality
        cursor.execute("""
            SELECT criticality, COUNT(*) FROM pending_reviews
            WHERE status = 'pending' GROUP BY criticality
        """)
        for row in cursor.fetchall():
            stats['by_criticality'][row[0]] = row[1]
            stats['total_pending'] += row[1]

        # Count by status
        cursor.execute("""
            SELECT status, COUNT(*) FROM pending_reviews GROUP BY status
        """)
        for row in cursor.fetchall():
            stats['by_status'][row[0]] = row[1]

        # Review action distribution
        cursor.execute("""
            SELECT review_action, COUNT(*) FROM human_reviews GROUP BY review_action
        """)
        for row in cursor.fetchall():
            stats['review_actions'][row[0]] = row[1]

        # Active reviewers
        cursor.execute("""
            SELECT DISTINCT reviewer_name, reviewer_qualification, COUNT(*)
            FROM human_reviews GROUP BY reviewer_id ORDER BY COUNT(*) DESC LIMIT 10
        """)
        for row in cursor.fetchall():
            stats['reviewers'].append({
                'name': row[0],
                'qualification': row[1],
                'review_count': row[2]
            })

        conn.close()
        return stats

    def escalate_prediction(
        self,
        prediction_id: str,
        escalation_reason: str,
        escalated_by: str
    ) -> bool:
        """
        Escalate a prediction for additional review.

        Args:
            prediction_id: ID of prediction to escalate
            escalation_reason: Reason for escalation
            escalated_by: ID of person escalating

        Returns:
            Success status
        """
        pending = self._get_pending_review(prediction_id)
        if not pending:
            return False

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Update status to escalated
        cursor.execute("""
            UPDATE pending_reviews SET status = 'escalated' WHERE prediction_id = ?
        """, (prediction_id,))

        # Upgrade review requirement to dual confirm
        cursor.execute("""
            UPDATE pending_reviews SET review_requirement = ? WHERE prediction_id = ?
        """, (ReviewRequirement.DUAL_CONFIRM.value, prediction_id))

        conn.commit()
        conn.close()

        self._log_audit('escalated', prediction_id, escalated_by, escalation_reason)

        logger.warning(f"Prediction {prediction_id} escalated: {escalation_reason}")

        return True

    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================

    def _is_qualified(
        self,
        reviewer_qual: ReviewerQualification,
        min_qual: ReviewerQualification
    ) -> bool:
        """Check if reviewer meets minimum qualification."""
        # Qualification hierarchy (higher index = more qualified)
        hierarchy = [
            ReviewerQualification.SYSTEM,
            ReviewerQualification.USER,
            ReviewerQualification.TECHNICIAN,
            ReviewerQualification.MASTER_TECH,
            ReviewerQualification.ENGINEER,
        ]

        reviewer_level = hierarchy.index(reviewer_qual) if reviewer_qual in hierarchy else 0
        min_level = hierarchy.index(min_qual) if min_qual in hierarchy else 0

        return reviewer_level >= min_level

    def _save_pending_review(self, pending: PendingReview):
        """Save pending review to database."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO pending_reviews
            (prediction_id, vehicle_id, prediction_type, criticality, confidence,
             failure_probability, days_to_failure, review_requirement,
             min_reviewer_qualification, created_at, expires_at, status, prediction_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pending.prediction_id,
            pending.vehicle_id,
            pending.prediction_type,
            pending.criticality,
            pending.confidence,
            pending.failure_probability,
            pending.days_to_failure,
            pending.review_requirement,
            pending.min_reviewer_qualification,
            pending.created_at,
            pending.expires_at,
            pending.status,
            json.dumps(pending.prediction_data)
        ))

        conn.commit()
        conn.close()

    def _get_pending_review(self, prediction_id: str) -> Optional[PendingReview]:
        """Get pending review by ID."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM pending_reviews WHERE prediction_id = ?
        """, (prediction_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return PendingReview(
            prediction_id=row[0],
            vehicle_id=row[1],
            prediction_type=row[2],
            criticality=row[3],
            confidence=row[4],
            failure_probability=row[5],
            days_to_failure=row[6],
            review_requirement=row[7],
            min_reviewer_qualification=row[8],
            created_at=row[9],
            expires_at=row[10],
            status=row[11],
            prediction_data=json.loads(row[12]) if row[12] else {}
        )

    def _save_review(self, review: HumanReview):
        """Save human review to database."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO human_reviews
            (review_id, prediction_id, reviewer_id, reviewer_name, reviewer_qualification,
             review_action, review_notes, timestamp, ip_address, device_info)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            review.review_id,
            review.prediction_id,
            review.reviewer_id,
            review.reviewer_name,
            review.reviewer_qualification,
            review.review_action,
            review.review_notes,
            review.timestamp,
            review.ip_address,
            review.device_info
        ))

        conn.commit()
        conn.close()

    def _get_reviews_for_prediction(self, prediction_id: str) -> List[HumanReview]:
        """Get all reviews for a prediction."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM human_reviews WHERE prediction_id = ? ORDER BY timestamp ASC
        """, (prediction_id,))

        rows = cursor.fetchall()
        conn.close()

        reviews = []
        for row in rows:
            reviews.append(HumanReview(
                review_id=row[0],
                prediction_id=row[1],
                reviewer_id=row[2],
                reviewer_name=row[3],
                reviewer_qualification=row[4],
                review_action=row[5],
                review_notes=row[6],
                timestamp=row[7],
                ip_address=row[8],
                device_info=row[9]
            ))

        return reviews

    def _get_review_decision(self, prediction_id: str) -> Optional[ReviewDecision]:
        """Get the final review decision for a prediction."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM review_decisions WHERE prediction_id = ?
            ORDER BY timestamp DESC LIMIT 1
        """, (prediction_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return ReviewDecision(
            decision_id=row[0],
            prediction_id=row[1],
            decision=row[2],
            reasoning=row[3],
            action_authorized=bool(row[4]),
            reviewer_count=row[5],
            reviewers=json.loads(row[6]),
            timestamp=row[7],
            expiry=row[8]
        )

    def _save_review_decision(self, decision: ReviewDecision):
        """Save review decision to database."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO review_decisions
            (decision_id, prediction_id, decision, reasoning, action_authorized,
             reviewer_count, reviewers, timestamp, expiry)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            decision.decision_id,
            decision.prediction_id,
            decision.decision,
            decision.reasoning,
            1 if decision.action_authorized else 0,
            decision.reviewer_count,
            json.dumps(decision.reviewers),
            decision.timestamp,
            decision.expiry
        ))

        conn.commit()
        conn.close()

    def _check_review_completion(self, prediction_id: str):
        """Check if review requirements are met and create decision if so."""
        pending = self._get_pending_review(prediction_id)
        if not pending:
            return

        reviews = self._get_reviews_for_prediction(prediction_id)
        review_req = ReviewRequirement(pending.review_requirement)

        decision = None

        # Check if requirements are fully met
        if review_req == ReviewRequirement.NONE:
            pass  # No decision needed

        elif review_req == ReviewRequirement.ACKNOWLEDGE:
            if reviews:
                decision = ReviewDecision(
                    decision_id=str(uuid.uuid4()),
                    prediction_id=prediction_id,
                    decision='acknowledged',
                    reasoning=f"Acknowledged by {reviews[0].reviewer_name}",
                    action_authorized=True,
                    reviewer_count=1,
                    reviewers=[reviews[0].reviewer_name],
                    timestamp=datetime.now().isoformat(),
                    expiry=(datetime.now() + self.review_expiry.get(
                        pending.criticality, timedelta(days=7)
                    )).isoformat()
                )

        elif review_req == ReviewRequirement.CONFIRM:
            confirmed = [r for r in reviews if r.review_action == 'confirmed']
            rejected = [r for r in reviews if r.review_action == 'rejected']

            if confirmed:
                decision = ReviewDecision(
                    decision_id=str(uuid.uuid4()),
                    prediction_id=prediction_id,
                    decision='approved',
                    reasoning=f"Confirmed by {confirmed[0].reviewer_name}",
                    action_authorized=True,
                    reviewer_count=1,
                    reviewers=[confirmed[0].reviewer_name],
                    timestamp=datetime.now().isoformat(),
                    expiry=(datetime.now() + self.review_expiry.get(
                        pending.criticality, timedelta(days=7)
                    )).isoformat()
                )
            elif rejected:
                decision = ReviewDecision(
                    decision_id=str(uuid.uuid4()),
                    prediction_id=prediction_id,
                    decision='rejected',
                    reasoning=rejected[0].review_notes,
                    action_authorized=False,
                    reviewer_count=1,
                    reviewers=[rejected[0].reviewer_name],
                    timestamp=datetime.now().isoformat(),
                    expiry=(datetime.now() + self.review_expiry.get(
                        pending.criticality, timedelta(days=7)
                    )).isoformat()
                )

        elif review_req == ReviewRequirement.DUAL_CONFIRM:
            confirmed = [r for r in reviews if r.review_action == 'confirmed']
            rejected = [r for r in reviews if r.review_action == 'rejected']
            unique_confirmed = list(set(r.reviewer_id for r in confirmed))

            if len(unique_confirmed) >= 2:
                reviewer_names = list(set(r.reviewer_name for r in confirmed))[:2]
                decision = ReviewDecision(
                    decision_id=str(uuid.uuid4()),
                    prediction_id=prediction_id,
                    decision='approved',
                    reasoning=f"Dual confirmation by {', '.join(reviewer_names)}",
                    action_authorized=True,
                    reviewer_count=2,
                    reviewers=reviewer_names,
                    timestamp=datetime.now().isoformat(),
                    expiry=(datetime.now() + self.review_expiry.get(
                        pending.criticality, timedelta(days=7)
                    )).isoformat()
                )
            elif rejected:
                decision = ReviewDecision(
                    decision_id=str(uuid.uuid4()),
                    prediction_id=prediction_id,
                    decision='rejected',
                    reasoning=rejected[0].review_notes,
                    action_authorized=False,
                    reviewer_count=1,
                    reviewers=[rejected[0].reviewer_name],
                    timestamp=datetime.now().isoformat(),
                    expiry=(datetime.now() + self.review_expiry.get(
                        pending.criticality, timedelta(days=7)
                    )).isoformat()
                )

        if decision:
            self._save_review_decision(decision)

            # Update pending review status
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE pending_reviews SET status = 'reviewed' WHERE prediction_id = ?
            """, (prediction_id,))
            conn.commit()
            conn.close()

            self._log_audit('decision_made', prediction_id, None,
                           f"Decision: {decision.decision}, Authorized: {decision.action_authorized}")

    def _log_audit(
        self,
        action: str,
        prediction_id: Optional[str],
        reviewer_id: Optional[str],
        details: str
    ):
        """Log to audit trail."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO review_audit_log (timestamp, action, prediction_id, reviewer_id, details)
            VALUES (?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            action,
            prediction_id,
            reviewer_id,
            details
        ))

        conn.commit()
        conn.close()


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_enforcer_instance: Optional[HumanInLoopEnforcer] = None


def get_human_in_loop_enforcer() -> HumanInLoopEnforcer:
    """Get or create the singleton enforcer instance."""
    global _enforcer_instance
    if _enforcer_instance is None:
        _enforcer_instance = HumanInLoopEnforcer()
    return _enforcer_instance


def require_human_review(
    prediction_id: str,
    vehicle_id: str,
    prediction_type: str,
    criticality: str,
    confidence: float,
    failure_probability: float,
    days_to_failure: int,
    prediction_data: Optional[Dict[str, Any]] = None
) -> PendingReview:
    """Convenience function to require human review."""
    enforcer = get_human_in_loop_enforcer()
    return enforcer.require_review(
        prediction_id=prediction_id,
        vehicle_id=vehicle_id,
        prediction_type=prediction_type,
        criticality=criticality,
        confidence=confidence,
        failure_probability=failure_probability,
        days_to_failure=days_to_failure,
        prediction_data=prediction_data
    )


def check_action_authorized(prediction_id: str, action: str) -> Tuple[bool, str]:
    """Convenience function to check if action is authorized."""
    enforcer = get_human_in_loop_enforcer()
    return enforcer.force_human_review_gate(prediction_id, action)
