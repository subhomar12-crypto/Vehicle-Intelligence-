"""
Reports API routes for PDF generation and analytics.

Handles vehicle health reports, trip reports, and maintenance summaries.
Reports are generated asynchronously via ARQ + Redis and emailed when ready.
"""

import logging
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from predict.core.db.session import get_db as get_db_session
from predict.core.security.auth import get_current_user
from predict.core.services.pdf_service import PDFService
from predict.core.services.fcm_service import FCMService
from predict.core.services.websocket_service import ws_manager
from predict.core.db.models.vehicle import VehicleProfile, ServiceRecord
from predict.core.db.models.prediction import Prediction
from predict.core.db.models.trip import Trip
from predict.core.db.models.audit import Report
from predict.core.db.models.guardian import VehicleGuardian

logger = logging.getLogger(__name__)
router = APIRouter()

DAILY_REPORT_LIMIT = 5


# Pydantic models
class GenerateReportRequest(BaseModel):
    report_type: str  # diagnostic, maintenance, trip
    vehicle_id: int
    trip_id: Optional[int] = None
    start_date: Optional[float] = None
    end_date: Optional[float] = None
    include_ai_predictions: bool = False


@router.post("/generate")
async def generate_report(
    request: GenerateReportRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """
    Enqueue a PDF report for background generation.

    Returns immediately with report_id and a message. The report will be
    generated asynchronously via ARQ worker, then emailed to the user
    and made available for download from /download/{report_id}.
    """
    user_id = current_user.get("user_id")

    # Verify vehicle access: owner OR active guardian
    vehicle_stmt = select(VehicleProfile).where(
        VehicleProfile.profile_id == request.vehicle_id,
    )
    vehicle_result = await session.execute(vehicle_stmt)
    vehicle = vehicle_result.scalar_one_or_none()

    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    is_owner = vehicle.owner_user_id == user_id
    if not is_owner:
        guardian_stmt = select(VehicleGuardian).where(
            VehicleGuardian.user_id == user_id,
            VehicleGuardian.profile_id == request.vehicle_id,
            VehicleGuardian.is_active == True,
        )
        guardian_result = await session.execute(guardian_stmt)
        guardian_link = guardian_result.scalar_one_or_none()
        if not guardian_link:
            raise HTTPException(status_code=403, detail="Not authorized to access this vehicle")

    # Rate limit: 5 reports per user per day
    today_start = time.time() - (time.time() % 86400)
    count_stmt = select(func.count(Report.id)).where(
        Report.user_id == user_id,
        Report.created_at >= today_start,
    )
    count_result = await session.execute(count_stmt)
    today_count = count_result.scalar() or 0
    if today_count >= DAILY_REPORT_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Report limit reached (5 per day). Try again tomorrow.",
        )

    # Normalize report type aliases
    report_type = request.report_type
    if report_type in ("health", "driving"):
        report_type = "diagnostic"
    elif report_type == "fuel":
        report_type = "maintenance"

    if report_type not in ("diagnostic", "maintenance", "trip"):
        raise HTTPException(status_code=400, detail="Invalid report type")
    if report_type == "trip" and not request.trip_id:
        raise HTTPException(status_code=400, detail="trip_id required for trip reports")

    # Create pending Report row
    current_time = time.time()
    report = Report(
        user_id=user_id,
        vehicle_id=request.vehicle_id,
        report_type=report_type,
        file_path="",  # filled by ARQ job on completion
        status="pending",
        created_at=current_time,
        updated_at=current_time,
    )
    session.add(report)
    await session.flush()

    # Enqueue ARQ background job
    try:
        from predict.core.jobs.queue import enqueue_enhanced_report
        await enqueue_enhanced_report(
            report_id=report.id,
            vehicle_id=request.vehicle_id,
            report_type=report_type,
            user_id=user_id,
            trip_id=request.trip_id,
            include_ai_predictions=request.include_ai_predictions,
        )
        logger.info(
            f"Report enqueued: id={report.id}, type={report_type}, vehicle={request.vehicle_id}"
        )
    except Exception as e:
        logger.error(f"Failed to enqueue report job: {e}")
        report.status = "failed"
        report.updated_at = time.time()
        raise HTTPException(status_code=500, detail="Failed to start report generation")

    return {
        "success": True,
        "report_id": report.id,
        "report_type": report_type,
        "vehicle_id": request.vehicle_id,
        "created_at": current_time,
        "message": "Report is being generated. You'll receive an email when it's ready.",
        "timestamp": time.time(),
    }


@router.get("/status/{report_id}")
async def get_report_status(
    report_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Get the status of a report generation."""
    user_id = current_user.get("user_id")
    
    stmt = select(Report).where(
        Report.id == report_id,
        Report.user_id == user_id,
    )
    result = await session.execute(stmt)
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return {
        "report_id": report.id,
        "status": report.status,
        "report_type": report.report_type,
        "vehicle_id": report.vehicle_id,
        "created_at": report.created_at,
        "completed_at": report.updated_at if report.status in ("ready", "completed") else None,
        "download_url": f"/api/v1/report/download/{report.id}",
        "timestamp": time.time(),
    }


@router.get("/download/{report_id}")
async def download_report(
    report_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Download a generated report."""
    user_id = current_user.get("user_id")
    
    stmt = select(Report).where(
        Report.id == report_id,
        Report.user_id == user_id,
    )
    result = await session.execute(stmt)
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    if report.status not in ("ready", "completed"):
        raise HTTPException(
            status_code=400, detail=f"Report status: {report.status}"
        )
    
    file_path = Path(report.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    
    return FileResponse(
        path=str(file_path),
        filename=f"predict_report_{report.report_type}_{report.vehicle_id}.pdf",
        media_type="application/pdf",
    )


@router.get("/history")
async def get_report_history(
    limit: int = Query(20, ge=1, le=100),
    report_type: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Get report generation history for current user."""
    user_id = current_user.get("user_id")

    stmt = (
        select(Report)
        .where(Report.user_id == user_id)
        .order_by(desc(Report.created_at))
        .limit(limit)
    )

    if report_type:
        stmt = stmt.where(Report.report_type == report_type)
    
    result = await session.execute(stmt)
    reports = result.scalars().all()
    
    return {
        "reports": [
            {
                "id": r.id,
                "report_type": r.report_type,
                "vehicle_id": r.vehicle_id,
                "status": r.status,
                "created_at": r.created_at,
                "download_url": f"/api/v1/report/download/{r.id}",
            }
            for r in reports
        ],
        "count": len(reports),
        "timestamp": time.time(),
    }


@router.delete("/{report_id}")
async def delete_report(
    report_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Delete a report."""
    user_id = current_user.get("user_id")

    stmt = select(Report).where(
        Report.id == report_id,
        Report.user_id == user_id,
    )
    result = await session.execute(stmt)
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Delete file
    file_path = Path(report.file_path)
    if file_path.exists():
        file_path.unlink()
    
    # Delete record
    await session.delete(report)
    await session.flush()
    
    logger.info(f"Report deleted: {report_id} by user {user_id}")
    
    return {
        "status": "success",
        "report_id": report_id,
        "timestamp": time.time(),
    }
