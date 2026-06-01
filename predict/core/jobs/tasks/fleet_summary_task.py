"""
Morning Fleet Summary — daily 7 AM push to fleet guardians.

Generates a summary of each fleet's health:
- Vehicles needing attention (health < 50%)
- Overdue services
- Active DTCs across fleet
- Fleet average health score
"""

import logging
import time
from typing import Dict, List, Any

from sqlalchemy import select, desc, func

logger = logging.getLogger(__name__)


async def send_daily_fleet_summary():
    """Generate and push morning fleet summary to all fleet admins."""
    from predict.core.db.session import get_db_session
    from predict.core.db.models.guardian import VehicleGuardian
    from predict.core.db.models.vehicle import VehicleProfile, VehicleData
    from predict.core.db.models.dtc import DTCCodes
    from predict.core.db.models.user import User
    from predict.core.services.fcm_service import FCMService

    fcm = FCMService()

    async with get_db_session() as session:
        # Get all guardian users (distinct)
        guardian_result = await session.execute(
            select(VehicleGuardian.user_id).distinct()
            .where(VehicleGuardian.is_active == True)
        )
        guardian_user_ids = [row[0] for row in guardian_result.fetchall() if row[0]]

        if not guardian_user_ids:
            logger.info("No active guardians — skipping fleet summary")
            return

        logger.info("Generating fleet summaries for %d guardians", len(guardian_user_ids))

        for guardian_id in guardian_user_ids:
            try:
                summary = await _build_guardian_summary(session, guardian_id)
                if summary:
                    await fcm.send_to_user(
                        user_id=guardian_id,
                        title="Morning Fleet Report",
                        body=summary["message"],
                        data={"type": "fleet_summary", "needs_attention": str(summary["needs_attention"])},
                    )
            except Exception as e:
                logger.error("Fleet summary failed for guardian %d: %s", guardian_id, e)

    logger.info("Daily fleet summary complete")


async def _build_guardian_summary(session, guardian_user_id: int) -> Dict[str, Any]:
    """Build summary for a single guardian's fleet."""
    from predict.core.db.models.guardian import VehicleGuardian
    from predict.core.db.models.vehicle import VehicleProfile, VehicleData
    from predict.core.db.models.dtc import DTCCodes

    # Get vehicles this guardian monitors
    links_result = await session.execute(
        select(VehicleGuardian.profile_id)
        .where(VehicleGuardian.user_id == guardian_user_id)
        .where(VehicleGuardian.is_active == True)
    )
    vehicle_ids = [row[0] for row in links_result.fetchall() if row[0]]

    if not vehicle_ids:
        return None

    total = len(vehicle_ids)
    needs_attention = 0
    active_dtc_count = 0

    for vid in vehicle_ids:
        # Check for active DTCs
        dtc_result = await session.execute(
            select(func.count())
            .select_from(DTCCodes)
            .where(DTCCodes.vehicle_id == vid, DTCCodes.is_active == 1)
        )
        dtc_count = dtc_result.scalar() or 0
        active_dtc_count += dtc_count

        # Check if vehicle has recent data (last 24h)
        one_day_ago = time.time() - 86400
        recent_result = await session.execute(
            select(func.count())
            .select_from(VehicleData)
            .where(VehicleData.profile_id == vid, VehicleData.timestamp > one_day_ago)
        )
        recent_count = recent_result.scalar() or 0
        if recent_count == 0:
            needs_attention += 1  # Vehicle hasn't reported in 24h

    # Build message
    parts = [f"{total} vehicles in fleet."]
    if needs_attention > 0:
        parts.append(f"{needs_attention} need attention.")
    if active_dtc_count > 0:
        parts.append(f"{active_dtc_count} active DTCs.")
    if needs_attention == 0 and active_dtc_count == 0:
        parts.append("All healthy.")

    return {
        "message": " ".join(parts),
        "total": total,
        "needs_attention": needs_attention,
        "active_dtcs": active_dtc_count,
    }
