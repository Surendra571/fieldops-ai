import logging
from datetime import UTC, datetime

from app.core.celery_app import celery_app
from app.core.database import db_manager
from app.repositories.technician_repo import TechnicianRepository
from app.tasks.utils import run_async

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.maintenance_tasks.cleanup_expired_reservations_task")
def cleanup_expired_reservations_task() -> dict[str, int]:
    """
    Finds expired tentative holds (older than 10 mins) and removes them from technician calendars.
    """

    async def _cleanup():
        db = db_manager.get_database()
        tech_repo = TechnicianRepository(db)
        now = datetime.now(UTC)

        cursor = db["slot_reservations"].find(
            {"expires_at": {"$lt": now}, "status": {"$ne": "CONFIRMED"}}
        )
        cleaned = 0

        async for res in cursor:
            token = res["reservation_token"]
            tech_id = res["technician_id"]
            # Release hold from technician active bookings
            await tech_repo.remove_active_booking(tech_id, token)
            await db["slot_reservations"].delete_one({"_id": res["_id"]})
            cleaned += 1

        logger.info(f"Cleaned up {cleaned} expired tentative holds.")
        return {"expired_holds_cleaned": cleaned}

    return run_async(_cleanup())
