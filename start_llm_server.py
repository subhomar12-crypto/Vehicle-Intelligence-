"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Start Llm Server

LLM Server Auto-Restart Wrapper
Keeps the LLM API server running continuously
Automatically restarts if it crashes
"""

import subprocess
import sys
import time
import logging
from datetime import datetime
from pathlib import Path

# Import config for path management
try:
    from config import get_config
    CONFIG = get_config()
    SCRIPT_DIR = str(CONFIG.ROOT_DIR)
except ImportError:
    CONFIG = None
    SCRIPT_DIR = str(Path(__file__).parent)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('llm_server_wrapper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

MAX_RESTARTS = 10
RESTART_DELAY = 5  # seconds between restarts
RESET_COUNTER_AFTER = 300  # reset restart counter after 5 minutes of stable running


def run_server():
    """Run the LLM API server with auto-restart."""
    restart_count = 0
    last_restart_time = time.time()

    logger.info("=" * 60)
    logger.info("LLM Server Auto-Restart Wrapper Started")
    logger.info("=" * 60)

    while restart_count < MAX_RESTARTS:
        try:
            logger.info(f"Starting LLM API Server (attempt {restart_count + 1})...")

            # Run the server
            process = subprocess.Popen(
                [sys.executable, "llm_api_server.py"],
                cwd=SCRIPT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # Stream output
            start_time = time.time()
            for line in process.stdout:
                print(line, end='')

                # Reset restart counter if server has been running for a while
                if time.time() - start_time > RESET_COUNTER_AFTER:
                    if restart_count > 0:
                        logger.info("Server stable - resetting restart counter")
                        restart_count = 0
                        start_time = time.time()

            # Server exited
            exit_code = process.wait()
            logger.warning(f"Server exited with code {exit_code}")

            # Check if we should restart
            restart_count += 1

            if restart_count >= MAX_RESTARTS:
                logger.error(f"Max restarts ({MAX_RESTARTS}) reached. Stopping.")
                break

            logger.info(f"Restarting in {RESTART_DELAY} seconds...")
            time.sleep(RESTART_DELAY)

        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
            if process:
                process.terminate()
            break
        except Exception as e:
            logger.error(f"Error running server: {e}")
            restart_count += 1
            time.sleep(RESTART_DELAY)

    logger.info("LLM Server Wrapper shutting down")


if __name__ == "__main__":
    run_server()
