import uuid
from typing import Any

from app.integrations.calendar.protocol import (
    CalendarEventPayload,
    CalendarEventResult,
    CalendarProviderProtocol,
)


class MockCalendarAdapter(CalendarProviderProtocol):
    """
    Deterministic in-memory calendar sync adapter.
    """

    def __init__(self):
        self.events: dict[str, dict[str, Any]] = {}
        self._simulate_failure: bool = False
        self._failure_reason: str = "Simulated calendar API failure"
        self._fail_count_remaining: int = 0

    def simulate_failures(self, count: int, reason: str = "Simulated calendar error"):
        self._fail_count_remaining = count
        self._failure_reason = reason

    def clear(self):
        self.events.clear()
        self._fail_count_remaining = 0

    async def create_event(self, payload: CalendarEventPayload) -> CalendarEventResult:
        if self._fail_count_remaining > 0:
            self._fail_count_remaining -= 1
            return CalendarEventResult(
                success=False,
                provider="mock_google_calendar",
                external_event_id="",
                error_message=self._failure_reason,
            )

        event_id = f"cal_evt_{uuid.uuid4().hex[:12]}"
        self.events[event_id] = {
            "title": payload.title,
            "description": payload.description,
            "start_time": payload.start_time,
            "end_time": payload.end_time,
            "location": payload.location,
            "attendees": payload.attendee_emails,
            "metadata": payload.metadata or {},
        }

        return CalendarEventResult(
            success=True,
            provider="mock_google_calendar",
            external_event_id=event_id,
            html_link=f"https://calendar.google.com/event?eid={event_id}",
        )

    async def update_event(
        self, external_event_id: str, payload: CalendarEventPayload
    ) -> CalendarEventResult:
        if self._fail_count_remaining > 0:
            self._fail_count_remaining -= 1
            return CalendarEventResult(
                success=False,
                provider="mock_google_calendar",
                external_event_id=external_event_id,
                error_message=self._failure_reason,
            )

        if external_event_id not in self.events:
            return CalendarEventResult(
                success=False,
                provider="mock_google_calendar",
                external_event_id=external_event_id,
                error_message="Event not found in external calendar.",
            )

        self.events[external_event_id].update(
            {
                "title": payload.title,
                "description": payload.description,
                "start_time": payload.start_time,
                "end_time": payload.end_time,
                "location": payload.location,
            }
        )

        return CalendarEventResult(
            success=True,
            provider="mock_google_calendar",
            external_event_id=external_event_id,
            html_link=f"https://calendar.google.com/event?eid={external_event_id}",
        )

    async def delete_event(self, external_event_id: str) -> bool:
        if external_event_id in self.events:
            del self.events[external_event_id]
            return True
        return False
