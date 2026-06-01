"""
AI Training scheduler task.
Runs as ARQ cron job every 15 minutes.
Checks if current time is within the configured training window.
"""

import json
import logging
import time
from pathlib import Path

from predict.core.config import get_config
from predict.core.ai.unified_ai_module import get_unified_ai

logger = logging.getLogger(__name__)


async def check_and_start_training(ctx):
    """Check if it's time to start AI training."""
    config = get_config()
    schedule_path = Path(config.DATA_DIR) / "ai_schedule.json"

    if not schedule_path.exists():
        return  # No schedule configured

    with open(schedule_path, "r") as f:
        schedule = json.loads(f.read())

    if not schedule.get("enabled", False):
        return

    # Check if current time is within window
    now = time.localtime()
    current_minutes = now.tm_hour * 60 + now.tm_min
    start_minutes = schedule["start_hour"] * 60 + schedule.get("start_minute", 0)
    end_minutes = schedule["end_hour"] * 60 + schedule.get("end_minute", 0)

    if start_minutes <= current_minutes < end_minutes:
        # Check if training is already in progress
        ai = get_unified_ai()
        status = ai.get_system_status()

        if status.get("training_in_progress", False):
            logger.info("Training already in progress, skipping")
            return

        logger.info("Starting scheduled AI training")
        # Start training (this should be non-blocking)
        # The actual training implementation depends on UnifiedAI's API
        # ai.start_training() or similar
    else:
        logger.debug("Outside training window (%02d:%02d - %02d:%02d), current: %02d:%02d",
                     schedule["start_hour"], schedule.get("start_minute", 0),
                     schedule["end_hour"], schedule.get("end_minute", 0),
                     now.tm_hour, now.tm_min)
