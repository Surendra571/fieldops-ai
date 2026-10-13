import logging
from typing import Any

from app.core.celery_app import celery_app
from app.core.database import db_manager
from app.repositories.outbox_repo import OutboxRepository
from app.services.outbox_service import OutboxService
from app.tasks.utils import run_async

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.outbox_tasks.process_outbox_batch_task", bind=True)
def process_outbox_batch_task(self, limit: int = 50) -> dict[str, Any]:
    """
    Celery task to poll and dispatch pending and retry-ready outbox events.
    """

    async def _process():
        repo = OutboxRepository(db_manager.get_database())
        service = OutboxService(repo)
        return await service.process_batch(limit=limit, worker_id=self.request.id)

    res = run_async(_process())
    logger.info(f"Outbox processing task {self.request.id} completed: {res}")
    return res
