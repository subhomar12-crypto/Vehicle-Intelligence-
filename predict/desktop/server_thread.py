"""
Embedded server thread for desktop mode.

Runs FastAPI server in a background thread with proper
lifecycle management for PySide6 GUI integration.
Includes Cloudflare tunnel management for going live.
"""

import logging
import asyncio
import shutil
import socket
import subprocess
import threading
import time
from typing import Optional

import uvicorn
from uvicorn.config import Config as UvicornConfig

from predict.core.api.app import create_app

logger = logging.getLogger(__name__)


class CloudflareTunnel:
    """
    Manages a cloudflared tunnel subprocess.

    Starts/stops 'cloudflared tunnel run <name>' to expose the
    local server to the internet via Cloudflare.
    """

    def __init__(self, tunnel_name: str = "predict-tunnel"):
        self.tunnel_name = tunnel_name
        self._process: Optional[subprocess.Popen] = None
        self._cloudflared_path = shutil.which("cloudflared")

    @property
    def is_available(self) -> bool:
        """Check if cloudflared binary is installed."""
        return self._cloudflared_path is not None

    @property
    def is_running(self) -> bool:
        """Check if the tunnel process is alive."""
        return self._process is not None and self._process.poll() is None

    def start(self) -> bool:
        """
        Start the Cloudflare tunnel.

        Returns:
            True if started successfully, False otherwise.
        """
        if self.is_running:
            logger.warning("Cloudflare tunnel already running")
            return True

        if not self.is_available:
            logger.warning("cloudflared not found in PATH")
            return False

        try:
            self._process = subprocess.Popen(
                [self._cloudflared_path, "tunnel", "run", self.tunnel_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            logger.info(
                f"Cloudflare tunnel '{self.tunnel_name}' started (PID {self._process.pid})"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to start Cloudflare tunnel: {e}")
            self._process = None
            return False

    def stop(self, timeout: float = 5) -> None:
        """Stop the Cloudflare tunnel process."""
        if not self.is_running:
            return

        logger.info("Stopping Cloudflare tunnel...")
        try:
            self._process.terminate()
            try:
                self._process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=2)
            logger.info("Cloudflare tunnel stopped")
        except Exception as e:
            logger.error(f"Error stopping Cloudflare tunnel: {e}")
        finally:
            self._process = None


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
    
    def _port_in_use(self) -> bool:
        """Check if the port is already in use by another process."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("127.0.0.1", self.port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def start(self) -> None:
        """Start the embedded server in a background thread."""
        if self._started:
            logger.warning("Server already started")
            return

        # Check if port is already occupied by another process
        if self._port_in_use():
            logger.warning(
                f"Port {self.port} already in use — assuming external server is running"
            )
            self._started = True
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
        Falls back to force-killing the process on the port if needed.

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

        # Force-kill any process still on the port (covers external/orphaned servers)
        self._force_kill_port()

        self._started = False
        logger.info("Embedded server stopped")

    def _force_kill_port(self) -> None:
        """Kill any process listening on self.port."""
        import sys
        if sys.platform == "win32":
            try:
                result = subprocess.run(
                    ["netstat", "-ano"],
                    capture_output=True, text=True, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                for line in result.stdout.splitlines():
                    if f":{self.port}" in line and "LISTENING" in line:
                        parts = line.split()
                        pid = int(parts[-1])
                        if pid > 0:
                            logger.info(f"Force-killing server process PID {pid} on port {self.port}")
                            subprocess.run(
                                ["taskkill", "/F", "/PID", str(pid)],
                                capture_output=True, timeout=5,
                                creationflags=subprocess.CREATE_NO_WINDOW,
                            )
            except Exception as e:
                logger.warning(f"Could not force-kill port {self.port}: {e}")
        else:
            try:
                result = subprocess.run(
                    ["lsof", "-ti", f":{self.port}"],
                    capture_output=True, text=True, timeout=5,
                )
                for pid_str in result.stdout.strip().splitlines():
                    pid = int(pid_str)
                    if pid > 0:
                        logger.info(f"Force-killing server process PID {pid} on port {self.port}")
                        import signal
                        import os
                        os.kill(pid, signal.SIGKILL)
            except Exception as e:
                logger.warning(f"Could not force-kill port {self.port}: {e}")
    
    def is_running(self) -> bool:
        """Check if server is running (own thread or external server)."""
        if not self._started:
            return False
        # External server mode: port was in use, no thread started
        if self._thread is None:
            return self._port_in_use()
        return self._thread.is_alive()
    
    @property
    def base_url(self) -> str:
        """Get server base URL (uses 127.0.0.1 for client access when bound to 0.0.0.0)."""
        host = "127.0.0.1" if self.host == "0.0.0.0" else self.host
        return f"http://{host}:{self.port}"


class ServerManager:
    """
    Singleton manager for the embedded server and Cloudflare tunnel.

    Ensures only one server instance runs across the application.
    When the server starts, the Cloudflare tunnel is also started
    to make the server accessible online.
    """

    _instance: Optional['ServerManager'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'ServerManager':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._server: Optional[EmbeddedServer] = None
                    cls._instance._tunnel = CloudflareTunnel()
        return cls._instance

    def start_server(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
    ) -> EmbeddedServer:
        """
        Start the embedded server and Cloudflare tunnel.

        Args:
            host: Server bind address
            port: Server port

        Returns:
            EmbeddedServer instance
        """
        if self._server is None:
            self._server = EmbeddedServer(host=host, port=port)
            self._server.start()

        # Start Cloudflare tunnel after server is ready
        if self._tunnel.is_available and not self._tunnel.is_running:
            self._tunnel.start()

        return self._server

    def stop_server(self) -> None:
        """Stop the embedded server and Cloudflare tunnel."""
        # Stop tunnel first
        if self._tunnel.is_running:
            self._tunnel.stop()

        if self._server:
            self._server.stop()
            self._server = None

    @property
    def server(self) -> Optional[EmbeddedServer]:
        """Get the current server instance."""
        return self._server

    @property
    def tunnel(self) -> CloudflareTunnel:
        """Get the Cloudflare tunnel instance."""
        return self._tunnel

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._server is not None and self._server.is_running()

    @property
    def is_live(self) -> bool:
        """Check if server is running AND tunnel is connected."""
        return self.is_running and self._tunnel.is_running


def get_server_manager() -> ServerManager:
    """Get the ServerManager singleton."""
    return ServerManager()
