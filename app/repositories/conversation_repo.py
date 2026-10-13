from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository):
    """
    Repository for managing customer service voice/chat sessions and bounded interaction history.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "conversation_sessions")

    async def get_by_session_id(self, session_id: str) -> dict[str, Any] | None:
        doc = await self.collection.find_one({"session_id": session_id})
        return self._serialize_doc(doc)

    async def create_session(
        self,
        session_id: str,
        customer_id: str | None = None,
        session_token: str | None = None,
        initial_history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        doc = {
            "session_id": session_id,
            "session_token": session_token,
            "customer_id": customer_id,
            "work_order_id": None,
            "tentative_hold_id": None,
            "status": "active",  # active, escalated, completed, expired, closed
            "extracted_draft": {},
            "history": initial_history or [],
            "escalation_reason": None,
            "created_at": now,
            "updated_at": now,
        }
        await self.collection.insert_one(doc)
        return self._serialize_doc(doc)  # type: ignore

    async def update_session_state(
        self,
        session_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        now = datetime.now(UTC)
        updates["updated_at"] = now
        await self.collection.update_one(
            {"session_id": session_id},
            {"$set": updates},
        )
        return await self.get_by_session_id(session_id)

    async def append_messages(
        self,
        session_id: str,
        new_messages: list[dict[str, Any]],
        draft_updates: dict[str, Any] | None = None,
        work_order_id: str | None = None,
        tentative_hold_id: str | None = None,
        status: str | None = None,
        escalation_reason: str | None = None,
    ) -> dict[str, Any] | None:
        now = datetime.now(UTC)
        push_op = {
            "$push": {
                "history": {
                    "$each": new_messages,
                    "$slice": -settings.CONVERSATION_HISTORY_LIMIT,
                }
            },
            "$set": {
                "updated_at": now,
            },
        }
        if draft_updates is not None:
            push_op["$set"]["extracted_draft"] = draft_updates
        if work_order_id is not None:
            push_op["$set"]["work_order_id"] = work_order_id
        if tentative_hold_id is not None:
            push_op["$set"]["tentative_hold_id"] = tentative_hold_id
        if status is not None:
            push_op["$set"]["status"] = status
        if escalation_reason is not None:
            push_op["$set"]["escalation_reason"] = escalation_reason

        await self.collection.update_one({"session_id": session_id}, push_op)
        return await self.get_by_session_id(session_id)
