from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class AppointmentRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "appointments")

    async def get_by_appointment_number(self, appt_number: str) -> dict[str, Any] | None:
        doc = await self.collection.find_one({"appointment_number": appt_number})
        return self._serialize_doc(doc)

    async def get_by_work_order_id(self, work_order_id: str) -> dict[str, Any] | None:
        doc = await self.collection.find_one({"work_order_id": work_order_id})
        return self._serialize_doc(doc)

    async def get_by_reservation_token(self, reservation_token: str) -> dict[str, Any] | None:
        doc = await self.collection.find_one({"reservation_token": reservation_token})
        return self._serialize_doc(doc)

    async def update_with_lock(
        self,
        appointment_id: str,
        current_lock_version: int,
        update_data: dict[str, Any],
    ) -> dict[str, Any] | None:
        query_id = self._to_object_id(appointment_id)
        update_doc = {**update_data, "updated_at": datetime.now(UTC)}
        result = await self.collection.find_one_and_update(
            {"_id": query_id, "lock_version": current_lock_version},
            {"$set": update_doc},
            return_document=True,
        )
        return self._serialize_doc(result)

    async def check_conflicts(
        self,
        technician_id: str,
        scheduled_start: datetime,
        scheduled_end: datetime,
        exclude_appointment_id: str | None = None,
    ) -> bool:
        """
        Check if there are any non-cancelled appointments overlapping the requested time window
        for the given technician.
        Condition for overlap: (existing_start < new_end) and (existing_end > new_start)
        """
        query: dict[str, Any] = {
            "technician_id": technician_id,
            "status": {"$in": ["TENTATIVE_HOLD", "CONFIRMED", "EN_ROUTE", "ON_SITE"]},
            "scheduled_start": {"$lt": scheduled_end},
            "scheduled_end": {"$gt": scheduled_start},
        }
        if exclude_appointment_id:
            query["_id"] = {"$ne": self._to_object_id(exclude_appointment_id)}

        count = await self.collection.count_documents(query)
        return count > 0

    async def find_appointments_for_technician(
        self,
        technician_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        query = {
            "technician_id": technician_id,
            "status": {"$ne": "CANCELLED"},
            "scheduled_start": {"$gte": start_date, "$lte": end_date},
        }
        cursor = self.collection.find(query).sort("scheduled_start", 1)
        items = []
        async for doc in cursor:
            serialized = self._serialize_doc(doc)
            if serialized:
                items.append(serialized)
        return items
