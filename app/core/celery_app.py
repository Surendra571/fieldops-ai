from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "fieldops_celery",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    # Celery Beat Periodic Schedule
    beat_schedule={
        "process-outbox-events-periodic": {
            "task": "app.tasks.outbox_tasks.process_outbox_batch_task",
            "schedule": 10.0,  # every 10 seconds
            "options": {"queue": "outbox"},
        },
        "check-upcoming-reminders-periodic": {
            "task": "app.tasks.notification_tasks.check_upcoming_appointment_reminders_task",
            "schedule": 900.0,  # every 15 minutes
            "options": {"queue": "notifications"},
        },
        "cleanup-expired-holds-periodic": {
            "task": "app.tasks.maintenance_tasks.cleanup_expired_reservations_task",
            "schedule": 300.0,  # every 5 minutes
            "options": {"queue": "maintenance"},
        },
    },
)

# Auto-discover tasks across app.tasks modules
celery_app.autodiscover_tasks(["app.tasks"])
