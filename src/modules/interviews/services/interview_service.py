from sqlalchemy.ext.asyncio import AsyncSession
from  configs.log_config import get_logger
from configs.env_config import FRONTEND_URL,FireFlies_Bot,COMPANY_EMAIL
from src.services.errors.base import DomainError

from src.modules.interviews.repositories import CalendarRepository,InterviewRepository,InterviewEventRepository,InterviewRoundConfigsRepository,InterviewSlotsRepository,PanelistRepository

from src.repositories.application_repository import ApplicationRepository 

from src.modules.email_services.services import CandidateEmailService, PanelEmailService
from src.models.enums import InterviewStatus, PanelMode,MeetingHostType, CalendarProvider,InterviewEventType,InterviewEventActor
from src.utils.timeline_formatter import TimelineFormatter, timeline_formatter
from datetime import datetime, timezone, timedelta
from typing import Optional
from src.repositories.job_repository import JobRepository
from workers_async.email_tasks_producer import EmailProducer,EnqueueReminderPayload
from src.modules.interviews.dtos.panel_dto import CreatePanelDTO
from src.modules.interviews.dtos.interviews_dto import MeetingDetails, Reminders
import asyncio
from src.utils.time_helper import format_interview_time, format_interview_schedule,serialize_datetime,TimeHelper
from src.utils.jwt import JWTService
from src.modules.interviews.services.calendar_service import CalendarService
from src.modules.reminders.reminder_dtos import CreateReminderDTO
from src.dtos.emails.panel_dto import PanelistReminderAvailabilityData,PanelistInterviewReminderData,PanelistBookingData,AvailableSlotsData,ThankYouPanelistData,PanelistSlotReleasedData,PanelistMeetingRescheduledData
from src.dtos.emails.candidate_dto import CandidateBookingLinkReminderData,CandidateInterviewReminderData,CandidateBookingLinkData,CandidateBookingConfirmationData,CandidateRescheduleNewSlotsData
from src.modules.reminders.model.reminder_enum import ReminderType, RecipientType, EntityType,ReminderStatus
from datetime import timedelta
from src.dtos.job_settings_dto import ReminderSettingsDTO,ReschedulingSettingsDTO
from src.modules.reminders.reminder_repository import ReminderRepository
from uuid import UUID
import pdfkit
import tempfile
from zoneinfo import ZoneInfo
from src.utils.supabase_file_handler import SupabaseFileHandler




