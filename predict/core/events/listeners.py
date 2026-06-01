"""
Event listeners for automated push notifications.

Listens to events emitted by the health assessment, telemetry,
and fleet monitoring systems. Sends push notifications via FCM.
"""

import logging
from typing import Dict, Any

from predict.core.events.event_bus import event_bus

logger = logging.getLogger(__name__)


def _get_fcm():
    """Lazy import to avoid circular deps at module level."""
    from predict.core.services.fcm_service import FCMService
    return FCMService()


@event_bus.on("urgency_escalated")
async def on_urgency_escalated(event: Dict[str, Any]):
    """Push critical/warning alerts to vehicle owner."""
    level = event.get("level", "WARNING")
    owner_id = event.get("owner_id")
    reason = event.get("reason", "Vehicle needs attention")
    vehicle_id = event.get("vehicle_id")

    if not owner_id:
        logger.debug("urgency_escalated: no owner_id, skipping push")
        return

    fcm = _get_fcm()

    if level == "CRITICAL":
        title = "Critical Vehicle Alert"
        channel = "guardian_alerts_critical"
    else:
        title = "Vehicle Warning"
        channel = "guardian_alerts_warning"

    await fcm.send_to_user(
        user_id=owner_id,
        title=title,
        body=reason,
        data={"type": "urgency", "vehicle_id": str(vehicle_id), "level": level},
    )
    logger.info("Pushed urgency %s alert to user %s for vehicle %s", level, owner_id, vehicle_id)


@event_bus.on("urgency_escalated")
async def on_urgency_guardian_notify(event: Dict[str, Any]):
    """Notify guardians when a monitored vehicle has a critical alert."""
    if event.get("level") != "CRITICAL":
        return

    vehicle_id = event.get("vehicle_id")
    if not vehicle_id:
        return

    try:
        from predict.core.db.session import get_db_session
        from predict.core.db.repositories.guardian_repo import GuardianRepository

        async with get_db_session() as session:
            repo = GuardianRepository(session)
            guardians = await repo.get_guardians_for_vehicle(vehicle_id)

        fcm = _get_fcm()
        for g in guardians:
            guardian_user_id = getattr(g, "guardian_user_id", None)
            if guardian_user_id:
                await fcm.send_to_user(
                    user_id=guardian_user_id,
                    title="Fleet Vehicle Critical Alert",
                    body=f"Vehicle #{vehicle_id}: {event.get('reason', 'Needs attention')}",
                    data={"type": "guardian_urgency", "vehicle_id": str(vehicle_id)},
                )
    except Exception as e:
        logger.error("Failed to notify guardians for vehicle %s: %s", vehicle_id, e)


@event_bus.on("speed_exceeded")
async def on_speed_exceeded(event: Dict[str, Any]):
    """Alert guardians when a driver exceeds speed threshold."""
    vehicle_id = event.get("vehicle_id")
    speed = event.get("speed", 0)

    if not vehicle_id:
        return

    try:
        from predict.core.db.session import get_db_session
        from predict.core.db.repositories.guardian_repo import GuardianRepository

        async with get_db_session() as session:
            repo = GuardianRepository(session)
            guardians = await repo.get_guardians_for_vehicle(vehicle_id)

        fcm = _get_fcm()
        for g in guardians:
            guardian_user_id = getattr(g, "guardian_user_id", None)
            if guardian_user_id:
                await fcm.send_guardian_alert(
                    guardian_token="",  # send_to_user via user_id instead
                    alert_type="speeding",
                    alert_data={
                        "title": "Speeding Alert",
                        "message": f"Driver reached {speed:.0f} km/h",
                        "vehicle_id": vehicle_id,
                        "severity": "high",
                    },
                )
                # Also use direct user push (more reliable)
                await fcm.send_to_user(
                    user_id=guardian_user_id,
                    title="Speeding Alert",
                    body=f"Vehicle #{vehicle_id} reached {speed:.0f} km/h",
                    data={"type": "speeding", "vehicle_id": str(vehicle_id)},
                )
    except Exception as e:
        logger.error("Failed to send speed alert for vehicle %s: %s", vehicle_id, e)


@event_bus.on("service_overdue")
async def on_service_overdue(event: Dict[str, Any]):
    """Notify vehicle owner about overdue service."""
    owner_id = event.get("owner_id")
    service_type = event.get("service_type", "Service")
    overdue_km = event.get("overdue_km", 0)
    vehicle_id = event.get("vehicle_id")

    if not owner_id:
        return

    fcm = _get_fcm()
    await fcm.send_to_user(
        user_id=owner_id,
        title=f"{service_type} Overdue",
        body=f"Overdue by {overdue_km:,.0f} km — schedule service soon",
        data={"type": "service_overdue", "vehicle_id": str(vehicle_id)},
    )
    logger.info("Pushed service overdue to user %s for vehicle %s", owner_id, vehicle_id)


@event_bus.on("health_assessment_completed")
async def on_health_assessment_completed(event: Dict[str, Any]):
    """Log health assessments for monitoring. No push — too noisy."""
    vehicle_id = event.get("vehicle_id")
    score = event.get("health_score", 0)
    logger.info("Health assessment completed for vehicle %s: score=%s", vehicle_id, score)
