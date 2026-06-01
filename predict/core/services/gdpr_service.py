"""
GDPR compliance service for data retention and privacy.

Handles:
- Data retention policy enforcement
- User data export (right to data portability)
- User data deletion (right to erasure)
- Consent management
- Privacy audit logging
"""

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

import aiofiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, text

from predict.core.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class DataRetentionPolicy:
    """Data retention policy configuration."""
    # User data
    inactive_user_days: int = 365  # Delete inactive users after 1 year
    deleted_user_grace_days: int = 30  # Grace period before hard delete
    
    # Vehicle data
    telemetry_days: int = 730  # 2 years of telemetry
    diagnostic_logs_days: int = 365  # 1 year of diagnostic logs
    prediction_history_days: int = 365  # 1 year of predictions
    
    # Audit data
    audit_log_days: int = 2555  # 7 years (regulatory)
    session_logs_days: int = 90  # 90 days of session logs
    
    # Marketing
    marketing_data_days: int = 730  # 2 years for marketing data
    
    def to_dict(self) -> Dict[str, int]:
        return {
            "inactive_user_days": self.inactive_user_days,
            "deleted_user_grace_days": self.deleted_user_grace_days,
            "telemetry_days": self.telemetry_days,
            "diagnostic_logs_days": self.diagnostic_logs_days,
            "prediction_history_days": self.prediction_history_days,
            "audit_log_days": self.audit_log_days,
            "session_logs_days": self.session_logs_days,
            "marketing_data_days": self.marketing_data_days,
        }


