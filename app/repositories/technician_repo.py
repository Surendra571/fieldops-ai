from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class TechnicianRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "technicians")

    async def get_by_user_id(self, user_id: str) -> dict[str, Any] | None:
        doc = await self.collection.find_one({"user_id": user_id})
        return self._serialize_doc(doc)

    async def find_active(self, required_skills: list[str] | None = None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"status": "ACTIVE"}
        if required_skills:
            query["skills"] = {"$all": required_skills}

        cursor = self.collection.find(query)
        items = []
        async for doc in cursor:
            serialized = self._serialize_doc(doc)
            if serialized:
                items.append(serialized)
        return items

    async def update_location(
        self,
        technician_id: str,
        coordinates: list[float],
        heading: float | None = None,
        speed_kph: float | None = None,
        battery_level: float | None = None,
    ) -> dict[str, Any] | None:
        query_id = self._to_object_id(technician_id)
        now = datetime.now(UTC)
        location_doc = {
            "type": "Point",
            "coordinates": coordinates,
            "updated_at": now,
        }
        if heading is not None:
            location_doc["heading"] = heading
        if speed_kph is not None:
            location_doc["speed_kph"] = speed_kph
        if battery_level is not None:
            location_doc["battery_level"] = battery_level

        result = await self.collection.find_one_and_update(
            {"_id": query_id},
            {
                "$set": {
                    "current_location": location_doc,
                    "updated_at": now,
                }
            },
            return_document=True,
        )
        return self._serialize_doc(result)

    async def add_active_booking_atomic(
        self,
        technician_id: str,
        booking_id: str,
        start_time: datetime,
        end_time: datetime,
        status: str = "CONFIRMED",
        buffer_minutes: int = 30,
    ) -> bool:
        """
        Database-enforced atomic slot reservation in MongoDB.
        Uses conditional $not: {$elemMatch: ...} to guarantee no overlapping booking
        exists in a single serialized document-level atomic mutation.
        """
        from datetime import timedelta

        query_id = self._to_object_id(technician_id)
        start_buf = start_time - timedelta(minutes=buffer_minutes)
        end_buf = end_time + timedelta(minutes=buffer_minutes)

        result = await self.collection.find_one_and_update(
            {
                "_id": query_id,
                "status": "ACTIVE",
                "active_bookings": {
                    "$not": {
                        "$elemMatch": {
                            "status": {
                                "$in": ["CONFIRMED", "TENTATIVE_HOLD", "EN_ROUTE", "ON_SITE"]
                            },
                            "start": {"$lt": end_buf},
                            "end": {"$gt": start_buf},
                        }
                    }
                },
            },
            {
                "$push": {
                    "active_bookings": {
                        "booking_id": booking_id,
                        "start": start_time,
                        "end": end_time,
                        "status": status,
                    }
                }
            },
            return_document=True,
        )
        return result is not None

    async def remove_active_booking(self, technician_id: str, booking_id: str) -> bool:
        """Atomically remove an active booking from technician calendar."""
        query_id = self._to_object_id(technician_id)
        result = await self.collection.update_one(
            {"_id": query_id},
            {"$pull": {"active_bookings": {"booking_id": booking_id}}},
        )
        if result.modified_count == 0:
            result = await self.collection.update_one(
                {"_id": query_id},
                {"$pull": {"active_bookings": {"appointment_id": booking_id}}},
            )
        return result.modified_count > 0
