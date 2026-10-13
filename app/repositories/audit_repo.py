from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class AuditRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "audit_events")

    async def log_event(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        actor_id: str | None = None,
        actor_role: str | None = None,
        changes: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        doc = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "actor_id": actor_id,
            "actor_role": actor_role,
            "changes": changes or {},
            "metadata": metadata or {},
            "timestamp": datetime.now(UTC),
        }
        return await self.create(doc)

    async def get_events_for_entity(
        self, entity_type: str, entity_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        query = {"entity_type": entity_type, "entity_id": entity_id}
        items, _ = await self.get_many(query, limit=limit, sort_field="timestamp", sort_order=-1)
        return items
