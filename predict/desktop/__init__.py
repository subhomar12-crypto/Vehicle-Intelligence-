"""
PREDICT Desktop GUI module.

PySide6-based desktop application with embedded FastAPI server.

Usage:
    from predict.desktop import start_desktop
    
    # Launch desktop app
    start_desktop(host="127.0.0.1", port=8000)
"""

from predict.desktop.app import start_desktop
from predict.desktop.server_thread import (
    EmbeddedServer,
    ServerManager,
    get_server_manager,
)
from predict.desktop.main_window import PredictMainWindow

__all__ = [
    "start_desktop",
    "EmbeddedServer",
    "ServerManager",
    "get_server_manager",
    "PredictMainWindow",
]
