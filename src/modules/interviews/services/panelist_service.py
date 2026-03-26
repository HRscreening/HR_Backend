from sqlalchemy.ext.asyncio import AsyncSession
from  configs.log_config import get_logger
from src.services.errors.base import DomainError


from src.modules.interviews.repositories import InterviewRepository,PanelistRepository,InterviewRoundConfigsRepository,InterviewSlotsRepository,InterviewEventRepository,CalendarRepository
from src.modules.interviews.services.slot_computation_service import SlotComputationService
from src.modules.interviews.services.calendar_service import CalendarService

from src.models.enums import PanelistResponseStatus, PanelMode, CalendarProvider,MeetingHostType,InterviewEventActor,InterviewEventType,InterviewStatus
from src.models import Interview_Slot
from datetime import datetime, timezone, timedelta
from configs.env_config import FRONTEND_URL,COMPANY_EMAIL,FireFlies_Bot
from src.repositories.application_repository import ApplicationRepository

from src.modules.email_services.services import PanelEmailService, CandidateEmailService
from collections import defaultdict

from src.modules.interviews.dtos.interviews_dto import MeetingDetails, Reminders
from src.modules.interviews.dtos.panel_dto import AvailableSlot,EditSlotsPayload,RescheduleSlotsPayload
from src.repositories.job_repository import JobRepository
from email_workers_async.email_tasks_producer import EmailProducer,EnqueueReminderPayload
from src.modules.reminders.reminder_repository import ReminderRepository

from datetime import datetime, timezone, date
from uuid import UUID
from typing import Optional
from src.utils.time_helper import format_interview_time, format_interview_schedule,serialize_datetime
from src.utils.jwt import JWTService
import asyncio
from src.dtos.job_settings_dto import ReminderSettingsDTO,ReschedulingSettingsDTO
from src.modules.reminders.reminder_dtos import CreateReminderDTO
from src.dtos.emails.panel_dto import PanelistReminderAvailabilityData,PanelistInterviewReminderData,PanelistBookingData,AvailableSlotsData,ThankYouPanelistData,PanelistSlotReleasedData,PanelistMeetingRescheduledData
from src.dtos.emails.candidate_dto import CandidateBookingLinkReminderData,CandidateInterviewReminderData,CandidateBookingLinkData,CandidateBookingConfirmationData,CandidateRescheduleNewSlotsData
from src.modules.reminders.model.reminder_enum import ReminderType, RecipientType, EntityType,ReminderStatus
from datetime import timedelta


# Most of the methods needs optimization,but basic functionality is ready. Will iterate and optimize in next passes. 


def get_current_utc_time():
    return datetime.now(timezone.utc)



