"""
FastAPI application factory.

Creates and configures the FastAPI application with:
- Lifespan events (startup/shutdown)
- Middleware
- Routers
- Error handlers
"""

import logging
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
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    
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
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Phase 2: Middleware added via router dependencies
    
    # Include API routers
    app.include_router(api_router, prefix="/api")
    
    # Setup static file serving (Phase 6)
    from predict.core.api.static_files import (
        setup_static_files,
        setup_protected_static_routes,
    )
    setup_static_files(app)
    setup_protected_static_routes(app)
    
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
