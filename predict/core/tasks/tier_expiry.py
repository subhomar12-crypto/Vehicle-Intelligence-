"""
Tier expiry background task.

Runs daily to downgrade users whose subscriptions have expired.
Started as an asyncio task within the FastAPI lifespan.
"""

import asyncio
import logging
import time

logger = logging.getLogger(__name__)

_expiry_task: asyncio.Task | None = None


async def _run_expiry_loop():
    """
    Continuously check for expired subscriptions every 24 hours.
    Downgrades users whose paid subscription period has ended.
    """
    logger.info("Tier expiry task started — running every 24 hours")
    while True:
        try:
            await _expire_subscriptions()
        except Exception as e:
            logger.error(f"Tier expiry task error: {e}", exc_info=True)
        await asyncio.sleep(86400)  # 24 hours


async def _expire_subscriptions():
    """
    Find subscriptions whose expires_at is in the past and downgrade users to free.
    """
    from predict.core.db.session import get_db_session
    from predict.core.db.models.subscription import Subscription
    from predict.core.db.models.user import User
    from sqlalchemy import select

    now = time.time()
    logger.info(f"Running subscription expiry check (now={now:.0f})")

    async with get_db_session() as session:
        # Find all active subscriptions that have expired
        result = await session.execute(
            select(Subscription).where(
                Subscription.status == "active",
                Subscription.expires_at != None,
                Subscription.expires_at < now,
            )
        )
        expired_subs = result.scalars().all()

        if not expired_subs:
            logger.debug("No expired subscriptions found")
            return

        logger.info(f"Found {len(expired_subs)} expired subscription(s)")

        for sub in expired_subs:
            try:
                # Mark subscription expired
                sub.status = "expired"

                # Downgrade user to free
                user_result = await session.execute(
                    select(User).where(User.id == sub.user_id)
                )
                user = user_result.scalar_one_or_none()
                if user and user.tier not in ("free", "admin"):
                    old_tier = user.tier
                    user.tier = "free"
                    logger.info(
                        f"Downgraded user {sub.user_id} from {old_tier} to free "
                        f"(sub {sub.id} expired at {sub.expires_at:.0f})"
                    )

            except Exception as e:
                logger.error(f"Failed to expire sub {sub.id}: {e}")


def start_expiry_task() -> asyncio.Task:
    """Start the tier expiry background task and return it."""
    global _expiry_task
    _expiry_task = asyncio.create_task(_run_expiry_loop(), name="tier-expiry")
    return _expiry_task


def stop_expiry_task():
    """Cancel the tier expiry task on shutdown."""
    global _expiry_task
    if _expiry_task and not _expiry_task.done():
        _expiry_task.cancel()
        logger.info("Tier expiry task cancelled")
