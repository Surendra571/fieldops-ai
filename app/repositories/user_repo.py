from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "users")

    async def get_by_email(self, email: str) -> dict[str, Any] | None:
        doc = await self.collection.find_one({"email": email.lower().strip()})
        return self._serialize_doc(doc)
