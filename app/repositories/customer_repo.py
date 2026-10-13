from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "customers")

    async def get_by_phone(self, phone: str) -> dict[str, Any] | None:
        clean_phone = phone.strip()
        doc = await self.collection.find_one({"phone": clean_phone})
        return self._serialize_doc(doc)

    async def get_by_user_id(self, user_id: str) -> dict[str, Any] | None:
        doc = await self.collection.find_one({"user_id": user_id})
        return self._serialize_doc(doc)

    async def search(
        self, query_str: str, skip: int = 0, limit: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        regex_query = {"$regex": query_str, "$options": "i"}
        filter_query = {
            "$or": [
                {"full_name": regex_query},
                {"phone": regex_query},
                {"email": regex_query},
            ]
        }
        return await self.get_many(filter_query, skip=skip, limit=limit)
