"""
Calendar Service
================
Generates RFC 5545 compliant .ics calendar invites for interview bookings.
Uses the `icalendar` library. Install via: pip install icalendar
"""
from pydantic import BaseModel
from datetime import datetime, timezone
from uuid import uuid4
from configs.log_config import get_logger
from src.repositories.interview_respositories.calendar_repository import CalendarRepository
from configs.env_config import Calendar_Client_Secret,Calendar_Client_ID,Google_Calendar_Meet_Creation_link,Google_Calendar_Access_Token ,Calendar_Refresh_Token      
import uuid
from typing import List, Optional
import httpx
from src.dtos.interviews_dtos.interviews_dto import MeetingDetails, Reminders
from uuid import UUID

# def _format_dt(dt: datetime) -> str:
#     """Format datetime as iCalendar UTC timestamp: 20260315T100000Z"""
#     if dt.tzinfo is None:
#         dt = dt.replace(tzinfo=timezone.utc)
#     utc_dt = dt.astimezone(timezone.utc)
#     return utc_dt.strftime("%Y%m%dT%H%M%SZ")


# def _escape(text: str) -> str:
#     """Escape special characters for iCalendar text fields."""
#     return (
#         text.replace("\\", "\\\\")
#         .replace(";", "\\;")
#         .replace(",", "\\,")
#         .replace("\n", "\\n")
#     )



class ICSGenerator:
    """Legacy class for generating .ics files using the icalendar library. 
    This is currently unused but can be repurposed if we want to switch to using the library instead of raw string formatting.
    """
    def __init__(self):
        self.logger = get_logger("ICSGenerator")
        
        
    def generate_ics(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        description: str = "",
        location: str = "",
        organizer_email: str | None = None,
        attendee_emails: list[str] | None = None,
    ) -> str:
        """
        Generate an .ics calendar event string.
        
        This uses raw string formatting to avoid hard dependency on icalendar
        library. Output is RFC 5545 compliant.

        Args:
            summary:   Event title (e.g. "Technical Interview – Round 1")
            start:     UTC start datetime
            end:       UTC end datetime
            description: Plain text description
            location:  Physical address or virtual meeting link
            organizer_email: Optional organizer email
            attendee_emails: Optional list of attendee emails
        
        Returns:
            .ics file contents as a string
        """
        uid = f"{uuid4()}@deskzero.app"
        dtstamp = self._format_dt(datetime.now(timezone.utc))
        dtstart = self._format_dt(start)
        dtend = self._format_dt(end)

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//DeskZero//Interview Scheduler//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:REQUEST",
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART:{dtstart}",
            f"DTEND:{dtend}",
            f"SUMMARY:{self._escape(summary)}",
        ]

        if description:
            lines.append(f"DESCRIPTION:{self._escape(description)}")

        if location:
            lines.append(f"LOCATION:{self._escape(location)}")

        if organizer_email:
            lines.append(f"ORGANIZER;CN=HR:mailto:{organizer_email}")

        for email in (attendee_emails or []):
            lines.append(f"ATTENDEE;RSVP=TRUE;ROLE=REQ-PARTICIPANT:mailto:{email}")

        lines.append("STATUS:CONFIRMED")
        lines.append("BEGIN:VALARM")
        lines.append("TRIGGER:-PT15M")
        lines.append("ACTION:DISPLAY")
        lines.append("DESCRIPTION:Interview starts in 15 minutes")
        lines.append("END:VALARM")
        lines.append("END:VEVENT")
        lines.append("END:VCALENDAR")

        return "\r\n".join(lines)

        
    #  ------------------------ Helpers ------------------------
    def _format_dt(dt: datetime) -> str:
        """Format datetime as iCalendar UTC timestamp: 20260315T100000Z"""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        utc_dt = dt.astimezone(timezone.utc)
        return utc_dt.strftime("%Y%m%dT%H%M%SZ")


    def _escape(text: str) -> str:
        """Escape special characters for iCalendar text fields."""
        return (
            text.replace("\\", "\\\\")
            .replace(";", "\\;")
            .replace(",", "\\,")
            .replace("\n", "\\n")
        )


