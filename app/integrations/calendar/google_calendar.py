import logging
from typing import Any

import httpx

from app.integrations.calendar.protocol import (
    CalendarEventPayload,
    CalendarEventResult,
    CalendarProviderProtocol,
)

logger = logging.getLogger(__name__)


class GoogleCalendarAdapter(CalendarProviderProtocol):
    """
    Google Calendar API v3 provider implementation.
    Requires OAuth access token.
    """

    def __init__(self, access_token: str = ""):
        self.access_token = access_token

    async def create_event(self, payload: CalendarEventPayload) -> CalendarEventResult:
        if not self.access_token:
            return CalendarEventResult(
                success=False,
                provider="google_calendar",
                external_event_id="",
                error_message="Google Calendar OAuth access token not configured.",
            )

        url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "summary": payload.title,
            "description": payload.description,
            "location": payload.location,
            "start": {"dateTime": payload.start_time.isoformat()},
            "end": {"dateTime": payload.end_time.isoformat()},
            "attendees": [{"email": e} for e in payload.attendee_emails],
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, headers=headers, json=body)
                if resp.status_code in (200, 201):
                    data = resp.json()
                    return CalendarEventResult(
                        success=True,
                        provider="google_calendar",
                        external_event_id=data.get("id", ""),
                        html_link=data.get("htmlLink"),
                    )
                return CalendarEventResult(
                    success=False,
                    provider="google_calendar",
                    external_event_id="",
                    error_message=f"Google Calendar error {resp.status_code}: {resp.text}",
                )
        except Exception as exc:
            return CalendarEventResult(
                success=False,
                provider="google_calendar",
                external_event_id="",
                error_message=f"Google Calendar request failed: {str(exc)}",
            )

    async def update_event(
        self, external_event_id: str, payload: CalendarEventPayload
    ) -> CalendarEventResult:
        if not self.access_token:
            return CalendarEventResult(
                success=False,
                provider="google_calendar",
                external_event_id=external_event_id,
                error_message="Google Calendar OAuth access token not configured.",
            )

        url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{external_event_id}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "summary": payload.title,
            "description": payload.description,
            "location": payload.location,
            "start": {"dateTime": payload.start_time.isoformat()},
            "end": {"dateTime": payload.end_time.isoformat()},
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.put(url, headers=headers, json=body)
                if resp.status_code == 200:
                    data = resp.json()
                    return CalendarEventResult(
                        success=True,
                        provider="google_calendar",
                        external_event_id=data.get("id", external_event_id),
                        html_link=data.get("htmlLink"),
                    )
                return CalendarEventResult(
                    success=False,
                    provider="google_calendar",
                    external_event_id=external_event_id,
                    error_message=f"Google Calendar update error {resp.status_code}: {resp.text}",
                )
        except Exception as exc:
            return CalendarEventResult(
                success=False,
                provider="google_calendar",
                external_event_id=external_event_id,
                error_message=f"Google Calendar update failed: {str(exc)}",
            )

    async def delete_event(self, external_event_id: str) -> bool:
        if not self.access_token:
            return False
        url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{external_event_id}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.delete(url, headers=headers)
                return resp.status_code in (200, 204)
        except Exception:
            return False
