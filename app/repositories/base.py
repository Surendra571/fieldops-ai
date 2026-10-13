from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase


class BaseRepository:
    """
    Base asynchronous MongoDB repository providing clean CRUD, pagination,
    and automatic ID/ObjectId serialization.
    """

    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str):
        self.db = db
        self.collection_name = collection_name
        self.collection: AsyncIOMotorCollection = db[collection_name]

    @staticmethod
    def _to_object_id(id_str: str) -> ObjectId | str:
        """Convert string to ObjectId if valid, else keep string."""
        if ObjectId.is_valid(id_str):
            return ObjectId(id_str)
        return id_str

    @staticmethod
    def _serialize_doc(doc: dict[str, Any] | None) -> dict[str, Any] | None:
        """Serialize a MongoDB document converting _id to id string."""
        if not doc:
            return None
        res = dict(doc)
        if "_id" in res:
            res["id"] = str(res["_id"])
            del res["_id"]
        return res

    _map_id = _serialize_doc

    async def create(self, doc_data: dict[str, Any]) -> dict[str, Any]:
        """Insert a document with created_at and updated_at timestamps."""
        now = datetime.now(UTC)
        to_insert = dict(doc_data)
        to_insert.setdefault("created_at", now)
        to_insert.setdefault("updated_at", now)

        result = await self.collection.insert_one(to_insert)
        to_insert["_id"] = result.inserted_id
        return self._serialize_doc(to_insert)  # type: ignore

    async def get_by_id(self, id_str: str) -> dict[str, Any] | None:
        """Retrieve a document by ID."""
        query_id = self._to_object_id(id_str)
        doc = await self.collection.find_one({"_id": query_id})
        return self._serialize_doc(doc)

    async def get_many(
        self,
        filter_query: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 20,
        sort_field: str = "created_at",
        sort_order: int = -1,
    ) -> tuple[list[dict[str, Any]], int]:
        """Retrieve paginated documents matching a filter."""
        query = filter_query or {}
        total = await self.collection.count_documents(query)
        cursor = self.collection.find(query).sort(sort_field, sort_order).skip(skip).limit(limit)
        items = []
        async for doc in cursor:
            serialized = self._serialize_doc(doc)
            if serialized:
                items.append(serialized)
        return items, total

    async def update(self, id_str: str, update_data: dict[str, Any]) -> dict[str, Any] | None:
        """Update a document and touch updated_at."""
        query_id = self._to_object_id(id_str)
        to_set = dict(update_data)
        to_set["updated_at"] = datetime.now(UTC)

        # Do not allow modifying id or _id directly
        to_set.pop("_id", None)
        to_set.pop("id", None)

        result = await self.collection.find_one_and_update(
            {"_id": query_id},
            {"$set": to_set},
            return_document=True,
        )
        return self._serialize_doc(result)

    async def delete(self, id_str: str) -> bool:
        """Delete a document by ID."""
        query_id = self._to_object_id(id_str)
        result = await self.collection.delete_one({"_id": query_id})
        return result.deleted_count > 0
