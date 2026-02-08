"""
Legal/GDPR endpoints.

Handles:
- Data export (right to data portability)
- Account deletion (right to be forgotten)
- Consent management
- Privacy policy acceptance
"""

import logging
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.api.deps import get_db, get_current_user
from predict.core.db.models.audit import ConsentRecord

logger = logging.getLogger(__name__)

router = APIRouter()


# ========================
# Request/Response Models
# ========================

class ConsentRequest(BaseModel):
    consent_type: str  # privacy_policy, terms_of_service, data_processing
    version: str
    is_granted: bool


class ExportRequest(BaseModel):
    data_types: list  # profile, vehicle_data, predictions, etc.
    format: str = "json"  # json, csv


# ========================
# Consent Management
# ========================

@router.get("/consents")
async def get_consents(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's consent records."""
    result = await db.execute(
        select(ConsentRecord).where(
            ConsentRecord.user_id == current_user['user_id']
        ).order_by(ConsentRecord.created_at.desc())
    )
    consents = result.scalars().all()
    
    return {
        "consents": [
            {
                "type": c.consent_type,
                "version": c.version,
                "is_granted": c.is_granted,
                "granted_at": c.granted_at.isoformat() if c.granted_at else None,
                "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
            }
            for c in consents
        ]
    }


@router.post("/consent")
async def record_consent(
    request: ConsentRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record a consent decision."""
    consent = ConsentRecord(
        user_id=current_user['user_id'],
        consent_type=request.consent_type,
        version=request.version,
        is_granted=request.is_granted,
        granted_at=datetime.now(timezone.utc) if request.is_granted else None,
    )
    
    db.add(consent)
    await db.commit()
    
    return {"success": True, "message": "Consent recorded"}


# ========================
# Data Export (GDPR Article 20)
# ========================

@router.post("/export/request")
async def request_data_export(
    request: ExportRequest,
    bg_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Request a data export (right to data portability).
    
    The export will be generated asynchronously and a download link
    will be sent via email when ready.
    """
    # TODO Phase 5: Implement async export generation
    
    return {
        "success": True,
        "message": "Data export requested. You will receive an email when it's ready.",
        "request_id": "export-request-id-placeholder",
    }


@router.get("/export/status/{request_id}")
async def get_export_status(
    request_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Check the status of a data export request."""
    # TODO Phase 5: Implement export status checking
    
    return {
        "request_id": request_id,
        "status": "pending",  # pending, processing, ready, expired
        "download_url": None,
        "expires_at": None,
    }


# ========================
# Account Deletion (GDPR Article 17)
# ========================

@router.post("/delete-account/request")
async def request_account_deletion(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Request account deletion (right to be forgotten).
    
    This initiates the deletion process. There's a 30-day grace period
    during which the user can cancel the deletion.
    """
    # TODO Phase 5: Implement deletion workflow
    
    return {
        "success": True,
        "message": "Account deletion initiated. You have 30 days to cancel.",
        "deletion_scheduled_at": "2026-03-10T00:00:00Z",  # Placeholder
    }


@router.post("/delete-account/cancel")
async def cancel_account_deletion(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a pending account deletion."""
    # TODO Phase 5: Implement deletion cancellation
    
    return {
        "success": True,
        "message": "Account deletion cancelled",
    }


# ========================
# Privacy Policy & Terms
# ========================

@router.get("/privacy-policy")
async def get_privacy_policy():
    """Get the current privacy policy."""
    return {
        "version": "1.0.0",
        "last_updated": "2026-01-01",
        "url": "https://predict.previlium.com/legal/privacy",
        "summary": "We collect vehicle data to provide predictive maintenance insights. "
                   "Your data is encrypted and never sold to third parties.",
    }


@router.get("/terms-of-service")
async def get_terms_of_service():
    """Get the current terms of service."""
    return {
        "version": "1.0.0",
        "last_updated": "2026-01-01",
        "url": "https://predict.previlium.com/legal/terms",
    }
