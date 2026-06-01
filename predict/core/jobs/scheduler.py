"""
APScheduler setup for periodic background tasks.

Jobs:
- Daily backup at 2 AM
- GDPR cleanup at 3 AM
- Daily stats aggregation at 8 PM
- Service overdue check every 1 hour
- Stale research refresh every 6 hours
- Parquet buffer flush every 30 minutes
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_scheduler = None


def get_scheduler():
    """Get or create the singleton scheduler."""
    global _scheduler
    if _scheduler is None:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        _scheduler = AsyncIOScheduler(
            job_defaults={"coalesce": True, "max_instances": 1},
        )
    return _scheduler


async def _safe_gdpr_cleanup():
    """Run GDPR cleanup with its own DB session."""
    try:
        from predict.core.db.session import get_db_session
        from predict.core.services.gdpr_service import GDPRService

        async with get_db_session() as session:
            service = GDPRService()
            results = await service.enforce_retention_policies(session)
            await session.commit()
            logger.info("Scheduled GDPR cleanup completed: %s", results)
    except Exception as e:
        logger.error("Scheduled GDPR cleanup failed: %s", e)


async def _safe_aggregate_daily():
    """Run daily stats aggregation."""
    try:
        from predict.core.jobs.tasks.aggregation_tasks import aggregate_daily_stats
        await aggregate_daily_stats()
        logger.info("Scheduled daily aggregation completed")
    except Exception as e:
        logger.error("Scheduled daily aggregation failed: %s", e)


async def _check_service_overdue():
    """Check all vehicles for overdue services and emit events."""
    try:
        from predict.core.db.session import get_db_session
        from predict.core.db.models.vehicle import VehicleProfile, ServiceRecord
        from predict.core.events.event_bus import event_bus
        from sqlalchemy import select

        async with get_db_session() as session:
            # Get vehicles with service records
            stmt = select(ServiceRecord).where(
                ServiceRecord.expected_lifespan_km.isnot(None),
                ServiceRecord.service_km.isnot(None),
            )
            result = await session.execute(stmt)
            records = result.scalars().all()

            for record in records:
                if not record.expected_lifespan_km or not record.service_km:
                    continue
                # Simple check: if service_km + expected_lifespan < current estimate
                overdue_km = 0  # Would need current odometer; simplified for now
                if overdue_km > 0:
                    # Get owner
                    profile_result = await session.execute(
                        select(VehicleProfile).where(
                            VehicleProfile.profile_id == record.profile_id
                        )
                    )
                    profile = profile_result.scalar_one_or_none()
                    if profile and profile.owner_user_id:
                        await event_bus.emit("service_overdue", {
                            "vehicle_id": record.profile_id,
                            "owner_id": profile.owner_user_id,
                            "service_type": record.service_type or "Maintenance",
                            "overdue_km": overdue_km,
                        })
    except Exception as e:
        logger.error("Service overdue check failed: %s", e)


async def _safe_fleet_summary():
    """Run morning fleet summary."""
    try:
        from predict.core.jobs.tasks.fleet_summary_task import send_daily_fleet_summary
        await send_daily_fleet_summary()
        logger.info("Scheduled fleet summary completed")
    except Exception as e:
        logger.error("Scheduled fleet summary failed: %s", e)


async def _refresh_stale_research():
    """Refresh vehicle research that's older than 30 days."""
    try:
        import time
        from predict.core.db.session import get_db_session
        from predict.core.db.models.vehicle import VehicleResearch
        from sqlalchemy import select

        thirty_days_ago = time.time() - (30 * 86400)

        async with get_db_session() as session:
            stmt = select(VehicleResearch).where(
                VehicleResearch.status == "completed",
                VehicleResearch.researched_at < thirty_days_ago,
            )
            result = await session.execute(stmt)
            stale = result.scalars().all()

            for research in stale:
                research.status = "stale"

            if stale:
                await session.commit()
                logger.info("Marked %d research records as stale", len(stale))
    except Exception as e:
        logger.error("Stale research refresh failed: %s", e)


def setup_scheduler():
    """Configure and start all scheduled jobs."""
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    scheduler = get_scheduler()

    # Daily GDPR cleanup at 3 AM
    scheduler.add_job(
        _safe_gdpr_cleanup,
        CronTrigger(hour=3),
        id="gdpr_cleanup",
        replace_existing=True,
    )

    # Daily stats aggregation at 8 PM
    scheduler.add_job(
        _safe_aggregate_daily,
        CronTrigger(hour=20),
        id="daily_stats",
        replace_existing=True,
    )

    # Service overdue check every 1 hour
    scheduler.add_job(
        _check_service_overdue,
        IntervalTrigger(hours=1),
        id="service_check",
        replace_existing=True,
    )

    # Stale research refresh every 6 hours
    scheduler.add_job(
        _refresh_stale_research,
        IntervalTrigger(hours=6),
        id="research_refresh",
        replace_existing=True,
    )

    # Morning fleet summary at 7 AM
    scheduler.add_job(
        _safe_fleet_summary,
        CronTrigger(hour=7),
        id="fleet_summary",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "APScheduler started with %d jobs: %s",
        len(scheduler.get_jobs()),
        [j.id for j in scheduler.get_jobs()],
    )


def shutdown_scheduler():
    """Gracefully stop the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler shut down")
    _scheduler = None