class GDPRService:
    """GDPR compliance and data retention service."""
    
    def __init__(self, policy: Optional[DataRetentionPolicy] = None):
        self.config = get_config()
        self.policy = policy or DataRetentionPolicy()
        self.data_export_dir = self.config.DATA_DIR / "exports"
        self.data_export_dir.mkdir(parents=True, exist_ok=True)
    
    async def export_user_data(
        self,
        user_id: int,
        session: AsyncSession,
    ) -> Path:
        """
        Export all user data for data portability request.
        
        Args:
            user_id: User to export data for
            session: Database session
        
        Returns:
            Path to exported JSON file
        """
        export_data = {
            "export_metadata": {
                "user_id": user_id,
                "exported_at": time.time(),
                "export_version": "1.0",
            },
            "user_profile": await self._export_user_profile(user_id, session),
            "vehicles": await self._export_vehicles(user_id, session),
            "dtc_history": await self._export_dtc_history(user_id, session),
            "telemetry": await self._export_telemetry(user_id, session),
            "predictions": await self._export_predictions(user_id, session),
            "trips": await self._export_trips(user_id, session),
            "subscriptions": await self._export_subscriptions(user_id, session),
            "audit_logs": await self._export_audit_logs(user_id, session),
        }
        
        # Write to file
        filename = f"data_export_user_{user_id}_{int(time.time())}.json"
        export_path = self.data_export_dir / filename
        
        async with aiofiles.open(export_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(export_data, indent=2, default=str))
        
        # Log the export
        await self._log_audit_event(
            user_id=user_id,
            event_type="data_export",
            details={"export_file": filename},
            session=session,
        )
        
        logger.info(f"User data exported: {export_path}")
        return export_path
    
    async def delete_user_data(
        self,
        user_id: int,
        session: AsyncSession,
        hard_delete: bool = False,
    ) -> Dict[str, Any]:
        """
        Delete user data (right to erasure).
        
        Args:
            user_id: User to delete
            session: Database session
            hard_delete: If True, permanently delete; otherwise soft delete
        
        Returns:
            Deletion summary
        """
        deleted_counts = {}
        
        try:
            if hard_delete:
                # Hard delete - remove all data
                # Delete in order to respect foreign keys
                deleted_counts["telemetry"] = await self._delete_user_telemetry(user_id, session)
                deleted_counts["dtc_records"] = await self._delete_user_dtc(user_id, session)
                deleted_counts["predictions"] = await self._delete_user_predictions(user_id, session)
                deleted_counts["trips"] = await self._delete_user_trips(user_id, session)
                deleted_counts["vehicles"] = await self._delete_user_vehicles(user_id, session)
                deleted_counts["subscriptions"] = await self._delete_user_subscriptions(user_id, session)
                deleted_counts["user"] = await self._delete_user_account(user_id, session)
            else:
                # Soft delete - anonymize
                deleted_counts["anonymized"] = await self._anonymize_user_data(user_id, session)
            
            await session.commit()
            
            # Log deletion
            await self._log_audit_event(
                user_id=user_id,
                event_type="data_deletion" if hard_delete else "data_anonymization",
                details={"counts": deleted_counts, "hard_delete": hard_delete},
                session=session,
            )
            
            logger.info(f"User data deleted: user_id={user_id}, hard={hard_delete}")
            
            return {
                "success": True,
                "user_id": user_id,
                "hard_delete": hard_delete,
                "deleted_counts": deleted_counts,
            }
            
        except Exception as e:
            await session.rollback()
            logger.error(f"User data deletion failed: {e}")
            return {
                "success": False,
                "user_id": user_id,
                "error": str(e),
            }
    
    async def enforce_retention_policies(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Run retention policy enforcement on all data.
        
        Args:
            session: Database session
        
        Returns:
            Summary of cleanup actions
        """
        results = {
            "old_telemetry_deleted": 0,
            "old_predictions_deleted": 0,
            "old_audit_logs_deleted": 0,
            "old_session_logs_deleted": 0,
            "inactive_users_flagged": 0,
            "errors": [],
        }
        
        try:
            # Clean old telemetry
            cutoff = time.time() - (self.policy.telemetry_days * 86400)
            results["old_telemetry_deleted"] = await self._delete_old_telemetry(cutoff, session)
            
            # Clean old predictions
            cutoff = time.time() - (self.policy.prediction_history_days * 86400)
            results["old_predictions_deleted"] = await self._delete_old_predictions(cutoff, session)
            
            # Clean old session logs
            cutoff = time.time() - (self.policy.session_logs_days * 86400)
            results["old_session_logs_deleted"] = await self._delete_old_session_logs(cutoff, session)
            
            # Flag inactive users
            cutoff = time.time() - (self.policy.inactive_user_days * 86400)
            results["inactive_users_flagged"] = await self._flag_inactive_users(cutoff, session)
            
            await session.commit()
            
            logger.info(f"Retention policies enforced: {results}")
            
        except Exception as e:
            await session.rollback()
            results["errors"].append(str(e))
            logger.error(f"Retention enforcement failed: {e}")
        
        return results
    
    async def record_consent(
        self,
        user_id: int,
        consent_type: str,
        granted: bool,
        session: AsyncSession,
        ip_address: Optional[str] = None,
    ) -> bool:
        """
        Record user consent for data processing.
        
        Args:
            user_id: User giving/withdrawing consent
            consent_type: Type of consent (marketing, analytics, etc.)
            granted: True if consent granted, False if withdrawn
            session: Database session
            ip_address: Optional IP address for audit
        
        Returns:
            True if recorded successfully
        """
        try:
            from predict.core.db.models.audit import ConsentRecord
            
            record = ConsentRecord(
                user_id=user_id,
                consent_type=consent_type,
                granted=granted,
                ip_address=ip_address,
                timestamp=time.time(),
            )
            session.add(record)
            await session.flush()
            
            # Update user's consent flags
            await session.execute(
                text(f"""
                    UPDATE users 
                    SET {consent_type}_consent = :granted,
                        updated_at = :now
                    WHERE id = :user_id
                """),
                {"granted": granted, "user_id": user_id, "now": time.time()}
            )
            
            logger.info(f"Consent recorded: user={user_id}, type={consent_type}, granted={granted}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to record consent: {e}")
            return False
    
    async def get_consent_status(
        self,
        user_id: int,
        session: AsyncSession,
    ) -> Dict[str, Any]:
        """Get current consent status for a user."""
        from predict.core.db.models.user import User
        
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            return {"error": "User not found"}
        
        return {
            "marketing": getattr(user, "marketing_consent", False),
            "analytics": getattr(user, "analytics_consent", True),  # Default to True for core function
            "data_sharing": getattr(user, "data_sharing_consent", False),
            "last_updated": getattr(user, "updated_at", None),
        }
    
    # Private export methods
    
    async def _export_user_profile(self, user_id: int, session: AsyncSession) -> Dict:
        from predict.core.db.models.user import User
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            return {}
        
        return {
            "id": user.id,
            "email": user.email,
            "first_name": getattr(user, "first_name", None),
            "last_name": getattr(user, "last_name", None),
            "tier": getattr(user, "tier", "free"),
            "created_at": user.created_at,
            "last_login": getattr(user, "last_login", None),
        }
    
    async def _export_vehicles(self, user_id: int, session: AsyncSession) -> List[Dict]:
        from predict.core.db.models.vehicle import VehicleProfile
        stmt = select(VehicleProfile).where(VehicleProfile.owner_user_id == user_id)
        result = await session.execute(stmt)
        vehicles = result.scalars().all()
        
        return [
            {
                "id": v.id,
                "name": getattr(v, "name", None),
                "vin": v.vin,
                "make": getattr(v, "make", None),
                "model": getattr(v, "model", None),
                "year": getattr(v, "year", None),
                "created_at": v.created_at,
            }
            for v in vehicles
        ]
    
    async def _export_dtc_history(self, user_id: int, session: AsyncSession) -> List[Dict]:
        from predict.core.db.models.dtc import DTCRecord
        stmt = select(DTCRecord).where(DTCRecord.user_id == user_id)
        result = await session.execute(stmt)
        records = result.scalars().all()
        
        return [
            {
                "code": r.code,
                "status": getattr(r, "status", None),
                "description": getattr(r, "description", None),
                "recorded_at": r.recorded_at,
            }
            for r in records
        ]
    
    async def _export_telemetry(self, user_id: int, session: AsyncSession) -> Dict:
        # Export summary only due to volume
        from predict.core.db.models.vehicle import TelemetryRecord

        stmt = select(func.count(TelemetryRecord.id)).where(TelemetryRecord.user_id == user_id)
        result = await session.execute(stmt)
        count = result.scalar()
        
        # Export last 30 days sample
        cutoff = time.time() - (30 * 86400)
        stmt = select(TelemetryRecord).where(
            TelemetryRecord.user_id == user_id,
            TelemetryRecord.ts >= cutoff
        ).limit(1000)
        result = await session.execute(stmt)
        records = result.scalars().all()
        
        return {
            "total_records": count,
            "sample_period_days": 30,
            "sample_records": [
                {
                    "timestamp": r.ts,
                    "speed": r.gps_speed,
                    "rpm": r.rpm,
                    "coolant_temp": r.coolant_temp,
                }
                for r in records
            ],
        }
    
    async def _export_predictions(self, user_id: int, session: AsyncSession) -> List[Dict]:
        from predict.core.db.models.prediction import Prediction
        stmt = select(Prediction).where(Prediction.user_id == user_id)
        result = await session.execute(stmt)
        predictions = result.scalars().all()
        
        return [
            {
                "id": p.id,
                "component": p.component,
                "risk_score": p.failure_probability,
                "confidence": p.confidence_score,
                "created_at": p.created_at,
            }
            for p in predictions
        ]
    
    async def _export_trips(self, user_id: int, session: AsyncSession) -> List[Dict]:
        from predict.core.db.models.trip import Trip
        stmt = select(Trip).where(Trip.user_id == user_id)
        result = await session.execute(stmt)
        trips = result.scalars().all()
        
        return [
            {
                "id": t.id,
                "start_time": getattr(t, "start_time", None),
                "end_time": getattr(t, "end_time", None),
                "distance_km": getattr(t, "distance_km", None),
                "score": getattr(t, "score", None),
            }
            for t in trips
        ]
    
    async def _export_subscriptions(self, user_id: int, session: AsyncSession) -> List[Dict]:
        from predict.core.db.models.subscription import Subscription
        stmt = select(Subscription).where(Subscription.user_id == user_id)
        result = await session.execute(stmt)
        subs = result.scalars().all()
        
        return [
            {
                "tier": s.tier,
                "status": s.status,
                "start_date": s.start_date,
                "end_date": s.end_date,
            }
            for s in subs
        ]
    
    async def _export_audit_logs(self, user_id: int, session: AsyncSession) -> List[Dict]:
        from predict.core.db.models.audit import AuditLog
        stmt = select(AuditLog).where(AuditLog.user_id == user_id)
        result = await session.execute(stmt)
        logs = result.scalars().all()
        
        return [
            {
                "event_type": l.event_type,
                "details": l.details,
                "timestamp": l.timestamp,
            }
            for l in logs
        ]
    
    # Private deletion methods
    
    async def _delete_user_telemetry(self, user_id: int, session: AsyncSession) -> int:
        from predict.core.db.models.vehicle import TelemetryRecord
        result = await session.execute(
            delete(TelemetryRecord).where(TelemetryRecord.user_id == user_id)
        )
        return result.rowcount
    
    async def _delete_user_dtc(self, user_id: int, session: AsyncSession) -> int:
        from predict.core.db.models.dtc import DTCRecord
        result = await session.execute(
            delete(DTCRecord).where(DTCRecord.user_id == user_id)
        )
        return result.rowcount
    
    async def _delete_user_predictions(self, user_id: int, session: AsyncSession) -> int:
        from predict.core.db.models.prediction import Prediction
        result = await session.execute(
            delete(Prediction).where(Prediction.user_id == user_id)
        )
        return result.rowcount
    
    async def _delete_user_trips(self, user_id: int, session: AsyncSession) -> int:
        from predict.core.db.models.trip import Trip
        result = await session.execute(
            delete(Trip).where(Trip.user_id == user_id)
        )
        return result.rowcount
    
    async def _delete_user_vehicles(self, user_id: int, session: AsyncSession) -> int:
        from predict.core.db.models.vehicle import VehicleProfile
        result = await session.execute(
            delete(VehicleProfile).where(VehicleProfile.owner_user_id == user_id)
        )
        return result.rowcount
    
    async def _delete_user_subscriptions(self, user_id: int, session: AsyncSession) -> int:
        from predict.core.db.models.subscription import Subscription
        result = await session.execute(
            delete(Subscription).where(Subscription.user_id == user_id)
        )
        return result.rowcount
    
    async def _delete_user_account(self, user_id: int, session: AsyncSession) -> int:
        from predict.core.db.models.user import User
        result = await session.execute(
            delete(User).where(User.id == user_id)
        )
        return result.rowcount
    
    async def _anonymize_user_data(self, user_id: int, session: AsyncSession) -> int:
        """Anonymize user data instead of deleting."""
        anonymous_id = f"anon_{uuid.uuid4().hex[:12]}"
        
        await session.execute(
            text("""
                UPDATE users 
                SET email = :anon_email,
                    password_hash = '',
                    first_name = NULL,
                    last_name = NULL,
                    phone = NULL,
                    fcm_token = NULL,
                    is_deleted = TRUE,
                    deleted_at = :now,
                    updated_at = :now
                WHERE id = :user_id
            """),
            {
                "anon_email": f"{anonymous_id}@deleted.predict",
                "user_id": user_id,
                "now": time.time(),
            }
        )
        
        return 1
    
    # Private retention cleanup methods
    
    async def _delete_old_telemetry(self, cutoff: float, session: AsyncSession) -> int:
        from predict.core.db.models.vehicle import TelemetryRecord
        result = await session.execute(
            delete(TelemetryRecord).where(TelemetryRecord.ts < cutoff)
        )
        return result.rowcount
    
    async def _delete_old_predictions(self, cutoff: float, session: AsyncSession) -> int:
        from predict.core.db.models.prediction import Prediction
        result = await session.execute(
            delete(Prediction).where(Prediction.created_at < cutoff)
        )
        return result.rowcount
    
    async def _delete_old_session_logs(self, cutoff: float, session: AsyncSession) -> int:
        from predict.core.db.models.audit import SessionLog
        result = await session.execute(
            delete(SessionLog).where(SessionLog.timestamp < cutoff)
        )
        return result.rowcount
    
    async def _flag_inactive_users(self, cutoff: float, session: AsyncSession) -> int:
        from predict.core.db.models.user import User
        result = await session.execute(
            text("""
                UPDATE users 
                SET inactive_flag = TRUE
                WHERE last_login < :cutoff AND inactive_flag = FALSE
            """),
            {"cutoff": cutoff}
        )
        return result.rowcount
    
    async def _log_audit_event(
        self,
        user_id: int,
        event_type: str,
        details: Dict[str, Any],
        session: AsyncSession,
    ) -> None:
        """Log a GDPR-related audit event."""
        try:
            from predict.core.db.models.audit import AuditLog
            
            log = AuditLog(
                user_id=user_id,
                event_type=event_type,
                details=json.dumps(details),
                timestamp=time.time(),
            )
            session.add(log)
            
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
