from src.services.errors.base import DomainError
from src.modules.interviews.dtos.interviews_dto import MeetingDetails, Reminders
from configs.env_config import FRONTEND_URL,FireFlies_Bot,COMPANY_EMAIL
from src.models.enums import InterviewStatus, PanelMode,MeetingHostType, CalendarProvider,InterviewEventType,InterviewEventActor
from datetime import datetime, timedelta, timezone
from uuid import UUID
from typing import Optional
from configs.log_config import get_logger
from src.modules.interviews.services.helpers.token_manager.Interview_token_manger import InterviewTokenManagerFactory
from src.enums.interview_token_facrory_enum import UserType
from src.modules.interviews.services.calendar_service import CalendarService
from src.modules.interviews.repositories.calendar_repository import CalendarRepository


# TODO: Implemented later
class InterviewMeetingHelper:
    def __init__(
        self,
        interview_token_manger_factory:InterviewTokenManagerFactory,
        calendar_repostiory:CalendarRepository,
        calendar_service:CalendarService       
                 
        ):
        
        self.interview_token_manger_factory = interview_token_manger_factory
        self.calendar_repostiory = calendar_repostiory
        self.calendar_service = calendar_service
        self.logger = get_logger("InterviewMeetingHelper")

    
    
    
    def _build_meeting_details(
        self,
        round_config,
        slot,
        attendees_emails: list[str],
        interview,
    ) -> MeetingDetails:
        print("TIMEZONE",round_config.timezone)
        return MeetingDetails(
            summary=round_config.title,
            description=f"Interview for {round_config.title}",
            location=round_config.interview_type.value if round_config.interview_type else "Online",
            start_time = slot.slot_start.isoformat(),
            end_time = slot.slot_end.isoformat(),
            timezone=round_config.timezone or "Asia/Kolkata",
            attendees_emails=attendees_emails,
            application_id=str(interview.application_id) if interview.application_id else None,
            reminders=[
                Reminders(method="email", minutes_before=1440),  # 1 day before
                Reminders(method="email", minutes_before=60),
                Reminders(method="email", minutes_before=30),
                Reminders(method="popup", minutes_before=10),
            ],
            visibility="public",
        )
    
        #! Currently bt default using Google calendar will need to make dynamic if required in future based on provider in calendar connection table for panelist and hr calendar credential
    
    async def _get_meet_link_for_interview(self, meeting_details: MeetingDetails, meeting_host_type:MeetingHostType,provider:CalendarProvider=CalendarProvider.GOOGLE,host_email:str=COMPANY_EMAIL) -> Optional[tuple[str,str | UUID]]:
        """Generate a calendar event and return the meet link."""
        
        # TODO: move redundant parts from other methods to here 
        
        refresh_token = await self.calendar_repostiory.get_calendar_access_token(host_email,CalendarProvider.GOOGLE)
        
        if not refresh_token:
            self.logger.error(f"Calendar refresh token not found for panelist {host_email}, provider {CalendarProvider.GOOGLE}")
            raise DomainError("Calendar credentials not found for the panelist, cannot create calendar event", status_code=404)
        
        
        if meeting_host_type == MeetingHostType.HR:
                # TODO: update to create calendar event with hr calendar credential
            meet_link,event_id = await self.calendar_service.create_google_calendar_event_owner_deskzero(meeting_details)
            
            
        elif meeting_host_type == MeetingHostType.PANELIST:
            self.logger.info(f"Creating calendar event with panelist credentials for meeting hosted by panelist.")
            meet_link,event_id = await self.calendar_service.create_google_calendar_event_owner_panelist(meeting_details,refresh_token)
            
        else:
            meet_link,event_id = await self.calendar_service.create_google_calendar_event_owner_deskzero(meeting_details)
        
        return meet_link,event_id



    
    
    async def _delete_calendar_event(self, calendar_event_id:str,host_email:str,provider:CalendarProvider=CalendarProvider.GOOGLE):
        try:
            refresh_token = await self.calendar_repostiory.get_calendar_access_token(host_email,CalendarProvider.GOOGLE)
        
            if not refresh_token:
                self.logger.error(f"Calendar refresh token not found for panelist {host_email}, provider {CalendarProvider.GOOGLE}")
                raise DomainError("Calendar credentials not found for the panelist, cannot create calendar event", status_code=404)
            
            if provider == CalendarProvider.GOOGLE:
                await self.calendar_service.delete_google_calendar_event(calendar_event_id,refresh_token)    
            

        except Exception as e:
            self.logger.error(f"Failed to delete calendar event with id {calendar_event_id} for host {host_email} and provider {provider}: {e}")




    async def _create_meet_link_and_reschedule_token(
        self,
        round_config,
        slot,
        interview,
        panelist,
        candidate_email: str,
        Provider: CalendarProvider = CalendarProvider.GOOGLE,
    ) -> tuple[str, str | UUID ,str , datetime]:
        """
        Fetches calendar creds, creates meet link, mints a candidate reschedule token.
        Returns (meet_link, reschedule_token, expiry_time).
        """
       
        attendees = [COMPANY_EMAIL, FireFlies_Bot, candidate_email, panelist.email]
        meeting_details = self._build_meeting_details(round_config, slot, attendees, interview)
        
        meet_link,calendar_event_id = await self._get_meet_link_for_interview(
            meeting_details, round_config.meeting_host_type, host_email=panelist.email,provider=Provider
        )

        expiry_time = slot.slot_start - timedelta(minutes=10)
        remaining_minutes = max(1, int((expiry_time - datetime.now(timezone.utc)).total_seconds() / 60))
        
        reschedule_token = self.interview_token_manger_factory.get_manager(UserType).create_token(
            token_type="reschedule",
            expiration_minutes=remaining_minutes,
            candidate_email=candidate_email,
            interview_id=str(interview.id),
        )
        
        return meet_link,calendar_event_id,reschedule_token, expiry_time
    