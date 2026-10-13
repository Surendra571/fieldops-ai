from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class CalendarEventPayload:
    title: str
    description: str
    start_time: datetime
    end_time: datetime
    location: str
    attendee_emails: list[str]
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class CalendarEventResult:
    success: bool
    provider: str
    external_event_id: str
    html_link: str | None = None
    error_message: str | None = None


class CalendarProviderProtocol(Protocol):
    """
    Provider-independent interface for external calendar synchronization (e.g. Google Calendar, Outlook).
    """

    async def create_event(self, payload: CalendarEventPayload) -> CalendarEventResult:
        """Create a synchronized calendar event."""
        ...

    async def update_event(
        self, external_event_id: str, payload: CalendarEventPayload
    ) -> CalendarEventResult:
        """Update an existing calendar event (e.g. when rescheduled)."""
        ...

    async def delete_event(self, external_event_id: str) -> bool:
        """Delete/cancel a calendar event."""
        ...
