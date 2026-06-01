"""
FastAPI application factory.

Creates and configures the FastAPI application with:
- Lifespan events (startup/shutdown)
- Middleware
- Routers
- Error handlers
"""

import os
# Suppress TensorFlow noise before any TF import
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")  # suppress INFO/WARNING
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")  # suppress oneDNN message

import logging
import threading
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from predict.core.version import APP_VERSION, APP_NAME
from predict.core.config import get_config
from predict.core.db.engine import init_engine, close_engine
from predict.core.middleware.error_handler import setup_error_handlers
from predict.core.api.v1.router import api_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {APP_NAME} v{APP_VERSION}")
    
    config = get_config()
    
    # Initialize database
    try:
        init_engine(config.DATABASE_URL)
        logger.info("Database engine initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    # Phase 4: Initialize Redis (lazy init on first use)
    # Phase 5: ARQ worker runs separately

    # Preload LLM model in background thread (avoids blocking server startup)
    def _preload_llm():
        try:
            from predict.core.ai.llm.assistant import get_llm_assistant
            assistant = get_llm_assistant()
            if not assistant.is_loaded:
                logger.info("Preloading LLM model in background thread...")
                assistant.load_model("qwen")
            if assistant.is_available():
                logger.info("LLM model preloaded successfully")
            else:
                logger.warning("LLM model not available (file may be missing)")
        except Exception as e:
            logger.warning(f"LLM preload failed (non-critical): {e}")

    threading.Thread(target=_preload_llm, daemon=True, name="llm-preload").start()

    # Start tier expiry background task
    from predict.core.tasks.tier_expiry import start_expiry_task
    start_expiry_task()
    logger.info("Tier expiry task started")

    # Start APScheduler (periodic jobs)
    try:
        from predict.core.jobs.scheduler import setup_scheduler
        setup_scheduler()
    except Exception as e:
        logger.warning("APScheduler startup failed (non-critical): %s", e)

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down application...")

    # Stop tier expiry task
    from predict.core.tasks.tier_expiry import stop_expiry_task
    stop_expiry_task()

    # Stop APScheduler
    try:
        from predict.core.jobs.scheduler import shutdown_scheduler
        shutdown_scheduler()
    except Exception:
        pass

    # Close database connections
    await close_engine()
    logger.info("Database engine closed")

    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Returns:
        Configured FastAPI app
    """
    config = get_config()
    
    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        description="PREDICT - Vehicle Intelligence Platform API",
        docs_url="/docs" if config.debug else None,
        redoc_url="/redoc" if config.debug else None,
        openapi_url="/openapi.json" if config.debug else None,
        lifespan=lifespan,
    )
    
    # Setup error handlers
    setup_error_handlers(app)
    
    # Add security headers middleware (must be added before CORS so it wraps responses)
    from predict.core.middleware.security_headers import SecurityHeadersMiddleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API routers
    app.include_router(api_router, prefix="/api")

    # Legacy Android auth routes at /auth/* (Android calls without /api/ prefix)
    from predict.core.api.v1.auth import app_legacy_router
    app.include_router(app_legacy_router, prefix="/auth", tags=["legacy-auth"])

    # Legacy vehicle_data routes (routes already have /api/ in their paths)
    from predict.core.api.v1 import vehicle_data as _vd
    app.include_router(_vd.legacy_router, tags=["legacy-vehicle-data"])
    
    # Setup static file serving (Phase 6)
    from predict.core.api.static_files import (
        setup_static_files,
        setup_protected_static_routes,
        setup_tile_server,
    )
    setup_static_files(app)
    setup_protected_static_routes(app)
    setup_tile_server(app)
    
    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "name": APP_NAME,
            "version": APP_VERSION,
            "status": "operational",
            "docs": "/docs",
        }
    
    # Health check endpoints
    @app.get("/health")
    async def health():
        return {"status": "healthy"}
    
    @app.get("/health/ready")
    async def health_ready():
        """Detailed health check for Kubernetes/liveness probes."""
        # TODO Phase 7: Check DB, Redis, ARQ
        return {
            "status": "ready",
            "checks": {
                "database": "ok",
                "redis": "ok",
            },
        }
    
    return app


# Module-level instance for `uvicorn predict.core.api.app:app`
app = create_app()