# TODO:  most of the methods doing same things and can be optimized skipping for future refactor for now to focus on feature development, also need to add more logs for better observability and debugging
class InterviewService:
    def __init__(
        self,
        interview_round_config_repository: InterviewRoundConfigsRepository,
        interview_event_repository: InterviewEventRepository,
        interview_repository: InterviewRepository,
        panelist_repository: PanelistRepository,
        slots_repository: InterviewSlotsRepository,
        calendar_repostiory:CalendarRepository,
        calendar_service: CalendarService,
        application_repository: ApplicationRepository ,
        panel_email_service: PanelEmailService,
        candidate_email_service: CandidateEmailService,
        job_repository: JobRepository,
        reminder_repository: ReminderRepository,
        email_producer: EmailProducer,
        supabase_file_handler: SupabaseFileHandler,
        db: AsyncSession,
        time_helper: TimeHelper | None = None,
    ):
        self.db = db
        self.interview_event_repository = interview_event_repository
        self.interview_round_config_repository = interview_round_config_repository
        self.interview_repository = interview_repository
        self.panelist_repository = panelist_repository
        self.calendar_repostiory = calendar_repostiory
        self.slots_repository = slots_repository
        self.job_repository = job_repository
        self.reminder_repository = reminder_repository
        self.email_producer = email_producer
        self.jwt_service: JWTService = JWTService()
        self.calendar_service = calendar_service
        self.application_repository = application_repository
        self.candidate_email_service: CandidateEmailService = candidate_email_service
        self.panel_email_service: PanelEmailService = panel_email_service
        self.timeline_formatter: TimelineFormatter = timeline_formatter
        self.frontend_url = FRONTEND_URL
        self.time_helper = time_helper or TimeHelper()
        self.supabase_file_handler = supabase_file_handler

        self.logger = get_logger("InterviewService")

    # ─── Timeline ─────────────────────────────────────────────────────────

    async def get_timeline(self, interview_id: str) -> list[dict]:
        """
        Fetch all timeline events for an interview and return them
        formatted for the HR dashboard.
        """
        interview = await self.interview_repository.get_interview_by_id(interview_id)
        if not interview:
            raise DomainError("Interview not found", status_code=404)

        events = await self.interview_event_repository.get_events_by_interview_id_brief(interview_id)
        # return self.timeline_formatter.format_timeline(events)
        return events

    # ─── Helpers ──────────────────────────────────────────────────────────

    def _validate_token(self, token: str) -> dict:
        """Decode and validate a candidate booking JWT."""
        payload = self.jwt_service.decode_token(token)
        interview_id = payload.get("interview_id")
        candidate_email = payload.get("candidate_email")
        if not interview_id or not candidate_email:
            raise DomainError("Invalid booking token payload", status_code=400)
        return payload

    def _validate_booking_eligibility(
    self,
        interview,
        token: str,
        round_config,
        is_reschedule: bool = False,
    ) -> None:
        """Raises DomainError if the interview isn't in a bookable state."""
        expected_token = interview.rescheduling_token if is_reschedule else interview.booking_token
        if expected_token != token:
            raise DomainError("Invalid or outdated booking link", status_code=400)

        if interview.status == InterviewStatus.SCHEDULED and not is_reschedule:
            raise DomainError("Interview is already scheduled", status_code=400)

        if interview.status != InterviewStatus.READY_TO_BOOK and not is_reschedule:
            raise DomainError("Booking is not available for this interview", status_code=400)

        if is_reschedule and interview.status != InterviewStatus.SCHEDULED:
            raise DomainError("Only scheduled interviews can be rescheduled", status_code=400)

    def _validate_reschedule_window(self, interview,token) -> None:
        """Raises if the reschedule window has closed."""
        now = datetime.now(timezone.utc)
        
        if now > interview.scheduled_start:
            raise DomainError("Interview has already started, can't reschedule", status_code=400)
        if now > interview.rescheduling_token_expires_at:
            raise DomainError("Rescheduling token has expired, can't reschedule", status_code=400)
        
        if interview.rescheduling_token != token:
                raise DomainError("Invalid or outdated rescheduling link", status_code=400)
        
        if interview.status != InterviewStatus.SCHEDULED:
            raise DomainError("Only scheduled interviews can be rescheduled", status_code=400)
        

    async def _load_interview_and_config(self, interview_id: str):
        """Load interview + round config, raise if missing or wrong status."""
        interview = await self.interview_repository.get_interview_by_id(interview_id)
        if not interview:
            raise DomainError("Interview not found", status_code=404)

        round_config = await self.interview_round_config_repository.get_interview_round_config_by_id(
            str(interview.round_config_id)
        )
        if not round_config:
            raise DomainError("Interview round configuration not found", status_code=404)

        return interview, round_config

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
        reschedule_token = self.jwt_service.create_candidate_reschedule_token(
            candidate_email=candidate_email,
            expiration_minutes=remaining_minutes,
            interview_id=str(interview.id),
        )
        return meet_link,calendar_event_id,reschedule_token, expiry_time
    
    async def _resolve_candidate_display(self, interview) -> tuple[Optional[object], str]:
        """Returns (candidate_obj, display_name). Safe — never raises."""
        try:
            await self.db.refresh(interview, ["application"])
            app = interview.application
            if app:
                await self.db.refresh(app, ["candidate"])
                candidate = app.candidate
                if candidate:
                    return candidate, candidate.full_name or candidate.email
        except Exception:
            pass
        return None, "Candidate"
    
    async def _get_panelist_for_slot(self, round_config_id, slot) -> object:
        """Fetches the panelist for a slot, raises if not found."""
        panelist = await self.panelist_repository.get_panelist_by_round_config_and_panelist_id(
            round_config_id, slot.panelist_id
        )
        if not panelist:
            raise DomainError(
                f"Panelist not found for selected slot", status_code=404
            )
        return panelist
    
    async def _enque_panelist_interview_reminders(self, panelist, panelist_reminder_settings: ReminderSettingsDTO, interview, config, meet_link, candidate_display,slot,panelist_reschedule_link):
        """Enqueues interview reminder emails for panelist based on their reminder settings."""
        reminders_payload = []
        for reminder_hr in panelist_reminder_settings.interview_reminder_sec:
            reminders_payload.append(CreateReminderDTO(
            entity_id=str(interview.id),
            entity_type=EntityType.INTERVIEW,
            payload=PanelistInterviewReminderData(
                candidate_name=candidate_display,
                panelist_name=panelist.name,
                panelist_email=panelist.email,
                interview_round_title=config.title,
                scheduled_start=serialize_datetime(slot.slot_start),
                scheduled_end=serialize_datetime(slot.slot_end),
                meet_link=meet_link,
                reschedule_link=panelist_reschedule_link   
            ).model_dump(mode="json"),
            recipient_id=str(panelist.id),
            recipient_type=RecipientType.PANELIST,
            reminder_type=ReminderType.INTERVIEW_UPCOMING,
                # ! set it before the slot start time minus the reminder hours, currently in minutes for testing, change to hours later
            next_run_at= datetime.now(timezone.utc) + timedelta(seconds=reminder_hr)  #! for now doing in minutes, change to hours later       
        ))
            
            
        if reminders_payload:
            reminders = await self.reminder_repository.create_reminders(reminders_payload)
            
            reminder_map = {str(r.id): r for r in reminders}
            enqueue_payloads = [EnqueueReminderPayload(reminder_id=r.id,run_at=r.next_run_at)for r in reminders]
            enqueue_results = await self.email_producer.enqueue_reminder_email_task(enqueue_payloads)

            for res in enqueue_results:
                if res.status == "success":
                    reminder_map[str(res.reminder_id)].worker_job_id = res.job_id 
            
            self.logger.info(f"Enqueued {len(enqueue_payloads)} reminder emails for panelist {panelist.email}")
    
    async def _enque_candidate_interview_reminders(self, candidate_email, candidate_display, candidate_reminder_settings: ReminderSettingsDTO, interview, config, meet_link, cand_reschedule_link,candidate,slot):
        reminders_payload = []
        for reminder_hr in candidate_reminder_settings.interview_reminder_sec:
            reminders_payload.append(CreateReminderDTO(
            entity_id=str(interview.id),
            entity_type=EntityType.INTERVIEW,
            payload=CandidateInterviewReminderData(
                candidate_name=candidate_display,
                candidate_email=candidate.email,
                interview_round_title=config.title,
                scheduled_start=serialize_datetime(slot.slot_start),
                scheduled_end=serialize_datetime(slot.slot_end),
                meet_link=meet_link,
                reschedule_link=cand_reschedule_link   
            ).model_dump(mode="json"),
            recipient_id=str(candidate.id or candidate_email),
            recipient_type=RecipientType.CANDIDATE,
            reminder_type=ReminderType.INTERVIEW_UPCOMING,
            # ! set it before the slot start time minus the reminder hours, currently in minutes for testing, change to hours later
            next_run_at= datetime.now(timezone.utc) + timedelta(seconds=reminder_hr)  #! for now doing in minutes, change to hours later       
        ))
            
            
        if reminders_payload:
            reminders = await self.reminder_repository.create_reminders(reminders_payload)
            
            reminder_map = {str(r.id): r for r in reminders}
            enqueue_payloads = [EnqueueReminderPayload(reminder_id=r.id,run_at=r.next_run_at)for r in reminders]
            enqueue_results = await self.email_producer.enqueue_reminder_email_task(enqueue_payloads)

            for res in enqueue_results:
                if res.status == "success":
                    reminder_map[str(res.reminder_id)].worker_job_id = res.job_id 
            
            self.logger.info(f"Enqueued {len(enqueue_payloads)} reminder emails for candidate {candidate_display} ")
    
          
        
    def _create_form_reminder_payload_for_panelist(self,requested_panelist,config, panelist_reminder_settings: ReminderSettingsDTO) -> list[CreateReminderDTO]:
        reminders_payload = []
        for panelist in requested_panelist:
            for reminder_hr in panelist_reminder_settings.form_reminder_sec:
                reminders_payload.append(CreateReminderDTO(
                    entity_id=str(config.id),
                    entity_type=EntityType.INTERVIEW,
                    payload=PanelistReminderAvailabilityData(
                        panelist_email=panelist.email,
                        panelist_name=panelist.name,
                        interview_round_title=config.title,
                        form_link=f"{self.frontend_url}/panelist/availability?token={panelist.availability_token}"
                    ).model_dump(),
                    recipient_id=str(panelist.id),
                    recipient_type=RecipientType.PANELIST,
                    reminder_type=ReminderType.BOOKING_LINK,
                    next_run_at= datetime.now(timezone.utc) + timedelta(seconds=reminder_hr)  #! for now doing in minutes, change to hours later       
                ))
                
        return reminders_payload
    
    
    
        

    def _generate_pdf_from_html(self, html_content: str):
        config = pdfkit.configuration(
            wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
        )

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        path = temp_file.name
        temp_file.close()

        pdfkit.from_string(html_content, path, configuration=config)

        return path
    
    def _normalize_transcript(self, transcript):
        for s in transcript["sentences"]:
            # s["role"] = "candidate" if "Raj" in s["speaker_name"] else "interviewer"
            s["time"] = f"{self.time_helper.format_time_for_transcript(s['start_time'])} – {self.time_helper.format_time_for_transcript(s['end_time'])}"
        return transcript
    
    
    # ─── GET booking form ─────────────────────────────────────────────────

    async def get_booking_form(self, token: str,is_reschedule: bool = False):
        """
        Validate token, return available slots for the candidate to pick.
        PANEL mode  → flat list of slots (panelist_email=null)
        SEQUENTIAL  → grouped by panelist {email: [slots]}
        """
        token = token.replace("Bearer ", "")
        payload = self._validate_token(token)
        interview_id = payload["interview_id"]

        interview, round_config = await self._load_interview_and_config(interview_id)

        # Token match check
        if is_reschedule == False and interview.booking_token != token:
            raise DomainError("Invalid or outdated booking link", status_code=400)
        
        
        if is_reschedule == True and interview.rescheduling_token != token:
            raise DomainError("Invalid or outdated rescheduling link", status_code=400)
        
        booked_slot = await self.slots_repository.get_booked_slot_by_interview_id(interview_id=interview_id)
        
        if is_reschedule and interview.rescheduling_token != token:
            raise DomainError("Invalid or outdated rescheduling link", status_code=400)

        # Already booked?
        if not is_reschedule and interview.status == InterviewStatus.SCHEDULED:
            return {
                "status": "already_booked",
                "message": "Your interview is already scheduled.",
                "scheduled_start": interview.scheduled_start.isoformat() if interview.scheduled_start else None,
                "scheduled_end": interview.scheduled_end.isoformat() if interview.scheduled_end else None,
            }

        # Token expired?
        if interview.booking_token_expires_at and interview.booking_token_expires_at < datetime.now(timezone.utc):
            return {
                "status": "expired",
                "message": "Your booking link has expired. Please contact HR for a new link.",
            }

        # Must be in READY_TO_BOOK
        if not is_reschedule and interview.status != InterviewStatus.READY_TO_BOOK:
            return {
                "status": "unavailable",
                "message": "Slots are not yet available for booking. Please wait for confirmation.",
            }

        # Build response based on panel mode
        if round_config.panel_mode == PanelMode.PANEL:
            slots = await self.slots_repository.get_available_slots(round_config.id)
            
            
            
            return {
                "status": "open",
                "panel_mode": "panel",
                "current_slot":{
                "id:": str(booked_slot.id) if booked_slot else None,
                "slot_start": booked_slot.slot_start.isoformat() if booked_slot else None,
                "slot_end": booked_slot.slot_end.isoformat() if booked_slot else None,
                },
                "data": {
                    "title": round_config.title,
                    "interview_type": round_config.interview_type.value if round_config.interview_type else None,
                    "duration_minutes": round_config.duration_minutes,
                    "slots": [
                        {
                            "id": str(s.id),
                            "slot_start": s.slot_start.isoformat(),
                            "slot_end": s.slot_end.isoformat(),
                        }
                        for s in slots
                    ],
                },
            }
        else:
            # SEQUENTIAL mode — grouped by panelist
            grouped = await self.slots_repository.get_slots_grouped_by_panelist(round_config.id)

            panelist_slots = {}

            for panelist_id, slot_list in grouped.items():
                panelist_slots[str(panelist_id)] = [
                    {
                        "id": str(s.id),
                        "slot_start": s.slot_start.isoformat(),
                        "slot_end": s.slot_end.isoformat(),
                    }
                    for s in slot_list
                ]
            return {
                "status": "open",
                "panel_mode": "sequential",
                "current_slot": {
                    "id": str(booked_slot.id) if booked_slot else None,
                    "slot_start": booked_slot.slot_start.isoformat() if booked_slot else None,
                    "slot_end": booked_slot.slot_end.isoformat() if booked_slot else None,
                },
                "data": {
                    "title": round_config.title,
                    "interview_type": round_config.interview_type.value if round_config.interview_type else None,
                    "duration_minutes": round_config.duration_minutes,
                    "panelist_slots": panelist_slots,
                },
            }


    # ─── SEQUENTIAL mode: book one slot per panelist ──────────────────────
    # TODO: change bokings only one slot over all the panelist 
    async def book_sequential_slot(self, token: str, slot_id:str):
        """
        SEQUENTIAL mode: candidate picks one slot over all panelist.
        bookings = [{"panelist_email": "...", "slot_id": "..."}, ...]
        """
        try:
            token = token.replace("Bearer ", "")
            payload = self._validate_token(token)
            interview_id = payload["interview_id"]
            interview, round_config = await self._load_interview_and_config(interview_id)
            slot = await self.slots_repository.get_slot_by_id(slot_id)
            self._validate_booking_eligibility(interview, token, round_config)            
            panelist = await self._get_panelist_for_slot(round_config.id, slot)
            
            if not panelist:
                raise DomainError(f"Panelist not found for selected slot", status_code=404)
            
            
            config = await self.interview_round_config_repository.get_interview_round_config_by_id(round_config.id)

            if not config:
                raise DomainError(f"Interview round configuration not found", status_code=404)
            
            slot = await self.slots_repository.book_slot_atomic(
                slot_id=slot_id,
                interview_id=interview.id,
            )
            if not slot:
                raise DomainError(
                    f"Slot for {panelist.email} is no longer available. Please pick another.",
                    status_code=409,
                )

            old_reminders = await self.reminder_repository.get_all_reminders_by_entity_id_and_type(str(round_config.id), EntityType.INTERVIEW,ReminderStatus.PENDING,ReminderType.BOOKING_LINK,RecipientType.CANDIDATE)
            if old_reminders:
                self.logger.info(f"Cancelling {len(old_reminders)} old booking link reminders for interview {interview.id}")
                old_reminder_ids = [str(r.id) for r in old_reminders]
                await self.reminder_repository.change_reminder_status_multi(old_reminder_ids,ReminderStatus.CANCELLED)
                await self.email_producer.cancel_jobs(old_reminder_ids)
                

            # Check pool exhaustion
            remaining = await self.slots_repository.count_remaining(round_config.id)
            if remaining == 0:
                round_config.slots_available = False
            

            meet_link,calendar_event_id,cand_reschedule_token, expiry_time = await self._create_meet_link_and_reschedule_token(
                round_config, slot, interview, panelist, payload.get("candidate_email", "")
            )
            # Timeline event
            await self.interview_event_repository.create_interview_event(
                interview_id=str(interview.id),
                event_type=InterviewEventType.Interview_Scheduled.value,
                actor=InterviewEventActor.CANDIDATE.value,
                summary=(
                    f"Candidate booked a slot with panelist {panelist.name}."
                    f"\nSchedule: {format_interview_schedule(slot.slot_start, slot.slot_end, round_config.timezone)}"
                    ),
                details={

                            "slot_id": str(slot.id),
                            "panelist_id": str(slot.panelist_id),
                            "candidate_email": payload.get("candidate_email", ""),
                            "slot_start": slot.slot_start.isoformat(),
                            "slot_end": slot.slot_end.isoformat(),
                    "panel_mode": "sequential",
                        }
            )
            
            cand_reschedule_link = f"{self.frontend_url}/interview/reschedule?token={cand_reschedule_token}"
            panelist_reschedule_token = self.jwt_service.create_panelist_reschedule_token(
                    panelist_id=str(panelist.id),
                    round_config_id=str(round_config.id),
                    interview_id=str(interview.id),
                    expiration_minutes=int((expiry_time - datetime.now(timezone.utc)).total_seconds() / 60))

            panelist_reschedule_link = f"{self.frontend_url}/panelist/reschedule?token={panelist_reschedule_token}"
            
            
            interview.scheduled_start = slot.slot_start
            interview.scheduled_end = slot.slot_end
            interview.status = InterviewStatus.SCHEDULED
            interview.booking_token = ""  # Invalidate
            interview.booking_token_expires_at = None

            interview.rescheduling_token_expires_at = expiry_time
            interview.meet_link = meet_link
            interview.calendar_event_id = calendar_event_id
            interview.rescheduling_token = cand_reschedule_token
            
            job_settings = await self.job_repository.get_job_settings(config.job_id)
            
            panelist_reminder_settings = ReminderSettingsDTO.model_validate(job_settings.panel_reminders) if job_settings and job_settings.panel_reminders else None
            candidate_reminder_settings = ReminderSettingsDTO.model_validate(job_settings.candidate_reminders) if job_settings and job_settings.candidate_reminders else None    
            
            candidate, candidate_display = await self._resolve_candidate_display(interview)
            
            
            if panelist_reminder_settings and panelist_reminder_settings.enabled:
                await self._enque_panelist_interview_reminders(panelist, panelist_reminder_settings, interview, config, meet_link, candidate_display,slot,panelist_reschedule_link)
            
            if candidate_reminder_settings and candidate_reminder_settings.enabled and candidate.email:
                await self._enque_candidate_interview_reminders(candidate.email, candidate_display, candidate_reminder_settings, interview, config, meet_link, cand_reschedule_link,candidate,slot)
            
            
            
            
            await self.db.commit()

            # Send confirmation email (best-effort, after commit)

            try:
                
                if candidate:
                    await self.candidate_email_service.send_booking_confirmation_email(
                        CandidateBookingConfirmationData(
                        candidate_email=candidate.email,
                        candidate_name=candidate_display,
                        interview_round_title=round_config.title,
                        scheduled_start=slot.slot_start,
                        scheduled_end=slot.slot_end,
                        meet_link=meet_link,
                        reschedule_link=cand_reschedule_link,
                        )
                    )
            except Exception as e:
                self.logger.error(f"Failed to send booking confirmation email: {e}")

            # Notify each panelist about their specific booked slot (best-effort)
            try:
               
               
                await self.panel_email_service.send_booking_confirmation_to_panelist(
                    PanelistBookingData(
                    panelist_email=panelist.email,
                    panelist_name=panelist.name,
                    candidate_name=candidate_display,
                    interview_round_title=round_config.title,
                    scheduled_start=slot.slot_start,
                    scheduled_end=slot.slot_end,
                    meet_link=meet_link,
                    reschedule_link=panelist_reschedule_link
                    )
                )
            except Exception as e:
                self.logger.error(f"Failed to send panelist booking notifications: {e}")

            return {
                "status": "booked",
                "scheduled_start": slot.slot_start.isoformat(),
                "scheduled_end": slot.slot_end.isoformat(),
                "meet_link": meet_link,
                "panelist_email": str(slot.panelist_id),
            }

        except DomainError:
            raise
        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Error booking sequential slots: {e}")
            raise DomainError("An error occurred while booking your slots. Please try again.")


   
    async def reschedule_to_new_slot(self, token: str, new_slot_id: str):
        """
        Reschedule an already booked interview to a new slot.
        This can be used for both PANEL and SEQUENTIAL modes, but the new slot must be valid for the interview's round config.
        """
        
        try:
            token = token.replace("Bearer ", "")
            payload = self._validate_token(token)
            interview_id = payload["interview_id"]

            interview, round_config = await self._load_interview_and_config(interview_id)
            
            self._validate_reschedule_window(interview,token) 
            
            booked_slot = await self.slots_repository.get_booked_slot_for_interview(interview_id)
            
            if not booked_slot:
                raise DomainError("No booked slot found for this interview, cannot reschedule", status_code=404)
            
            await self.slots_repository.release_slot(booked_slot.id)
            
            new_slot = await self.slots_repository.get_slot_by_id(new_slot_id)
            
            if new_slot.is_booked:
                raise DomainError("Selected new slot is already booked, please choose another", status_code=409)
            
            job_settings = await self.job_repository.get_job_settings(round_config.job_id)
            panelist_reminder_settings = ReminderSettingsDTO.model_validate(job_settings.panel_reminders) if job_settings and job_settings.panel_reminders else None
            candidate_reminder_settings = ReminderSettingsDTO.model_validate(job_settings.candidate_reminders) if job_settings and job_settings.candidate_reminders else None
            reschedule_settings = ReschedulingSettingsDTO.model_validate(job_settings.rescheduling) if job_settings and job_settings.rescheduling else None
            
            if not reschedule_settings.enabled or not reschedule_settings.candidate_rescheduling_allowed:
                raise DomainError("Candidate rescheduling is not allowed for this interview round.", status_code=403)
            
            now = datetime.now(timezone.utc)
            if now > booked_slot.slot_start - timedelta(seconds=reschedule_settings.reschedule_window_for_candidate):
                raise DomainError(f"Rescheduling is only allowed up to {reschedule_settings.reschedule_window_for_candidate/3600} hrs before the scheduled interview time.", status_code=403)
            
            if interview.times_rescheduled_by_candidate >= reschedule_settings.max_reschedule_allowed_by_candidate:
                raise DomainError(f"You have reached the maximum number of reschedules allowed ({reschedule_settings.max_reschedule_allowed_by_candidate}).", status_code=403)

            old_calendar_event_id = interview.calendar_event_id
            
            new_panelist =  await self.panelist_repository.get_panelist_by_round_config_and_panelist_id(round_config.id,new_slot.panelist_id) 
            
            if not new_panelist:
                raise DomainError(f"Panelist with id {new_slot.panelist_id} not found", status_code=404)
            
            
            # Attempt to book the new slot atomically
            await self.slots_repository.book_slot_atomic(new_slot_id,interview.id,)
            
            expiry_time = new_slot.slot_start - timedelta(minutes=10)
            remaining_time = int(
                (expiry_time - datetime.now(timezone.utc)).total_seconds() / 60
            )
            cand_reschedule_token = self.jwt_service.create_candidate_reschedule_token(
                candidate_email=payload.get("candidate_email", ""),
                expiration_minutes=remaining_time,
                interview_id=str(interview.id)
            )
            cand_reschedule_link = f"{self.frontend_url}/interview/reschedule?token={cand_reschedule_token}"
            
            
            panelist_reschedule_token = self.jwt_service.create_panelist_reschedule_token(
                    panelist_id=str(new_panelist.id),
                    round_config_id=str(round_config.id),
                    interview_id=str(interview.id),
                    expiration_minutes=remaining_time
                )
            
            panelist_reschedule_link=f"{self.frontend_url}/panelist/reschedule?token={panelist_reschedule_token}"
            
            
            interview.scheduled_start = new_slot.slot_start
            interview.scheduled_end = new_slot.slot_end
            
            interview.rescheduling_token_expires_at = expiry_time
            
            
            # TODO: also delete event from calendar
            # TODO : cancel all Reminders and events related to the old slot and create new ones for the new slot
           
            
            remaining = await self.slots_repository.count_remaining(round_config.id)
            if remaining == 0:
                round_config.slots_available = False
        
            
            
            old_panelist = await self.panelist_repository.get_panelist_by_round_config_and_panelist_id(round_config_id=round_config.id,panelist_id=booked_slot.panelist_id)
            
            if not old_panelist:
                self.logger.error(f"Old panelist with email {booked_slot.id} not found for round config {round_config.id}")
                raise DomainError("Original panelist not found, cannot reschedule", status_code=404)
 

            if reschedule_settings.same_panel_on_reschedule and old_panelist.email != new_panelist.email:
                raise DomainError("Rescheduling to a different panelist is not allowed for this interview round.", status_code=403)
            
            # TODO: need to either delete old calendar evnet or update the calendar event with new details, currently creating a new calendar event and leaving the old one as is, need to clean up old calendar events later
            
            # new slot panelist is different from old slot panelist then send email to new panelist and old panelist about the reschedule
            attendees_emails = [COMPANY_EMAIL,FireFlies_Bot,payload.get("candidate_email", "")] + [new_panelist.email]  
            meeting_details = self._build_meeting_details(round_config, new_slot, attendees_emails, interview)
            meet_link,calendar_event_id = await self._get_meet_link_for_interview(meeting_details, round_config.meeting_host_type, host_email=new_panelist.email,provider=CalendarProvider.GOOGLE)
            
            
            interview.meet_link = meet_link
            interview.calendar_event_id = calendar_event_id
            interview.times_rescheduled_by_candidate += 1
            candidate, candidate_display = await self._resolve_candidate_display(interview)
            
            all_reminders = await self.reminder_repository.get_all_reminders_by_entity_id_and_type(str(interview.id), EntityType.INTERVIEW)
            
            if all_reminders:
                self.logger.info(f"Cancelling {len(all_reminders)} old booking link reminders for interview {interview.id}")
                old_reminders_ids = [r.id for r in all_reminders if r.reminder_type == ReminderType.BOOKING_LINK and r.status == ReminderStatus.PENDING]
                await self.email_producer.cancel_jobs(old_reminders_ids)
                await self.reminder_repository.change_reminder_status_multi(old_reminders_ids, ReminderStatus.CANCELLED)
                
            tasks = []
            # Send confirmation email (best-effort, after commit)
            try:
                if candidate:
                    
                   tasks.append(self.candidate_email_service.send_booking_confirmation_email(
                       CandidateBookingConfirmationData(
                           
                        candidate_email=candidate.email,
                        candidate_name=candidate.full_name or candidate.email,
                        interview_round_title=round_config.title,
                        scheduled_start=new_slot.slot_start,
                        scheduled_end=new_slot.slot_end,
                        meet_link=meet_link,
                        reschedule_link=cand_reschedule_link,
                       )
                    ))
            except Exception as e:
                self.logger.error(f"Failed to send booking confirmation email: {e}")

            # Notify each panelist about their specific booked slot (best-effort)
            try:
               

                if old_panelist.email != new_panelist.email:
                    self.logger.info(f"Panelist changed from {old_panelist.email} to {new_panelist.email}, sending notifications to both panelists about the reschedule.")
                    
                    
                    # Notify old panelist about the reschedule
                    tasks.append( self.panel_email_service.send_slot_released_to_panelist(
                        PanelistSlotReleasedData(   
                        panelist_email=old_panelist.email,
                        panelist_name=old_panelist.name,
                        candidate_name=candidate_display,
                        interview_round_title=round_config.title,
                        old_scheduled_start=booked_slot.slot_start,
                        old_scheduled_end=booked_slot.slot_end,
                        )
                    ))
                    
                    await self.interview_event_repository.create_interview_event(
                        interview_id=str(interview.id),
                        event_type=InterviewEventType.Interview_Rescheduled.value,
                        actor=InterviewEventActor.CANDIDATE.value,
                        summary = (
                            f"Candidate rescheduled the interview with new panelist {new_panelist.name}. "
                            f"\nNew schedule: {format_interview_schedule(new_slot.slot_start, new_slot.slot_end, round_config.timezone)}"
                        ),
                        details={
                            "old_slot_id": str(booked_slot.id),
                            "old_slot_start": booked_slot.slot_start.isoformat(),
                            "old_slot_end": booked_slot.slot_end.isoformat(),
                            "old_panelist_email": old_panelist.email,
                            "new_slot_id": str(new_slot.id),
                            "new_slot_start": new_slot.slot_start.isoformat(),
                            "new_slot_end": new_slot.slot_end.isoformat(),
                            "new_panelist_email": new_panelist.email,
                        },
                    )
                    

                               
                    # Notify new panelist about the reschedule and new booking
                    tasks.append( self.panel_email_service.send_booking_confirmation_to_panelist(
                        PanelistBookingData(
                        panelist_email=new_panelist.email,
                        panelist_name=new_panelist.name,
                        candidate_name=candidate_display,
                        interview_round_title=round_config.title,
                        scheduled_start=new_slot.slot_start,
                        scheduled_end=new_slot.slot_end,
                        meet_link=meet_link,
                        reschedule_link=panelist_reschedule_link
                        )
                    ))
                else:                     
                    await self.interview_event_repository.create_interview_event(
                        interview_id=str(interview.id),
                        event_type=InterviewEventType.Interview_Rescheduled.value,
                        actor=InterviewEventActor.CANDIDATE.value,
                       summary = (
                            f"Candidate rescheduled the interview with panelist {new_panelist.name}. "
                            f"\nNew schedule: {format_interview_schedule(new_slot.slot_start, new_slot.slot_end, round_config.timezone)}"
                        ),
                        details={
                            "old_slot_id": str(booked_slot.id),
                            "old_slot_start": booked_slot.slot_start.isoformat(),
                            "old_slot_end": booked_slot.slot_end.isoformat(),
                            "new_slot_id": str(new_slot.id),
                            "new_slot_start": new_slot.slot_start.isoformat(),
                            "new_slot_end": new_slot.slot_end.isoformat(),
                        },
                    )
                    
                    
                    # sending reschuduled email to the same panelist if the panelist is same for old slot and new slot because of the time change 
                    tasks.append( self.panel_email_service.send_meeting_rescheduled_email_to_panelist(
                        PanelistMeetingRescheduledData(
                        panelist_email=new_panelist.email,
                        panelist_name=new_panelist.name,
                        candidate_name=candidate_display,
                        interview_round_title=round_config.title,
                        old_scheduled_start=booked_slot.slot_start,
                        old_scheduled_end=booked_slot.slot_end,
                        new_scheduled_start=new_slot.slot_start,
                        new_scheduled_end=new_slot.slot_end,
                        new_meet_link=meet_link,
                        reschedule_link=panelist_reschedule_link
                    )))

            except Exception as e:
                self.logger.error(f"Failed to send panelist booking notifications: {e}")
                
                        

            if candidate_reminder_settings and candidate_reminder_settings.enabled and candidate.email:
                await self._enque_candidate_interview_reminders(candidate.email, candidate_display, candidate_reminder_settings, interview, round_config, meet_link, cand_reschedule_link,candidate,new_slot)
            
                
            if panelist_reminder_settings and panelist_reminder_settings.enabled:
                    await self._enque_panelist_interview_reminders(new_panelist, panelist_reminder_settings, interview, round_config, meet_link, candidate_display,new_slot,panelist_reschedule_link)

            if old_calendar_event_id:
            # Always delete the old calendar event to prevent confusion
                try:
                    await self._delete_calendar_event(old_calendar_event_id,old_panelist.email if old_panelist else None, provider=round_config.meeting_host_type)
                except Exception as e:
                    self.logger.error(f"Failed to delete old calendar event with id {old_calendar_event_id}: {e}")
            
            await self.db.commit()
            
            if tasks:
                try:
                    await asyncio.gather(*tasks, return_exceptions=True)
                except Exception as e:
                    self.logger.error(f"Error sending reschedule notification emails: {e}")



            return {
                "status": "booked",
                "scheduled_start": new_slot.slot_start.isoformat(),
                "scheduled_end": new_slot.slot_end.isoformat(),
                "meet_link": meet_link,
                "panelist_email": new_panelist.email,
            }
        
        except DomainError:
            raise
        
        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Error rescheduling to new slot: {e}")
            raise DomainError("An error occurred while rescheduling your slot. Please try again.")
        



    async def request_for_slots(self, token: str):
        """
        Allow candidate to request for new slots if they are not happy with the currently available slots. This will notify the recruiter to add more slots or make necessary changes.
        """
        try:
            token = token.replace("Bearer ", "")
            payload = self._validate_token(token)
            interview_id = payload["interview_id"]

            interview, round_config = await self._load_interview_and_config(interview_id)

            if interview.rescheduling_token != token and interview.booking_token != token:
                raise DomainError("Invalid or outdated booking link", status_code=400)

            config = await self.interview_round_config_repository.get_interview_round_config_by_id(str(interview.round_config_id))
            
            if not config:
                raise DomainError("Interview round configuration not found", status_code=404)

                
            # Ask Panelist for new slots 
            remaining_seconds = (round_config.end_date - datetime.now(timezone.utc)).total_seconds()

            if remaining_seconds <= 0:
                raise DomainError("Round already expired")

            token_expiry_in_min = max(1, int(remaining_seconds // 60))
            
            
            panelist_not_requested = await self.panelist_repository.get_panelists_not_pending(round_config.id)

            if not panelist_not_requested:
                raise DomainError(
                    "All panelists have already been requested for availability, wait for them to respond or contact your recruiter for assistance."
                )
                
            await self.interview_event_repository.create_interview_event(
                interview_id=str(interview.id),
                event_type=InterviewEventType.Candidate_Requested_New_Slots.value,
                actor=InterviewEventActor.CANDIDATE.value,
                summary=(f"Notifying {len(panelist_not_requested)} panelists for availability."),
                details={
                    "panelist_emails": [p.email for p in panelist_not_requested],
                    "info":"Thsese panelist are requested for availability as candidate requested for new slots",
                },
            )
            
            panelists = await self.panelist_repository.request_panelist_for_availability(round_config.id,token_expiry_in_min)
            job_settings = await self.job_repository.get_job_settings(config.job_id) 
            
            
            panelist_reminder_settings = ReminderSettingsDTO.model_validate(job_settings.panel_reminders) if job_settings and job_settings.panel_reminders else None
            
            if panelist_reminder_settings and panelist_reminder_settings.enabled and panelist_reminder_settings.form_reminder_hours:
                reminders_payload = await self._create_form_reminder_payload_for_panelist(panelists, config, panelist_reminder_settings) if panelist_reminder_settings and panelist_reminder_settings.enabled else []
                
                if reminders_payload:
                    reminders = await self.reminder_repository.create_reminders(reminders_payload)
                    
                    reminder_map = {str(r.id): r for r in reminders}
                    enqueue_payloads = [EnqueueReminderPayload(reminder_id=r.id,run_at=r.next_run_at)for r in reminders]
                    enqueue_results = await self.email_producer.enqueue_reminder_email_task(enqueue_payloads)

                    for res in enqueue_results:
                        if res.status == "success":
                            reminder_map[str(res.reminder_id)].worker_job_id = res.job_id 
            
            await self.db.commit()
            
                
            # TODO: Enque email sending task if many panelists to avoid delays in response
            tasks = [
                self.panel_email_service.send_slot_availability_email(
                    AvailableSlotsData(   
                    panelist_email=panelist.email,
                    panelist_name=panelist.name,
                    interview_round_title=round_config.title,
                    form_link=f"{self.frontend_url}/panelist/availability?token={panelist.availability_token}",
                    )
                )
                for panelist in panelists
            ]

            await asyncio.gather(*tasks, return_exceptions=True)

            
            return 
        except DomainError:
            raise

        except Exception as e:
            self.logger.error(f"Error requesting new slots: {e}")
            raise DomainError("An error occurred while requesting new slots. Please try again.")

    async def get_interview_details(self, application_id: str):
        """Fetch interview details along with timeline events."""

        application = await self.application_repository.get_application_by_id(application_id)
        if not application:
            raise DomainError("Application not found for the given ID", status_code=404)

        if application.current_round == 0:
            raise DomainError("No interview scheduled yet for this application", status_code=404)

        interviews = await self.interview_repository.get_interviews_with_details_and_le_round_number(
            application_id,
            application.current_round
        )
        
        data = {
            "current_round": None,
            "past_rounds": []
        }

        for interview in interviews:

            interview_data = {
                "interview": {
                    "id": str(interview.id),
                    "round_number": interview.round_number,
                    "status": interview.status.value,
                    "is_complete": interview.status == InterviewStatus.COMPLETED,
                    # ! the interview may change as hr can change the round configuration after the interview is scheduled but before the interview is conducted so we need to handle the case when round config is not same as the interview round config at the time of scheduling and also handle the case when round config is deleted after scheduling
                    "interview_type": interview.round_config.interview_type.value if interview.round_config and interview.round_config.interview_type else None,
                    "meet_link": interview.meet_link if interview.status == InterviewStatus.SCHEDULED else None,
                    "scheduled_at": format_interview_schedule(interview.scheduled_start, interview.scheduled_end, interview.round_config.timezone) if interview.scheduled_start and interview.scheduled_end else None,
                    "notes": None,
                    "summary": interview.ai_summary if interview.ai_summary else None,
                    "is_transcript_available": bool(interview.transcript_url)
                    
                },
                "round_config": {
                    "title": interview.round_config.title,
                    "duration_minutes": interview.round_config.duration_minutes
                },
                "timeline_events": [
                    {
                        "actor": e.actor,
                        "event_type": e.event_type,
                        "summary": e.summary,
                        "created_at": e.created_at
                    }
                    for e in interview.events
                ]
            }

            if interview.round_number == application.current_round:
                data["current_round"] = interview_data
            else:
                data["past_rounds"].append(interview_data)

        return data
    

    async def download_interview_transcript(self, interview_id: str):
        """Allow authorized users to download the transcript of an interview."""

        interview = await self.interview_repository.get_interview_by_id(interview_id)

        if not interview:
            raise DomainError("Interview not found for the given ID", status_code=404)

        if not interview.transcript_url:
            raise DomainError("Transcript not available for this interview", status_code=404)
        round_config = await self.interview_round_config_repository.get_interview_round_config_by_id(str(interview.round_config_id))
        # TEMP transcript
        from data.transcript import load_transcript
        from src.utils.templte_engine import render_template


        transcript = await self.supabase_file_handler.get_json_data_from_file_on_supabase(interview.transcript_url) 

        if not transcript:
            raise DomainError("Transcript not available for this interview", status_code=404)

        transcript = self._normalize_transcript(transcript)
        transcript["title"] = f"{round_config.title if round_config and round_config.title else "Interview"}-{interview.id}-Transcript"
        # ✅ Render HTML
        html_content = render_template(
            "transcript/transcript.html",
            {
                "transcript": transcript,
            }
        )

        # ✅ Generate PDF using HTML (FIXED)
        pdf_path = self._generate_pdf_from_html(html_content)

        return pdf_path