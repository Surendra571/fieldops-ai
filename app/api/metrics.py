from datetime import UTC, datetime

from fastapi import APIRouter

from app.core.config import settings
from app.core.middleware import metrics_collector

router = APIRouter(tags=["Metrics & Observability"])
_START_TIME = datetime.now(UTC)


@router.get("/metrics")
async def get_metrics():
    """
    Exposes real-time system metrics, latency percentiles, request volume,
    and error rates for observability and performance evaluation.
    """
    summary = metrics_collector.get_summary()
    uptime_seconds = (datetime.now(UTC) - _START_TIME).total_seconds()

    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": round(uptime_seconds, 1),
        "timestamp": datetime.now(UTC).isoformat(),
        "metrics": summary,
    }
