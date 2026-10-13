from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditEventCreate(BaseModel):
    entity_type: str
    entity_id: str
    action: str
    actor_id: str | None = None
    actor_role: str | None = None
    changes: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class AuditEventResponse(AuditEventCreate):
    id: str
    timestamp: datetime
