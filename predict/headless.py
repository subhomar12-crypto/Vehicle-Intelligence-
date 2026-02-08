"""
Headless mode entry point.

Runs the FastAPI server without GUI for 24/7 operation.
Can be installed as a Windows service using NSSM.

Usage:
    python -m predict --headless
    python -m predict --headless --host 0.0.0.0 --port 8000
"""

import logging
import sys
import signal
from typing import Optional

import uvicorn

from predict.core.version import APP_NAME, APP_VERSION
from predict.core.config import get_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('data/logs/server.log', encoding='utf-8'),
    ]
)
logger = logging.getLogger(__name__)


class HeadlessServer:
    """Headless server runner."""
    
    def __init__(self):
        self.server = None
        self.should_exit = False
    
    def start(self, host: Optional[str] = None, port: Optional[int] = None):
        """Start the headless server."""
        config = get_config()
        
        host = host or config.SERVER_HOST
        port = port or config.SERVER_PORT
        
        logger.info(f"Starting {APP_NAME} v{APP_VERSION} in headless mode")
        logger.info(f"Server will listen on {host}:{port}")
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Ensure log directory exists
        import os
        os.makedirs('data/logs', exist_ok=True)
        
        # Create Uvicorn server
        self.server = uvicorn.Server(
            uvicorn.Config(
                app="predict.core.api.app:create_app",
                factory=True,
                host=host,
                port=port,
                log_level="info",
                access_log=True,
                reload=False,  # No reload in production
            )
        )
        
        try:
            # Run server
            self.server.run()
        except Exception as e:
            logger.error(f"Server error: {e}", exc_info=True)
            raise
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.should_exit = True
        if self.server:
            self.server.should_exit = True


def start_headless(host: Optional[str] = None, port: Optional[int] = None):
    """
    Entry point for headless mode.
    
    Args:
        host: Bind host (default from config)
        port: Bind port (default from config)
    """
    server = HeadlessServer()
    server.start(host=host, port=port)


if __name__ == "__main__":
    start_headless()
