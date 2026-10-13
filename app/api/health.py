import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health & Readiness"])


@router.get("/health", status_code=status.HTTP_200_OK)
@router.get("/health/live", status_code=status.HTTP_200_OK)
async def liveness_probe():
    """Liveness probe indicating application process is alive."""
    return {
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/ready", status_code=status.HTTP_200_OK)
@router.get("/health/ready", status_code=status.HTTP_200_OK)
async def readiness_probe(db: AsyncIOMotorDatabase = Depends(get_database)):
    """Readiness probe verifying database connectivity."""
    try:
        await db.command("ping")
        return {
            "status": "ready",
            "database": "connected",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        logger.error("Readiness check database ping failed: %s", str(e))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "message": "Database connectivity check failed.",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
