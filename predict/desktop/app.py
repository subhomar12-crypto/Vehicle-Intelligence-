"""
PREDICT Desktop Application Entry Point.

Initializes PySide6 GUI with embedded FastAPI server.
"""

import logging
import sys
import os
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from predict.core.config import get_config
from predict.core.version import APP_NAME, APP_VERSION
from predict.desktop.server_thread import get_server_manager
from predict.desktop.main_window import PredictMainWindow
from predict.desktop.theme import PredictTheme

logger = logging.getLogger(__name__)


def setup_logging():
    """Setup logging for desktop mode."""
    config = get_config()
    config.ensure_directories()
    
    log_file = config.LOGS_DIR / "desktop.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )


def start_desktop(
    host: str = "127.0.0.1",
    port: int = 8000,
) -> int:
    """
    Run the PREDICT Desktop application.
    
    Args:
        host: Server bind address
        port: Server port
    
    Returns:
        Exit code
    """
    # Setup logging
    setup_logging()
    
    logger.info(f"Starting {APP_NAME} Desktop v{APP_VERSION}")
    
    # Enable high DPI scaling (must be set BEFORE QApplication is created)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Create Qt Application
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    # Apply dark theme
    PredictTheme.apply_dark_theme(app)
    
    try:
        # Start embedded server
        logger.info("Starting embedded server...")
        server_manager = get_server_manager()
        server = server_manager.start_server(host=host, port=port)
        
        if not server.is_running():
            logger.error("Failed to start embedded server")
            return 1
        
        logger.info(f"Server running at {server.base_url}")
        
        # Create and show main window
        logger.info("Creating main window...")
        window = PredictMainWindow()
        window.show()
        
        logger.info("Application ready")
        
        # Run Qt event loop
        exit_code = app.exec()
        
        # Cleanup
        logger.info("Shutting down...")
        server_manager.stop_server()
        
        return exit_code
    
    except Exception as e:
        logger.exception(f"Application error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(start_desktop())
