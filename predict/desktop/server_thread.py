"""
Embedded server thread for desktop mode.

Runs FastAPI server in a background thread with proper
lifecycle management for PySide6 GUI integration.
"""

import logging
import asyncio
import threading
import time
from typing import Optional

import uvicorn
from uvicorn.config import Config as UvicornConfig

from predict.core.api.app import create_app

logger = logging.getLogger(__name__)


class EmbeddedServer:
    """
    Embedded FastAPI server for desktop mode.
    
    Runs the server in a background thread so the GUI
    remains responsive.
    """
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        log_level: str = "info",
    ):
        self.host = host
        self.port = port
        self.log_level = log_level
        
        self._server: Optional[uvicorn.Server] = None
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._shutdown_event = threading.Event()
        self._started = False
    
    def start(self) -> None:
        """Start the embedded server in a background thread."""
        if self._started:
            logger.warning("Server already started")
            return
        
        logger.info(f"Starting embedded server on {self.host}:{self.port}")
        
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()
        
        # Wait for server to be ready
        self._wait_for_ready(timeout=30)
        self._started = True
        
        logger.info("Embedded server started successfully")
    
    def _run_server(self) -> None:
        """Server thread entry point."""
        # Create new event loop for this thread
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            # Create FastAPI app
            app = create_app()
            
            # Configure uvicorn
            config = UvicornConfig(
                app=app,
                host=self.host,
                port=self.port,
                log_level=self.log_level,
                loop="asyncio",
            )
            
            self._server = uvicorn.Server(config)
            
            # Run server (blocks until shutdown)
            self._loop.run_until_complete(self._server.serve())
        
        except Exception as e:
            logger.error(f"Server error: {e}")
        
        finally:
            self._shutdown_event.set()
    
    def _wait_for_ready(self, timeout: float = 30) -> bool:
        """
        Wait for server to be ready.
        
        Args:
            timeout: Maximum wait time in seconds
        
        Returns:
            True if server ready, False on timeout
        """
        import socket
        
        start = time.time()
        while time.time() - start < timeout:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((self.host, self.port))
                sock.close()
                
                if result == 0:
                    return True
            except Exception:
                pass
            
            time.sleep(0.1)
        
        return False
    
    def stop(self, timeout: float = 10) -> None:
        """
        Stop the embedded server gracefully.
        
        Args:
            timeout: Shutdown timeout in seconds
        """
        if not self._started:
            return
        
        logger.info("Stopping embedded server...")
        
        if self._loop and self._server:
            try:
                # Schedule shutdown in server's event loop
                asyncio.run_coroutine_threadsafe(
                    self._server.shutdown(),
                    self._loop
                )
                
                # Wait for shutdown to complete
                if self._thread and self._thread.is_alive():
                    self._thread.join(timeout=timeout)
                
                if self._thread and self._thread.is_alive():
                    logger.warning("Server thread did not stop gracefully")
            
            except Exception as e:
                logger.error(f"Error stopping server: {e}")
        
        self._started = False
        logger.info("Embedded server stopped")
    
    def is_running(self) -> bool:
        """Check if server is running."""
        return (
            self._started and
            self._thread is not None and
            self._thread.is_alive()
        )
    
    @property
    def base_url(self) -> str:
        """Get server base URL."""
        return f"http://{self.host}:{self.port}"


class ServerManager:
    """
    Singleton manager for the embedded server.
    
    Ensures only one server instance runs across the application.
    """
    
    _instance: Optional['ServerManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> 'ServerManager':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._server: Optional[EmbeddedServer] = None
        return cls._instance
    
    def start_server(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
    ) -> EmbeddedServer:
        """
        Start the embedded server (singleton).
        
        Args:
            host: Server bind address
            port: Server port
        
        Returns:
            EmbeddedServer instance
        """
        if self._server is None:
            self._server = EmbeddedServer(host=host, port=port)
            self._server.start()
        
        return self._server
    
    def stop_server(self) -> None:
        """Stop the embedded server."""
        if self._server:
            self._server.stop()
            self._server = None
    
    @property
    def server(self) -> Optional[EmbeddedServer]:
        """Get the current server instance."""
        return self._server
    
    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._server is not None and self._server.is_running()


def get_server_manager() -> ServerManager:
    """Get the ServerManager singleton."""
    return ServerManager()