class CalendarService(ICSGenerator):
    """Service layer for calendar-related operations, such as generating .ics files for interview events. 
    This is currently unused but can be expanded in the future to handle more complex calendar logic, such as syncing with external calendar providers.
    """
    def __init__(self):
        super().__init__()
        
        self.logger = get_logger("CalendarService")
        
        # ---- DeskZero Calendar Credentials
        self.calendar_client_id = Calendar_Client_ID
        self.calendar_client_secret = Calendar_Client_Secret
        self.google_calendar_access_token = Google_Calendar_Access_Token
        self.google_calendar_meet_creation_link = Google_Calendar_Meet_Creation_link
        self.calendar_refresh_token = Calendar_Refresh_Token
        
        
        
    def _build_google_calendar_event(
        self,
        meeting_details:MeetingDetails
    ):
        """
        Returns Google Calendar event body for creating event with Google Meet.
        """

        attendees = [{"email": email} for email in meeting_details.attendees_emails] if meeting_details.attendees_emails else []

        event_body = {
            "summary": meeting_details.summary,
            "description":  meeting_details.description,
            "location":  meeting_details.location,
            "visibility":  meeting_details.visibility,
            "start": {
                "dateTime":  meeting_details.start_time,
                "timeZone":  meeting_details.timezone,
            },
            "end": {
                "dateTime":  meeting_details.end_time,
                "timeZone":  meeting_details.timezone,
            },
            "attendees":  attendees,
            "conferenceData": {
                "createRequest": {
                    "requestId": str(uuid.uuid4()),
                    "conferenceSolutionKey": {
                        "type": "hangoutsMeet"
                    }
                }
            },
            "guestsCanInviteOthers": False,
            "guestsCanModify": False,
            "guestsCanSeeOtherGuests": True,
        }

        # Add metadata
        if  meeting_details.application_id:
            event_body["extendedProperties"] = {
                "private": {
                    "application_id":  meeting_details.application_id
                }
            }

        # Reminders
        if meeting_details.reminders:
            event_body["reminders"] = {
                "useDefault": False,
                "overrides": [
                    {
                        "method": r.method,
                        "minutes": r.minutes_before
                    }
                    for r in meeting_details.reminders
                ]
            }
        else:
            event_body["reminders"] = {"useDefault": True}

        return event_body

    async def _get_google_access_token(self,refresh_token:str) -> str:
        # ! Url needs to be stored in env config
        url = "https://oauth2.googleapis.com/token"

        data = {
            "client_id": self.calendar_client_id,
            "client_secret": self.calendar_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }

        async with httpx.AsyncClient() as client:
            res = await client.post(url, data=data)

        if res.status_code != 200:
            raise Exception(f"Failed to refresh access token: {res.text}")

        return res.json()["access_token"]


    async def create_google_calendar_event_owner_deskzero(self,meeting_details: MeetingDetails) -> str:
        try:
            
            access_token  = await self._get_google_access_token(refresh_token=self.calendar_refresh_token)
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            event_body = self._build_google_calendar_event(meeting_details)

            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(
                    f"{self.google_calendar_meet_creation_link}?conferenceDataVersion=1",
                    json=event_body,
                    headers=headers
                )

            if res.status_code not in [200, 201]:
                self.logger.error(
                    f"Google Calendar API error: {res.status_code} - {res.text}"
                )
                raise Exception("Failed to create calendar event")

            data = res.json()
            
            if not data.get("hangoutLink"):
                self.logger.error(
                    f"Google Calendar event created but no Meet link generated: {data}"
                )
                raise Exception("Calendar event created but failed to generate Meet link")

            self.logger.info(
                f"Google Calendar event created successfully"
            )

            return data.get("hangoutLink")

        except Exception as e:
            self.logger.error(f"Error creating Google Calendar event: {str(e)}")
            raise Exception("Failed to create calendar event")
        
    # ! currenlty using refresj token as for dev apps google provide short lived   
    async def create_google_calendar_event_owner_panelist(self,meeting_details: MeetingDetails,refresh_token:str) -> str:
        try:
            
            access_token  = await self._get_google_access_token(refresh_token)
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            event_body = self._build_google_calendar_event(meeting_details)

            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(
                    f"{self.google_calendar_meet_creation_link}?conferenceDataVersion=1",
                    json=event_body,
                    headers=headers
                )

            if res.status_code not in [200, 201]:
                self.logger.error(
                    f"Google Calendar API error: {res.status_code} - {res.text}"
                )
                raise Exception("Failed to create calendar event")

            data = res.json()
            
            if not data.get("hangoutLink"):
                self.logger.error(
                    f"Google Calendar event created but no Meet link generated: {data}"
                )
                raise Exception("Calendar event created but failed to generate Meet link")

            self.logger.info(
                f"Google Calendar event created successfully"
            )

            return data.get("hangoutLink")

        except Exception as e:
            self.logger.error(f"Error creating Google Calendar event: {str(e)}")
            raise Exception("Failed to create calendar event")