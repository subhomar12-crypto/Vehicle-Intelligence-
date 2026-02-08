"""
PREDICT Desktop GUI module.

PySide6-based desktop application with embedded FastAPI server.

Usage:
    from predict.desktop import run_desktop_app
    
    # Launch desktop app
    run_desktop_app(host="127.0.0.1", port=8000)
"""

from predict.desktop.app import run_desktop_app
from predict.desktop.server_thread import (
    EmbeddedServer,
    ServerManager,
    get_server_manager,
)
from predict.desktop.main_window import PredictMainWindow

__all__ = [
    "run_desktop_app",
    "EmbeddedServer",
    "ServerManager",
    "get_server_manager",
    "PredictMainWindow",
]
