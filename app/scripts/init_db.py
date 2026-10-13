import asyncio
import logging

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

logger = logging.getLogger(__name__)


async def init_indexes(db: AsyncIOMotorDatabase) -> None:
    """
    Creates necessary MongoDB indexes for performance, geospatial querying,
    and data integrity constraints.
    """
    logger.info("Initializing MongoDB indexes...")

    # Users
    await db["users"].create_index([("email", ASCENDING)], unique=True)

    # Customers
    await db["customers"].create_index([("phone", ASCENDING)], unique=True)
    await db["customers"].create_index([("email", ASCENDING)], sparse=True)
    await db["customers"].create_index([("user_id", ASCENDING)], sparse=True)

    # Technicians
    await db["technicians"].create_index([("current_location", "2dsphere")])
    await db["technicians"].create_index([("home_base", "2dsphere")])
    await db["technicians"].create_index([("skills", ASCENDING), ("status", ASCENDING)])
    await db["technicians"].create_index([("user_id", ASCENDING)], sparse=True)

    # Work Orders
    await db["work_orders"].create_index([("work_order_number", ASCENDING)], unique=True)
    await db["work_orders"].create_index([("customer_id", ASCENDING), ("created_at", DESCENDING)])
    await db["work_orders"].create_index([("status", ASCENDING), ("priority", ASCENDING)])
    await db["work_orders"].create_index(
        [("idempotency_key", ASCENDING)],
        unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )

    # Appointments
    await db["appointments"].create_index([("appointment_number", ASCENDING)], unique=True)
    await db["appointments"].create_index(
        [("technician_id", ASCENDING), ("scheduled_start", ASCENDING), ("status", ASCENDING)]
    )
    await db["appointments"].create_index([("work_order_id", ASCENDING)])
    await db["appointments"].create_index([("customer_id", ASCENDING)])
    await db["appointments"].create_index(
        [("reservation_token", ASCENDING)], unique=True, sparse=True
    )

    # Audit Events
    await db["audit_events"].create_index(
        [("entity_type", ASCENDING), ("entity_id", ASCENDING), ("timestamp", DESCENDING)]
    )

    # Idempotency Records
    await db["idempotency_records"].create_index(
        [("key", ASCENDING), ("scope", ASCENDING)], unique=True
    )
    await db["idempotency_records"].create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)

    # Slot Reservations (Ephemeral holds)
    await db["slot_reservations"].create_index([("reservation_token", ASCENDING)], unique=True)
    await db["slot_reservations"].create_index(
        [("technician_id", ASCENDING), ("scheduled_start", ASCENDING)]
    )
    await db["slot_reservations"].create_index(
        [("status", ASCENDING), ("claim_expires_at", ASCENDING)]
    )
    await db["slot_reservations"].create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)

    # Outbox Events (Transactional Outbox)
    await db["outbox_events"].create_index([("event_id", ASCENDING)], unique=True)
    await db["outbox_events"].create_index([("status", ASCENDING), ("next_retry_at", ASCENDING)])
    await db["outbox_events"].create_index(
        [("idempotency_key", ASCENDING)], unique=True, sparse=True
    )
    await db["outbox_events"].create_index(
        [("aggregate_type", ASCENDING), ("aggregate_id", ASCENDING)]
    )

    # Webhook Events (Deduplication)
    await db["webhook_events"].create_index(
        [("webhook_id", ASCENDING), ("provider", ASCENDING)], unique=True
    )
    await db["webhook_events"].create_index([("processed_at", DESCENDING)])

    # Conversation Sessions (Agent history and context)
    await db["conversation_sessions"].create_index([("session_id", ASCENDING)], unique=True)
    await db["conversation_sessions"].create_index([("customer_id", ASCENDING)], sparse=True)
    await db["conversation_sessions"].create_index([("updated_at", DESCENDING)])

    logger.info("MongoDB indexes successfully initialized.")


async def main():
    from motor.motor_asyncio import AsyncIOMotorClient

    from app.core.config import settings

    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DB_NAME]
    await init_indexes(db)
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
