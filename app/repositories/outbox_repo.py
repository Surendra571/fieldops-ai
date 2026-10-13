import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import settings
from app.repositories.base import BaseRepository
from app.schemas.outbox import OutboxEventCreate, OutboxEventStatus


class OutboxRepository(BaseRepository):
    """
    Asynchronous repository for Transactional Outbox pattern.
    Guarantees reliable message staging, atomic locking, exponential backoff,
    and dead-letter queue management.
    """

    def __init__(self, db: Any):
        super().__init__(db, "outbox_events")

    async def stage_event(self, event_create: OutboxEventCreate) -> dict[str, Any]:
        """
        Stage an event in PENDING state. If an idempotency_key is provided
        and already exists, return the existing event.
        """
        now = datetime.now(UTC)
        if event_create.idempotency_key:
            existing = await self.collection.find_one(
                {"idempotency_key": event_create.idempotency_key}
            )
            if existing:
                return self._map_id(existing)

        event_id = str(uuid.uuid4())
        doc = {
            "event_id": event_id,
            "event_type": event_create.event_type.value,
            "aggregate_type": event_create.aggregate_type,
            "aggregate_id": event_create.aggregate_id,
            "payload": event_create.payload,
            "status": OutboxEventStatus.PENDING.value,
            "retry_count": 0,
            "max_retries": event_create.max_retries,
            "next_retry_at": now,
            "last_error": None,
            "external_reference_id": None,
            "correlation_id": event_create.correlation_id or str(uuid.uuid4()),
            "idempotency_key": event_create.idempotency_key,
            "created_at": now,
            "updated_at": now,
            "processed_at": None,
        }
        result = await self.collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return self._map_id(doc)

    async def fetch_batch_for_processing(
        self, limit: int = 50, worker_id: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Fetch pending or retry-ready events and atomically mark them IN_FLIGHT.
        """
        now = datetime.now(UTC)
        worker_tag = worker_id or f"worker_{uuid.uuid4().hex[:8]}"

        # Look for events that are PENDING or FAILED and due for retry
        # Also recover stuck IN_FLIGHT events older than 5 minutes (worker crash recovery)
        stuck_threshold = now - timedelta(minutes=5)
        query = {
            "$or": [
                {
                    "status": {
                        "$in": [OutboxEventStatus.PENDING.value, OutboxEventStatus.FAILED.value]
                    },
                    "next_retry_at": {"$lte": now},
                },
                {
                    "status": OutboxEventStatus.IN_FLIGHT.value,
                    "updated_at": {"$lte": stuck_threshold},
                },
            ]
        }

        # Find candidate ids first
        cursor = self.collection.find(query).sort("created_at", 1).limit(limit)
        candidates = await cursor.to_list(length=limit)

        locked_events = []
        for cand in candidates:
            # Atomically claim each event
            updated = await self.collection.find_one_and_update(
                {
                    "_id": cand["_id"],
                    "status": {
                        "$in": [
                            OutboxEventStatus.PENDING.value,
                            OutboxEventStatus.FAILED.value,
                            OutboxEventStatus.IN_FLIGHT.value,
                        ]
                    },
                },
                {
                    "$set": {
                        "status": OutboxEventStatus.IN_FLIGHT.value,
                        "locked_by": worker_tag,
                        "updated_at": now,
                    }
                },
                return_document=True,
            )
            if updated:
                locked_events.append(self._map_id(updated))

        return locked_events

    async def mark_completed(self, event_id: str, external_reference_id: str | None = None) -> bool:
        """Mark an event as successfully delivered (SENT)."""
        now = datetime.now(UTC)
        res = await self.collection.update_one(
            {"event_id": event_id},
            {
                "$set": {
                    "status": OutboxEventStatus.SENT.value,
                    "external_reference_id": external_reference_id,
                    "processed_at": now,
                    "updated_at": now,
                    "last_error": None,
                }
            },
        )
        return res.modified_count > 0

    async def mark_failed(
        self, event_id: str, error_message: str, current_retry_count: int, max_retries: int
    ) -> dict[str, Any]:
        """
        Record failure. Calculates exponential backoff with jitter.
        If retry_count + 1 >= max_retries, transitions to DEAD_LETTER.
        """
        now = datetime.now(UTC)
        new_retry_count = current_retry_count + 1

        if new_retry_count >= max_retries:
            new_status = OutboxEventStatus.DEAD_LETTER.value
            next_retry_at = now + timedelta(days=365)  # park indefinitely
        else:
            new_status = OutboxEventStatus.FAILED.value
            # Full jitter exponential backoff: backoff = min(max_backoff, base * 2^retry + jitter)
            base = settings.OUTBOX_BASE_BACKOFF_SECONDS
            max_backoff = settings.OUTBOX_MAX_BACKOFF_SECONDS
            exponential = min(max_backoff, base * (2**new_retry_count))
            jitter = random.uniform(0.1, 1.0)
            backoff_seconds = exponential + jitter
            next_retry_at = now + timedelta(seconds=backoff_seconds)

        updated = await self.collection.find_one_and_update(
            {"event_id": event_id},
            {
                "$set": {
                    "status": new_status,
                    "retry_count": new_retry_count,
                    "next_retry_at": next_retry_at,
                    "last_error": error_message,
                    "updated_at": now,
                }
            },
            return_document=True,
        )
        return self._map_id(updated) if updated else {}

    async def replay_dead_letter(self, event_id: str) -> dict[str, Any] | None:
        """
        Safely reset an event in DEAD_LETTER back to PENDING with retry_count=0.
        """
        now = datetime.now(UTC)
        updated = await self.collection.find_one_and_update(
            {"event_id": event_id, "status": OutboxEventStatus.DEAD_LETTER.value},
            {
                "$set": {
                    "status": OutboxEventStatus.PENDING.value,
                    "retry_count": 0,
                    "next_retry_at": now,
                    "last_error": None,
                    "updated_at": now,
                }
            },
            return_document=True,
        )
        return self._map_id(updated) if updated else None

    async def get_metrics(self) -> dict[str, int]:
        """Calculate counts for each outbox status."""
        pipeline = [
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        counts: dict[str, int] = {
            "total_events": 0,
            "PENDING": 0,
            "IN_FLIGHT": 0,
            "SENT": 0,
            "FAILED": 0,
            "DEAD_LETTER": 0,
        }
        cursor = self.collection.aggregate(pipeline)
        async for doc in cursor:
            st = doc.get("_id")
            ct = doc.get("count", 0)
            if st in counts:
                counts[st] = ct
            counts["total_events"] += ct

        return {
            "total_events": counts["total_events"],
            "pending": counts["PENDING"],
            "in_flight": counts["IN_FLIGHT"],
            "sent": counts["SENT"],
            "failed": counts["FAILED"],
            "dead_letter": counts["DEAD_LETTER"],
        }
