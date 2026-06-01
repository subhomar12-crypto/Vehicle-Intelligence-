"""
Audit log and failed operation repository.
"""

import time
import logging
from typing import Optional, List

from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.models.audit import AuditLog, FailedOperation
from predict.core.db.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class AuditLogRepository(BaseRepository[AuditLog]):
    """Repository for Audit Log entities."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, AuditLog)
    
    async def log_action(
        self,
        action: str,
        user_id: int,
        details: str,
        ip_address: str,
        request_id: str,
    ) -> AuditLog:
        """Log an audit action."""
        audit_entry = await self.create(
            action=action,
            user_id=user_id,
            details=details,
            ip_address=ip_address,
            request_id=request_id,
            timestamp=time.time(),
        )
        logger.info(f"Audit: {action} by user {user_id}")
        return audit_entry
    
    async def get_audit_trail(
        self,
        user_id: int,
        limit: int = 100,
    ) -> List[AuditLog]:
        """Get audit trail for a user."""
        stmt = (
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(desc(AuditLog.timestamp))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_by_action(
        self,
        action: str,
        limit: int = 50,
    ) -> List[AuditLog]:
        """Get audit logs for a specific action type."""
        stmt = (
            select(AuditLog)
            .where(AuditLog.action == action)
            .order_by(desc(AuditLog.timestamp))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_recent(
        self,
        limit: int = 100,
    ) -> List[AuditLog]:
        """Get recent audit logs."""
        stmt = (
            select(AuditLog)
            .order_by(desc(AuditLog.timestamp))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_by_request_id(self, request_id: str) -> List[AuditLog]:
        """Get audit logs by request ID."""
        stmt = (
            select(AuditLog)
            .where(AuditLog.request_id == request_id)
            .order_by(AuditLog.timestamp)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class FailedOperationRepository(BaseRepository[FailedOperation]):
    """Repository for Failed Operation entities."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, FailedOperation)
    
    async def record_failure(
        self,
        operation_type: str,
        payload: dict,
        error_message: str,
    ) -> FailedOperation:
        """Record a failed operation for retry."""
        failed_op = await self.create(
            operation_type=operation_type,
            payload=payload,
            error_message=error_message,
            retry_count=0,
            status='pending',
            created_at=time.time(),
        )
        logger.warning(f"Recorded failed operation: {operation_type}")
        return failed_op
    
    async def get_failed_operations(
        self,
        status: str,
        limit: int = 50,
    ) -> List[FailedOperation]:
        """Get failed operations by status."""
        stmt = (
            select(FailedOperation)
            .where(FailedOperation.status == status)
            .order_by(desc(FailedOperation.created_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def mark_operation_completed(self, op_id: int) -> None:
        """Mark a failed operation as completed (after successful retry)."""
        op = await self.get_by_id(op_id)
        if op:
            op.status = 'completed'
            op.completed_at = time.time()
            await self.session.flush()
    
    async def mark_operation_failed_permanently(
        self,
        op_id: int,
        error: str,
    ) -> None:
        """Mark operation as permanently failed (max retries exceeded)."""
        op = await self.get_by_id(op_id)
        if op:
            op.status = 'failed'
            op.error_message = error
            await self.session.flush()
    
    async def get_retry_candidates(self) -> List[FailedOperation]:
        """
        Get operations ready for retry.
        
        Returns operations that are pending and haven't exceeded max retries.
        """
        import time
        
        # Exponential backoff: wait longer between each retry
        # retry_count: 0 -> wait 60s, 1 -> wait 300s, 2 -> wait 900s
        backoff_delays = [60, 300, 900, 3600]
        
        stmt = (
            select(FailedOperation)
            .where(FailedOperation.status == 'pending')
            .where(FailedOperation.retry_count < 4)
            .order_by(desc(FailedOperation.created_at))
        )
        result = await self.session.execute(stmt)
        candidates = result.scalars().all()
        
        # Filter based on backoff timing
        ready = []
        now = time.time()
        for op in candidates:
            delay = backoff_delays[min(op.retry_count, len(backoff_delays) - 1)]
            if now - op.created_at > delay:
                ready.append(op)
        
        return ready
    
    async def increment_retry_count(self, op_id: int) -> None:
        """Increment the retry count for an operation."""
        op = await self.get_by_id(op_id)
        if op:
            op.retry_count += 1
            await self.session.flush()
    
    async def get_failure_stats(self) -> dict:
        """Get statistics about failed operations."""
        stmt = (
            select(
                FailedOperation.status,
                func.count(FailedOperation.id).label('count')
            )
            .group_by(FailedOperation.status)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        
        return {
            row.status: row.count
            for row in rows
        }