class PanelistService:
    def __init__(self, 
        interview_round_config_repository:InterviewRoundConfigsRepository,
        interview_event_repository:InterviewEventRepository,
        interview_repository:InterviewRepository,
        panelist_repository:PanelistRepository,
        slots_repository:InterviewSlotsRepository,
        calendar_repository: CalendarRepository,
        application_repository:ApplicationRepository,
        calendar_service: CalendarService,
        panel_email_service: PanelEmailService,
        candidate_email_service: CandidateEmailService,
        job_repository: JobRepository,
        email_producer: EmailProducer,
        reminder_repository: ReminderRepository,
        db: AsyncSession):
        
        
        self.db = db
        self.frontend_url = FRONTEND_URL
        self.interview_event_repository = interview_event_repository 
        self.interview_round_config_repository = interview_round_config_repository
        self.interview_repository = interview_repository
        self.panelist_repository = panelist_repository
        self.slots_repository = slots_repository
        self.calendar_repository = calendar_repository
        self.application_repository = application_repository
        self.calendar_service = calendar_service
        self.panel_email_service : PanelEmailService = panel_email_service
        self.candidate_email_service : CandidateEmailService = candidate_email_service
        self.jwt_service : JWTService = JWTService()
        self.job_repository = job_repository
        self.email_producer = email_producer
        self.reminder_repository = reminder_repository
        self.logger = get_logger("PanelistService") 
    
    def _validate_and_extract_token_payload(
        self,
        availability_token: str
    ) -> tuple[str, str,str]:

        self.logger.info(f"Validating availability token: {availability_token}")    
        payload = self.jwt_service.decode_token(availability_token)


        panelist_id = payload.get("panelist_id",None)
        round_config_id = payload.get("round_config_id",None)
        token_type = payload.get("token_type",None)

        if not panelist_id or not round_config_id or not token_type :
            raise DomainError(
                "Invalid token payload.",
                status_code=400
            )
        
        return panelist_id, round_config_id,token_type
    
    def _validate_and_extract_reschedule_token_payload(
        self,
        reschedule_token: str
    ) -> tuple[str, str,str]:

        payload = self.jwt_service.decode_token(reschedule_token)


        interview_id = payload.get("interview_id",None)
        round_config_id = payload.get("round_config_id",None)
        panelist_id = payload.get("panelist_id",None)

        if not panelist_id or not interview_id or not round_config_id:
            raise DomainError(
                "Invalid token payload.",
                status_code=400
            )
        
        return panelist_id, round_config_id , interview_id
    
    def _check_panelist_form_open(self, round_config, panelist):

        
        # if panelist.response_status == PanelistResponseStatus.SUBMITTED:
        #     return {
        #         "status": "submitted",
        #         "message": "You have already submitted your availability. Thank you!",
        #     }
            
        now = get_current_utc_time()
        if panelist.token_expires_at and panelist.token_expires_at < now:
            return {
                "status": "expired",
                "message": "Your availability submission link has expired. Please contact HR to resend the link.",
            }


        if now > round_config.end_date:
            return {
                "status": "closed",
                "message": "The availability submission period for this interview round has ended.",
            }
        
        # ! Allowing early submissions, as it can be helpful for scheduling. HR can always resend the link if needed.
        # if now < round_config.start_date:
        #     return {
        #         "status": "not_started",
        #         "message": "The availability submission period has not started yet. Please check back later.",
        #     }

        return None  # Form is open
        
    def _get_slot_computation_service(self):
        return SlotComputationService(
                slots_repo=self.slots_repository,
                round_config_repo=self.interview_round_config_repository,
                interview_repo=self.interview_repository,
                event_repo=self.interview_event_repository,
                candidate_email_service=self.candidate_email_service,
                db=self.db,
            )

    def _group_slots_by_date(self,slots: list[Interview_Slot]) -> list[dict]:
        """Group slots by local date, ordered by date then start time."""
        groups: dict[date, list[dict]] = defaultdict(list)
        
        for slot in slots:
            # Convert to local date for grouping key
            local_date = slot.slot_start.astimezone().date()
            groups[local_date].append({
                "id": str(slot.id),
                "slot_start": slot.slot_start,
                "slot_end": slot.slot_end,
                "is_booked": slot.is_booked,
                "is_expired": slot.is_expired,
            })
        
        # Sort groups by date, slots within each group by start time
        return [
            {
                "date": str(date_key),          # "2025-06-12"
                "slots": sorted(day_slots, key=lambda s: s["slot_start"]),
            }
            for date_key, day_slots in sorted(groups.items())
        ]
            
    async def _get_meet_link_for_interview(self, meeting_details: MeetingDetails, meeting_host_type:MeetingHostType,refresh_token:str) -> Optional[str]:
        """Generate a calendar event and return the meet link."""
        
        # TODO: move redundant parts from other methods to here 
            
        if meeting_host_type == MeetingHostType.HR:
                # TODO: update to create calendar event with hr calendar credential
            meet_link = await self.calendar_service.create_google_calendar_event_owner_deskzero(meeting_details)
            
            
        elif meeting_host_type == MeetingHostType.PANELIST:
            self.logger.info(f"Creating calendar event with panelist credentials for meeting hosted by panelist.")
            meet_link = await self.calendar_service.create_google_calendar_event_owner_panelist(meeting_details,refresh_token)
            
        else:
            meet_link = await self.calendar_service.create_google_calendar_event_owner_deskzero(meeting_details)
        
        return meet_link

    def _create_booking_reminder_payload_candidate(self, cand_interview_data, round_config, candidate_reminder_settings) -> list[CreateReminderDTO]:
        reminders_payload = []
        for cand in cand_interview_data:
            for reminder_sec in set(candidate_reminder_settings.form_reminder_sec):
                reminders_payload.append(CreateReminderDTO(
                    entity_id=str(round_config.id),
                    entity_type=EntityType.INTERVIEW,
                    payload=CandidateBookingLinkReminderData(
                        candidate_email=cand["candidate_email"],
                        candidate_full_name=cand["candidate_full_name"],
                        interview_round_title=round_config.title,
                        form_link=f"{self.frontend_url}/interview/book?token={cand["booking_token"]}"
                    ).model_dump(mode="json"),
                    recipient_id=str(cand["id"]),
                    recipient_type=RecipientType.CANDIDATE,
                    reminder_type=ReminderType.BOOKING_LINK,
                    next_run_at= datetime.now(timezone.utc) + timedelta(minutes=reminder_sec)  #! for now doing in minutes, change to hours later       
                ))
        return reminders_payload

       
    async def _enque_panelist_interview_reminders(self, panelist, panelist_reminder_settings: ReminderSettingsDTO, interview, config, meet_link, candidate_display,slot,panelist_reschedule_link):
        """Enqueues interview reminder emails for panelist based on their reminder settings."""
        reminders_payload = []
        for reminder_sec in panelist_reminder_settings.interview_reminder_sec:
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
            next_run_at= datetime.now(timezone.utc) + timedelta(seconds=reminder_sec)  #! for now doing in minutes, change to hours later       
        ))
            
            
        if reminders_payload:
            reminders = await self.reminder_repository.create_reminders(reminders_payload)
            enqueue_payloads = [EnqueueReminderPayload(reminder_id=r.id,run_at=r.next_run_at)for r in reminders]
            enqueue_results = await self.email_producer.enqueue_reminder_email_task(enqueue_payloads)
            
            self.logger.info(f"Enqueued {len(enqueue_payloads)} reminder emails for panelist {panelist.email}")
    
    async def _enque_candidate_interview_reminders(self, candidate_email, candidate_display, candidate_reminder_settings: ReminderSettingsDTO, interview, config, meet_link, cand_reschedule_link,candidate,slot):
        reminders_payload = []
        for reminder_sec in candidate_reminder_settings.interview_reminder_sec:
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
            next_run_at= datetime.now(timezone.utc) + timedelta(seconds=reminder_sec)  #! for now doing in minutes, change to hours later       
        ))
            
            
        if reminders_payload:
            reminders = await self.reminder_repository.create_reminders(reminders_payload)
            enqueue_payloads = [EnqueueReminderPayload(reminder_id=r.id,run_at=r.next_run_at)for r in reminders]
            enqueue_results = await self.email_producer.enqueue_reminder_email_task(enqueue_payloads)
            
            self.logger.info(f"Enqueued {len(enqueue_payloads)} reminder emails for candidate {candidate_display} ")
    
          
            
    # TODO: Mark Panels Token Expired while checking JWT
    async def get_panelist_form_details(self, availability_token: str):

        availability_token = availability_token.replace("Bearer ", "")
        
        panelist_id, round_config_id,token_type = self._validate_and_extract_token_payload(availability_token)

        print(f"Extracted from token - panelist_id: {panelist_id}, round_config_id: {round_config_id}, token_type: {token_type}")
        round_config = await self.interview_round_config_repository.get_interview_round_config_by_id(round_config_id)

        if not round_config:
            raise DomainError(
                "Interview round configuration not found for the provided token"
            )

        panelist = await self.panelist_repository.get_panelist_by_round_config_and_panelist_id(
            round_config_id=round_config.id,
            panelist_id=panelist_id,
        )

        if not panelist:
            raise DomainError("Panelist not found for the provided token")
        
        if str(panelist.round_config_id) != str(round_config_id):
            raise DomainError("Panelist does not belong to the interview round configuration in the token")
        
        if token_type == "create" and panelist.availability_token != availability_token:
            raise DomainError(
                "Invalid or outdated availability link.",
                status_code=400
            )
            
        if token_type == "edit" and panelist.edit_token != availability_token:
            raise DomainError(
                "Invalid or outdated availability link.",
                status_code=400
            )
                
        # ⭐ Check if form is open
        status_response = self._check_panelist_form_open(
            round_config,
            panelist,
        )

        if status_response:
            return status_response
        
        
        # TODO : Add this also later
        # if round_config.Panel_owner:
        
        
        
        if round_config.meeting_host_type == MeetingHostType.PANELIST:
            # TODO : Remove or condn after making default calendar provider dynamic
            calendar_connection = await self.calendar_repository.get_calendar_connection_by_email_and_provider(
                provider_email=panelist.email,provider= CalendarProvider.GOOGLE
                )
            
            now = get_current_utc_time()
            # TODO: Handle case when calendar token is expired, currently we are just treating it as no calendar connection, but we can also have a separate status for expired calendar token which will prompt panelist to reconnect their calendar.
            if not calendar_connection or calendar_connection.token_expires_at < now:
                return {
                    "status": "no_calendar",
                    "provider": CalendarProvider.GOOGLE, # should fetch from round_config.calendar_provider, but currenltly config have no such field TODO: Add
                }
    
                
        all_slots = await self.slots_repository.get_slots_by_panelist_id(round_config.id, panelist.id)

        res_data = {
            "status": "open",
            "data": {
                "title": round_config.title,
                "start_date": round_config.start_date,
                "end_date": round_config.end_date,
                "duration_minutes": round_config.duration_minutes,
                "interview_type": round_config.interview_type,
            },
        }
        

        res_data["data"]["existing_slots"] = self._group_slots_by_date(all_slots)
        res_data["data"]["is_editing"] = len(all_slots) > 0  # frontend uses this to switch mode
                
                
     

        # ⭐ Form is open → return details
        return res_data



    async def get_panelist_reschedule_form_details(self, rescheduling_token: str):
        rescheduling_token = rescheduling_token.replace("Bearer ", "")
        
        panelist_id, round_config_id, interview_id = self._validate_and_extract_reschedule_token_payload(rescheduling_token)

        round_config = await self.interview_round_config_repository.get_interview_round_config_by_id(round_config_id)
        if not round_config:
            raise DomainError("Interview round configuration not found for the provided token")

        panelist = await self.panelist_repository.get_panelist_by_round_config_and_panelist_id(
            round_config_id=round_config.id,
            panelist_id=panelist_id,
        )
        if not panelist:
            raise DomainError("Panelist not found for the provided token")

        if str(panelist.round_config_id) != str(round_config_id):
            raise DomainError("Panelist does not belong to the interview round configuration in the token")

        # ! panelist reshedule token will auto expire befor that slot timing, so no need to check for token expiry separately, as we will check the slot timing in the next steps which will cover the token expiry as well.     
        # if panelist.rescheduling_token != rescheduling_token:
        #     raise DomainError("Invalid or outdated rescheduling link.", status_code=400)

        # ── Form window check ─────────────────────────────────────────────────────
        status_response = self._check_panelist_form_open(round_config, panelist)
        if status_response:
            return status_response
        if round_config.meeting_host_type == MeetingHostType.PANELIST:
            # ── Calendar check ────────────────────────────────────────────────────────
            calendar_connection = await self.calendar_repository.get_calendar_connection_by_email_and_provider(
                provider_email=panelist.email, provider=CalendarProvider.GOOGLE
            )
            now = get_current_utc_time()
            if not calendar_connection or calendar_connection.token_expires_at < now:
                return {
                    "status": "no_calendar",
                    "provider": CalendarProvider.GOOGLE.value,
                }

        # ── Slot validity checks (order matters) ──────────────────────────────────
        current_slot = await self.slots_repository.get_slot_by_interview_id_with_round_config_id_with_panelist_id(interview_id,round_config.id,panelist.id)

        if not current_slot:
            raise DomainError("Booked slot not found for this interview.", status_code=404)

        if current_slot.is_expired:
            return {
                "status": "expired",
                "message": "The current interview slot has already passed. Rescheduling is not possible.",
            }

        if not current_slot.is_booked:
            return {
                "status": "not_booked",
                "message": "The current slot is not booked. No need to reschedule.",
            }
        now = get_current_utc_time()
        if current_slot.slot_start < now + timedelta(hours=1):
            return {
                "status": "too_late",
                "message": "Rescheduling is only allowed at least 1 hour before the scheduled interview time.",
            }

        # ── Build response ────────────────────────────────────────────────────────
        all_slots = await self.slots_repository.get_slots_by_panelist_id(round_config.id, panelist.id)


        return {
            "status": "open",
            "data": {
                "title": round_config.title,
                "start_date": round_config.start_date,
                "end_date": round_config.end_date,
                "duration_minutes": round_config.duration_minutes,
                "interview_type": round_config.interview_type,
                "reschedule_slot_id": str(current_slot.id),
                "existing_slots": self._group_slots_by_date(all_slots),
            },
        }
     
    # TODO : Notify HR 
    async def submit_panelist_availability(self, availability_token: str, available_slots: list[AvailableSlot]):
        try:
            
            if not available_slots:
                raise DomainError(
                    "At least one available slot must be provided.",
                    status_code=400
                )
            
            availability_token = availability_token.replace("Bearer ", "")
            
            panelist_id, round_config_id,token_type = self._validate_and_extract_token_payload(availability_token)
            
            
            if token_type != "create":
                raise DomainError(
                    "Invalid request. This endpoint is only for initial availability submission. For editing existing availability, please use the edit endpoint.",
                    status_code=400
                )

            panelist = await self.panelist_repository.get_panelist_by_round_config_and_panelist_id(
                round_config_id=round_config_id,
                panelist_id=panelist_id,
            )
            
            if not panelist:
                raise DomainError("Panelist not found for the provided token")
            
            
            
            round_config = await self.interview_round_config_repository.get_interview_round_config_by_id(
                round_config_id=round_config_id
            )
            if not round_config:
                raise DomainError("Interview round configuration not found for the provided token")
            
            if panelist.availability_token != availability_token:
                raise DomainError(
                    "Invalid or outdated availability link.",
                    status_code=400
                )
            
            status_response = self._check_panelist_form_open(round_config, panelist)
            if status_response:
                return status_response
            
            available_slots_json = [
                    slot.model_dump(mode="json")
                    for slot in available_slots
                ]

            panelist.response_status = PanelistResponseStatus.SUBMITTED
            
            now = get_current_utc_time()
            expiry_time = round_config.end_date
            expiry_minutes = int((expiry_time - now).total_seconds() / 60)
            
            
            edit_token = self.jwt_service.create_panelist_edit_token(
                panelist_id=panelist_id,
                round_config_id=round_config_id,
                expiration_minutes=expiry_minutes, 
            )
            
            panelist.edit_token = edit_token
            panelist.edit_token_expires_at = expiry_time  # Edit token expires at the end of availability window  
            panelist.availability_token = None  # Invalidate the token after submission
            panelist.token_expires_at = None  # Clear token expiry
            
            await self.db.flush()

            
            

            # ─── Slot computation based on panel_mode ─────────────────────
            slot_computation_service = self._get_slot_computation_service()

            if round_config.panel_mode == PanelMode.SEQUENTIAL:
                # SEQUENTIAL: each panelist is independent — compute immediately
                success = await slot_computation_service.compute_single_panelist_slots(
                    round_config_id=round_config_id,
                    panelist_id=panelist_id,
                    panelist_email=panelist.email,
                    available_slots_json=available_slots_json,
                )
                if not success:
                    self.logger.warning(f"No computable slots from panelist {panelist.email} for round_config {round_config_id}")
            else:
                # PANEL: need ALL panelists before we can compute intersection
                all_panelists = await self.panelist_repository.get_all_panelists_by_round_config_id(round_config_id)
                if all(p.response_status == PanelistResponseStatus.SUBMITTED for p in all_panelists):
                    success = await slot_computation_service.compute_and_store_slots(
                        round_config_id=round_config_id,
                    )
                    if not success:
                        self.logger.warning(f"Slot computation returned no slots for round_config {round_config_id}")
                else:
                    self.logger.info(
                        f"PANEL mode: waiting for remaining panelists to submit for round_config {round_config_id}"
                    )

                        
            cand_interview_data = await self.interview_repository.send_booking_link_to_waiting_candidates(
                round_config_id=round_config_id,token_expiry_in_min=expiry_minutes
            )
            job_settings = await self.job_repository.get_job_settings(round_config.job_id) 
            candidate_reminder_settings = ReminderSettingsDTO.model_validate(job_settings.candidate_reminders) if job_settings and job_settings.candidate_reminders else None    
            reminders_payload =  self._create_booking_reminder_payload_candidate(cand_interview_data,round_config,candidate_reminder_settings) if candidate_reminder_settings and candidate_reminder_settings.enabled else []
            
            old_reminders = await self.reminder_repository.get_all_reminders_by_recipient_id_and_type(str(panelist.id),RecipientType.PANELIST,ReminderStatus.PENDING,ReminderType.BOOKING_LINK)
            
            if old_reminders:
                old_reminder_ids = [str(r.id) for r in old_reminders]
                await self.email_producer.cancel_jobs(old_reminder_ids)
                await self.reminder_repository.change_reminder_status_multi(old_reminder_ids, ReminderStatus.CANCELLED)
                
                
            if reminders_payload:
                reminders = await self.reminder_repository.create_reminders(reminders_payload)
                enqueue_payloads = [EnqueueReminderPayload(reminder_id=r.id,run_at=r.next_run_at)for r in reminders]
                enqueue_results = await self.email_producer.enqueue_reminder_email_task(enqueue_payloads)
                        
                self.logger.info(f"Enqueued {len(enqueue_payloads)} reminder emails for candidates for round_config {round_config_id}")
                
            
            self.logger.info(f"Sending booking links to {len(cand_interview_data)} waiting candidates for round_config {round_config_id}")
            await self.db.commit()
            
            await self.panel_email_service.send_thanks_for_submitting_availability_email(
                ThankYouPanelistData(
                    
                panelist_email=panelist.email,
                panelist_name=panelist.name,
                interview_round_title=round_config.title,
                edit_slots_link=f"{self.frontend_url}/panelist/edit-slots?token={edit_token}",
                validity_period=f"{round_config.end_date.astimezone().strftime('%Y-%m-%d %H:%M %Z')}",
                )
            )
            
            # Notify Waiting Candidates

            await asyncio.gather(*[
                self.candidate_email_service.send_booking_link_email(
                    CandidateBookingLinkData(
                    candidate_email=data["candidate_email"],
                    candidate_name=data["candidate_full_name"],
                    interview_round_title=round_config.title,
                    booking_link=f"{self.frontend_url}/interview/book?token={data["booking_token"]}",
                )) for data in cand_interview_data
            ])
            

            
        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Error submitting panelist availability: {str(e)}")
            raise DomainError("An error occurred while submitting your availability. Please try again later.")
    
    

    
    async def edit_panelist_availability(self, availability_token: str, payload: EditSlotsPayload):
        try:
            availability_token = availability_token.replace("Bearer ", "")
            panelist_id, round_config_id , token_type = self._validate_and_extract_token_payload(availability_token)
            panelist_uuid = UUID(panelist_id)
            
            # ! To be handled
            # if token_type != "edit":
            #     raise DomainError(
            #         "Invalid request. This endpoint is only for editing existing availability. For initial submission, please use the submit endpoint.",
            #         status_code=400
            #     )
            

            panelist = await self.panelist_repository.get_panelist_by_round_config_and_panelist_id(
                round_config_id=round_config_id,
                panelist_id=panelist_id,
            )
            if not panelist:
                raise DomainError("Panelist not found for the provided token")

            round_config = await self.interview_round_config_repository.get_interview_round_config_by_id(round_config_id)
            if not round_config:
                raise DomainError("Interview round configuration not found")

            if panelist.edit_token != availability_token and panelist.availability_token != availability_token:
                raise DomainError("Invalid or outdated availability link.", status_code=400)

            now = get_current_utc_time()
            if now > round_config.end_date:
                raise DomainError("The availability window is closed. Edits are no longer accepted.", status_code=400)

            slot_computation_service = self._get_slot_computation_service()

            # ── Deletes ───────────────────────────────────────────────────────────
            if payload.delete:
                slots = await self.slots_repository.get_slots_by_ids(payload.delete, panelist_uuid)
                booked = [s for s in slots if s.is_booked]
                if booked:
                    raise DomainError(f"{len(booked)} slot(s) are booked and cannot be deleted.", status_code=400)
                await self.slots_repository.delete_slots_by_ids(panelist.id,round_config.id,payload.delete)

            # ── Updates (delete old + recompute) ──────────────────────────────────
            if payload.update:
                slots = await self.slots_repository.get_slots_by_ids(
                    [item.id for item in payload.update], panelist_uuid
                )
                booked = [s for s in slots if s.is_booked]
                if booked:
                    raise DomainError(f"{len(booked)} slot(s) are booked and cannot be updated.", status_code=400)

                await self.slots_repository.delete_slots_by_ids(panelist.id,round_config.id,[item.id for item in payload.update])
                await slot_computation_service.compute_slots_for_new_ranges(
                    round_config_id=round_config_id,
                    panelist_id=panelist_id,
                    panelist_email=panelist.email,
                    available_slots_json=[
                        {
                            "date": str(item.slot_start.astimezone().date()),
                            "time": [{"start_time": item.slot_start.isoformat(), "end_time": item.slot_end.isoformat()}],
                        }
                        for item in payload.update
                    ],
                )

            # ── Additions ─────────────────────────────────────────────────────────
            if payload.add:
                await slot_computation_service.compute_slots_for_new_ranges(
                    round_config_id=round_config_id,
                    panelist_id=panelist_id,
                    panelist_email=panelist.email,
                    available_slots_json=[
                        {
                            "date": str(item.date),
                            "time": [{"start_time": item.slot_start.isoformat(), "end_time": item.slot_end.isoformat()}],
                        }
                        for item in payload.add
                    ],
                )
            panelist.response_status = PanelistResponseStatus.SUBMITTED  # In case they are editing before initial submission
            
            now = get_current_utc_time()
            expiry_time = round_config.end_date
            expiry_minutes = int((expiry_time - now).total_seconds() / 60)
            
            cand_interview_data = await self.interview_repository.send_booking_link_to_waiting_candidates(
                round_config_id=round_config_id,token_expiry_in_min=expiry_minutes
            )
            
            self.logger.info(f"Sending booking links to {len(cand_interview_data)} waiting candidates for round_config {round_config_id}")
            
            old_reminders = await self.reminder_repository.get_all_reminders_by_recipient_id_and_type(str(panelist.id),RecipientType.PANELIST,ReminderStatus.PENDING,ReminderType.BOOKING_LINK)
            
            if old_reminders:
                old_reminder_ids = [str(r.id) for r in old_reminders]
                await self.email_producer.cancel_jobs(old_reminder_ids)
                await self.reminder_repository.change_reminder_status_multi(old_reminder_ids, ReminderStatus.CANCELLED)
                
            
            await self.db.commit()
            
            
            await asyncio.gather(*[
                self.candidate_email_service.send_booking_link_email(
                    CandidateBookingLinkData(
                    candidate_email=data["candidate_email"],
                    candidate_name=data["candidate_full_name"],
                    interview_round_title=round_config.title,
                    booking_link=f"{self.frontend_url}/interview/book?token={data["booking_token"]}",
                )) for data in cand_interview_data
            ])
            

        except DomainError:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Error editing panelist availability: {str(e)}")
            raise DomainError("An error occurred while updating your availability. Please try again later.")
     
        
        
    async def reschedule_slots(self, rescheduling_token: str, payload: RescheduleSlotsPayload):
        """Allows panelists to reschedule a booked interview slot. Only applicable for SEQUENTIAL panel mode."""
        try:
            
            if not payload.reschedule_slot:
                raise DomainError(
                    "A new slot must be provided for rescheduling.",
                    status_code=400
                )
            
            rescheduling_token = rescheduling_token.replace("Bearer ", "")
            
            panelist_id, round_config_id , interview_id = self._validate_and_extract_reschedule_token_payload(rescheduling_token)

            round_config = await self.interview_round_config_repository.get_interview_round_config_by_id(round_config_id)

            if not round_config:
                raise DomainError(
                    "Interview round configuration not found for the provided token"
                )
                        # update the application too
            interview = await self.interview_repository.get_interview_by_id(interview_id) 
            
            if not interview:
                raise DomainError("Interview not found for the provided token")
            
            
            panelist = await self.panelist_repository.get_panelist_by_round_config_and_panelist_id(
                round_config_id=round_config.id,
                panelist_id=panelist_id,
            )

            if not panelist:
                raise DomainError("Panelist not found for the provided token")
            
            if str(panelist.round_config_id) != str(round_config_id):
                raise DomainError("Panelist does not belong to the interview round configuration in the token")
                        

            current_slot = await self.slots_repository.get_slot_by_interview_id_with_round_config_id_with_panelist_id(interview_id,round_config.id,panelist.id)
            
            if not current_slot:
                raise DomainError("Current interview slot not found for rescheduling.")
            
            if current_slot.id != payload.reschedule_slot.id:
                raise DomainError("The slot provided for rescheduling does not match the currently booked slot.")
            
            current_slot.slot_start = payload.reschedule_slot.slot_start
            current_slot.slot_end = payload.reschedule_slot.slot_end
            
            
            job_settings = await self.job_repository.get_job_settings(round_config.job_id)
            panelist_reminder_settings = ReminderSettingsDTO.model_validate(job_settings.panel_reminders) if job_settings and job_settings.panel_reminders else None
            candidate_reminder_settings = ReminderSettingsDTO.model_validate(job_settings.candidate_reminders) if job_settings and job_settings.candidate_reminders else None
            reschedule_settings = ReschedulingSettingsDTO.model_validate(job_settings.rescheduling) if job_settings and job_settings.rescheduling else None
            
            if not reschedule_settings.enabled or not reschedule_settings.panelist_rescheduling_allowed:
                raise DomainError("Panelist rescheduling is not allowed for this interview round.", status_code=403)
            now = get_current_utc_time()
            if now > current_slot.slot_start - timedelta(seconds=reschedule_settings.reschedule_window_for_panelist):
                raise DomainError(f"Rescheduling is only allowed up to {reschedule_settings.reschedule_window_for_panelist/3600} hrs before the scheduled interview time.", status_code=403)
            
            if interview.times_rescheduled_by_panelist >= reschedule_settings.max_reschedule_allowed_by_panelist:
                raise DomainError(f"You have reached the maximum number of reschedules allowed ({reschedule_settings.max_reschedule_allowed_by_panelist}).", status_code=403)

            # get existing reminders for this interview and cancel them, as the interview time is changing, we will create new reminders later in the flow with updated time.
            existing_reminders = await self.reminder_repository.get_all_reminders_by_entity_id_and_type(
                entity_id=str(interview.id),
                entity_type=EntityType.INTERVIEW,
                reminder_type=ReminderType.INTERVIEW_UPCOMING,
                status=ReminderStatus.PENDING
            )
            
            if existing_reminders:
                existing_reminder_ids = [str(r.id) for r in existing_reminders]
                try:
                    await self.email_producer.cancel_jobs(existing_reminder_ids)
                except Exception as e:
                    self.logger.error(f"Error cancelling reminder email jobs for interview {interview.id}: {str(e)}")
                    raise DomainError("An error occurred while rescheduling the interview. Please try again later.")
                
                await self.reminder_repository.change_reminder_status_multi(existing_reminder_ids, ReminderStatus.CANCELLED)
            
            
            

            
            
            
            # ! Handle reminders too.


            await self.db.flush()


            # ─── Slot computation based on panel_mode ─────────────────────
            slot_computation_service = self._get_slot_computation_service()

            if payload.add:
                await slot_computation_service.compute_slots_for_new_ranges(
                    round_config_id=round_config_id,
                    panelist_id=panelist_id,
                    panelist_email=panelist.email,
                    available_slots_json=[
                        {
                            "date": str(item.date),
                            "time": [{"start_time": item.slot_start.isoformat(), "end_time": item.slot_end.isoformat()}],
                        }
                        for item in payload.add
                    ],
                )
                

            
            application = await self.application_repository.get_application_by_interview_id(interview_id)
            
            await self.db.refresh(application, ["candidate"])
            candidate = application.candidate
            if not candidate or not candidate.email:
                raise DomainError("Candidate email not found for this application", status_code=400)

            
           

            
            
            
            #! currently creating new meeting but ideally should update will apply it later need to make db fields to store meeting id from calendar provider to update the same meeting instead of creating new one.
            attendees_emails = [COMPANY_EMAIL,FireFlies_Bot, candidate.email ]+ [panelist.email]  
                
            meeting_details = MeetingDetails(
                summary=round_config.title,
                description=f"Interview for {round_config.title}",
                location=round_config.interview_type.value if round_config.interview_type else "Online",
                start_time=current_slot.slot_start.isoformat(),
                end_time=current_slot.slot_end.isoformat(),
                timezone=round_config.timezone or "UTC",
                attendees_emails= attendees_emails,
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
            calendar_refresh_token = await self.calendar_repository.get_calendar_access_token(panelist.email,CalendarProvider.GOOGLE)
            
            if not calendar_refresh_token:
                self.logger.error(f"Calendar refresh token not found for panelist {panelist.email}, provider {CalendarProvider.GOOGLE}")
                raise DomainError("Calendar credentials not found for the panelist, cannot create calendar event", status_code=404)
            
            # ! currently using deskzero's calendar will need to update later on to hr or panel we calendar connection table to store those credential
            meet_link = await self._get_meet_link_for_interview(meeting_details, round_config.meeting_host_type,refresh_token=calendar_refresh_token)


            
            # update interview
            interview.scheduled_start = payload.reschedule_slot.slot_start
            interview.scheduled_end = payload.reschedule_slot.slot_end
            interview.meet_link = meet_link
            interview.times_rescheduled_by_panelist += 1
            # interview.status = InterviewStatus.READY_TO_BOOK

            await self.interview_event_repository.create_interview_event(
                interview_id=str(interview.id),
                event_type=InterviewEventType.Interview_Rescheduled.value,
                actor=InterviewEventActor.PANELIST.value,
                summary = (
                    f"Panelist rescheduled the interview. New time: {format_interview_time(payload.reschedule_slot.slot_start, round_config.timezone)}"
                ),
                details={"candidate_email": candidate.email},
            )
            
            

            expiry_time =  payload.reschedule_slot.slot_start - timedelta(minutes=10)
            remaining_time = int(
                (expiry_time - now).total_seconds() / 60
            )
            
            reschedule_token = self.jwt_service.create_panelist_reschedule_token(
                        panelist_id=str(panelist.id),
                        round_config_id=str(round_config.id),
                        interview_id=str(interview.id),
                        expiration_minutes=remaining_time
                    )
            
            interview.rescheduling_token = reschedule_token
            interview.rescheduling_token_expires_at = expiry_time 
            
            expiry_time = current_slot.slot_start - timedelta(minutes=10)
            remaining_time = int(
                (expiry_time - datetime.now(timezone.utc)).total_seconds() / 60
            )
            reschedule_token = self.jwt_service.create_candidate_reschedule_token(
                candidate_email=candidate.email,
                expiration_minutes=remaining_time,
                interview_id=str(interview.id)
            )
            interview.rescheduling_token = reschedule_token
            interview.rescheduling_token_expires_at = expiry_time

            panelist_reschedule_token = self.jwt_service.create_panelist_reschedule_token(
                panelist_id=str(panelist.id),
                round_config_id=str(round_config.id),
                interview_id=str(interview.id),
                expiration_minutes=remaining_time
            )
            
            if panelist_reminder_settings and panelist_reminder_settings.enabled:
                await self._enque_panelist_interview_reminders(
                    panelist=panelist,
                    panelist_reminder_settings=panelist_reminder_settings,
                    interview=interview,
                    config=round_config,
                    meet_link=meet_link,
                    candidate_display=candidate.full_name,
                    slot=payload.reschedule_slot,
                    panelist_reschedule_link=f"{self.frontend_url}/panelist/reschedule?token={panelist_reschedule_token}"
                )
                
            if candidate_reminder_settings and candidate_reminder_settings.enabled:
                await self._enque_candidate_interview_reminders(
                    candidate_email=candidate.email,
                    candidate_display=candidate.full_name,
                    candidate_reminder_settings=candidate_reminder_settings,
                    interview=interview,
                    config=round_config,
                    meet_link=meet_link,
                    cand_reschedule_link=f"{self.frontend_url}/interview/reschedule?token={reschedule_token}",
                    candidate=candidate,
                    slot=payload.reschedule_slot
                    
                )
                
            await self.db.commit()
            
            # TODO: stop candidate receiving reminders for old slot

            await self.candidate_email_service.send_interview_rescheduled_email(
                CandidateRescheduleNewSlotsData(
                    
                candidate_email=candidate.email,
                candidate_name=candidate.full_name,
                interview_round_title=round_config.title,
                reschedule_link=f"{self.frontend_url}/interview/reschedule?token={reschedule_token}",
                scheduled_start=current_slot.slot_start,
                scheduled_end=current_slot.slot_end,
                reason="The panelist has rescheduled the interview.",
                )
            )
        
            
            return {
                "message": "Interview rescheduled successfully. The candidate has been notified to pick a new slot."
            }
                
        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Error rescheduling interview: {str(e)}")
            raise DomainError("An error occurred while rescheduling the interview. Please try again later.")
