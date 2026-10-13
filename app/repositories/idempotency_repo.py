import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.repositories.base import BaseRepository


class IdempotencyRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "idempotency_records")

    @staticmethod
    def compute_request_hash(data: Any) -> str:
        """Compute canonical SHA256 fingerprint for request payload."""
        if data is None:
            serialized = "null"
        elif isinstance(data, (dict, list)):
            serialized = json.dumps(data, sort_keys=True, default=str)
        else:
            serialized = str(data)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    async def get_record(self, key: str, scope: str) -> dict[str, Any] | None:
        doc = await self.collection.find_one({"key": key, "scope": scope})
        return self._serialize_doc(doc)

    async def acquire(
        self, key: str, scope: str, request_hash: str, ttl_hours: int = 24
    ) -> tuple[bool, dict[str, Any] | None]:
        """
        Attempts to acquire an idempotency lock atomically.
        Returns:
            (True, None) if lock successfully acquired as PENDING.
            (False, existing_record) if key already exists (in progress or completed).
        """
        now = datetime.now(UTC)
        expires_at = now + timedelta(hours=ttl_hours)

        record = {
            "key": key,
            "scope": scope,
            "request_hash": request_hash,
            "status": "PENDING",
            "response_code": None,
            "response_body": None,
            "created_at": now,
            "expires_at": expires_at,
        }

        try:
            await self.collection.insert_one(record)
            return True, None
        except DuplicateKeyError:
            # Key collision: load existing record
            existing = await self.get_record(key, scope)
            return False, existing

    async def commit(
        self, key: str, scope: str, response_code: int, response_body: dict[str, Any]
    ) -> None:
        """Mark idempotency record as COMPLETED with cached response."""
        now = datetime.now(UTC)
        await self.collection.update_one(
            {"key": key, "scope": scope},
            {
                "$set": {
                    "status": "COMPLETED",
                    "response_code": response_code,
                    "response_body": response_body,
                    "updated_at": now,
                }
            },
        )

    async def release(self, key: str, scope: str) -> None:
        """Release a PENDING lock when an operation fails so retries are permitted."""
        await self.collection.delete_one({"key": key, "scope": scope, "status": "PENDING"})
