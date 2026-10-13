import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.database import close_mongo_connection, connect_to_mongo
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import (
    RateLimiterMiddleware,
    RequestIdMiddleware,
    RequestLatencyMiddleware,
)
from app.scripts.init_db import init_indexes

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    setup_logging(
        level="DEBUG" if settings.DEBUG else "INFO",
        log_format=settings.LOG_FORMAT,
    )
    logger.info("Starting up %s (Environment: %s)...", settings.PROJECT_NAME, settings.ENVIRONMENT)
    try:
        await connect_to_mongo()
        # Initialize indexes on startup
        from app.core.database import db_manager

        if db_manager.db is not None:
            await init_indexes(db_manager.db)
    except Exception as e:
        logger.warning(
            "Database connection failed during startup (will retry on readiness check): %s",
            str(e),
        )

    yield

    # --- Shutdown ---
    logger.info("Shutting down %s...", settings.PROJECT_NAME)
    await close_mongo_connection()


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        description="FieldOps AI — Production-Minded Voice-Based Field Service Management Platform",
        lifespan=lifespan,
        docs_url="/docs" if settings.DEBUG or settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.DEBUG or settings.ENVIRONMENT != "production" else None,
        openapi_url="/openapi.json"
        if settings.DEBUG or settings.ENVIRONMENT != "production"
        else None,
    )

    # Global Observability & Protection Middlewares (executed in reverse registration order)
    # 1. Rate Limiting (evaluated first)
    app.add_middleware(RateLimiterMiddleware)
    # 2. Latency Measurement & Access Logging
    app.add_middleware(RequestLatencyMiddleware)
    # 3. Request Correlation ID
    app.add_middleware(RequestIdMiddleware)

    # 4. CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register standardized RFC 7807 error envelopes
    register_exception_handlers(app)

    # Health, readiness, and metrics probes
    app.include_router(health_router, prefix=settings.API_V1_STR)
    app.include_router(health_router)  # root /health and /ready for container runners
    app.include_router(metrics_router, prefix=settings.API_V1_STR)
    app.include_router(metrics_router)  # root /metrics for Prometheus scrapers

    # Core API v1 routes
    app.include_router(api_v1_router, prefix=settings.API_V1_STR)

    return app


app = create_application()
