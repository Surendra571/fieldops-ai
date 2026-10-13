from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class WorkOrderRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "work_orders")

    async def get_by_work_order_number(self, wo_number: str) -> dict[str, Any] | None:
        doc = await self.collection.find_one({"work_order_number": wo_number})
        return self._serialize_doc(doc)

    async def get_by_idempotency_key(self, key: str) -> dict[str, Any] | None:
        doc = await self.collection.find_one({"idempotency_key": key})
        return self._serialize_doc(doc)

    async def append_audit_transition(
        self,
        work_order_id: str,
        from_status: str,
        to_status: str,
        actor: str,
        reason: str | None = None,
    ) -> dict[str, Any] | None:
        query_id = self._to_object_id(work_order_id)
        now = datetime.now(UTC)
        transition = {
            "transition_id": f"tr_{int(now.timestamp() * 1000)}",
            "from_status": from_status,
            "to_status": to_status,
            "actor": actor,
            "timestamp": now,
            "reason": reason,
        }

        result = await self.collection.find_one_and_update(
            {"_id": query_id},
            {
                "$set": {"status": to_status, "updated_at": now},
                "$push": {"audit_trail": transition},
            },
            return_document=True,
        )
        return self._serialize_doc(result)

    async def search(
        self,
        search_term: str,
        base_filter: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        regex_query = {"$regex": search_term, "$options": "i"}
        search_clause = {
            "$or": [
                {"work_order_number": regex_query},
                {"description": regex_query},
                {"symptoms": regex_query},
                {"service_address.street": regex_query},
                {"service_address.city": regex_query},
                {"service_address.postal_code": regex_query},
            ]
        }
        if base_filter:
            final_query = {"$and": [base_filter, search_clause]}
        else:
            final_query = search_clause
        return await self.get_many(final_query, skip=skip, limit=limit)
