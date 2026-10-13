from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_active_user, get_db, require_roles
from app.core.config import settings
from app.repositories.outbox_repo import OutboxRepository
from app.schemas.outbox import OutboxMetricsResponse
from app.schemas.user import UserRole
from app.services.outbox_service import OutboxService, metrics_tracker

router = APIRouter(prefix="/integrations", tags=["Integrations"])


@router.get(
    "/status",
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER))],
)
async def get_integrations_status():
    """
    Returns the configured providers for external adapters and connection health.
    """
    return {
        "notification_provider": settings.NOTIFICATION_PROVIDER,
        "maps_provider": settings.MAPS_PROVIDER,
        "calendar_provider": settings.CALENDAR_PROVIDER,
        "crm_provider": settings.CRM_PROVIDER,
        "outbox_retries_max": settings.OUTBOX_MAX_RETRIES,
        "has_twilio_creds": bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN),
        "has_sendgrid_creds": bool(settings.SENDGRID_API_KEY),
    }


@router.get(
    "/metrics",
    response_model=OutboxMetricsResponse,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN))],
)
@router.get(
    "/outbox/metrics",
    response_model=OutboxMetricsResponse,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN))],
)
async def get_integrations_metrics(
    db: Any = Depends(get_db),
):
    """
    Operational metrics for outbox pipeline, delivery counts, retries, and dead-letter queue.
    """
    repo = OutboxRepository(db)
    counts = await repo.get_metrics()
    stats = metrics_tracker.get_stats()

    return OutboxMetricsResponse(
        total_events=counts["total_events"],
        pending=counts["pending"],
        in_flight=counts["in_flight"],
        sent=counts["sent"],
        failed=counts["failed"],
        dead_letter=counts["dead_letter"],
        notifications_sent_total=stats["notifications_sent_total"],
        notifications_failed_total=stats["notifications_failed_total"],
        notifications_retried_total=stats["notifications_retried_total"],
    )


@router.get("/outbox/dead-letter")
async def list_dead_letter_events(
    db: Any = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    current_user: Any = Depends(get_current_active_user),
):
    """
    Lists permanently failed outbox events in DEAD_LETTER status for dispatcher/admin inspection.
    """
    if current_user.role not in (UserRole.ADMIN.value, UserRole.DISPATCHER.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators and dispatchers can inspect the dead-letter queue.",
        )

    repo = OutboxRepository(db)
    cursor = repo.collection.find({"status": "DEAD_LETTER"}).sort("updated_at", -1).limit(limit)
    items = await cursor.to_list(length=limit)
    return [repo._map_id(item) for item in items]


@router.post("/outbox/replay/{event_id}")
async def replay_dead_letter_event(
    event_id: str,
    db: Any = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
):
    """
    Safely reset a DEAD_LETTER event back to PENDING with retry_count=0.
    """
    if current_user.role not in (UserRole.ADMIN.value, UserRole.DISPATCHER.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators and dispatchers can replay dead-letter events.",
        )

    repo = OutboxRepository(db)
    replayed = await repo.replay_dead_letter(event_id)
    if not replayed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dead-letter event '{event_id}' not found.",
        )
    return {"status": "replayed", "event": replayed}


@router.post(
    "/outbox/process",
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER))],
)
async def trigger_outbox_processing(
    db: Any = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    current_user: Any = Depends(get_current_active_user),
):
    """
    Manually trigger outbox batch processing (can be invoked by webhook, cron, or dev script).
    """
    repo = OutboxRepository(db)
    service = OutboxService(repo)
    result = await service.process_batch(limit=limit, worker_id=f"manual_{current_user.id}")
    return result
