from app.core.config import settings
from app.integrations.calendar.google_calendar import GoogleCalendarAdapter
from app.integrations.calendar.mock_calendar import MockCalendarAdapter
from app.integrations.calendar.protocol import (
    CalendarEventPayload,
    CalendarEventResult,
    CalendarProviderProtocol,
)

_mock_calendar_instance: MockCalendarAdapter | None = None


def get_calendar_provider() -> CalendarProviderProtocol:
    global _mock_calendar_instance
    if settings.CALENDAR_PROVIDER == "google_calendar":
        return GoogleCalendarAdapter()
    if _mock_calendar_instance is None:
        _mock_calendar_instance = MockCalendarAdapter()
    return _mock_calendar_instance


__all__ = [
    "CalendarEventPayload",
    "CalendarEventResult",
    "CalendarProviderProtocol",
    "GoogleCalendarAdapter",
    "MockCalendarAdapter",
    "get_calendar_provider",
]
