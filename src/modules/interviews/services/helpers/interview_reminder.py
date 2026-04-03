from datetime import datetime, timedelta, timezone
from src.dtos.job_settings_dto import ReminderSettingsDTO
from src.dtos.emails.panel_dto import PanelistReminderAvailabilityData,PanelistInterviewReminderData
from src.dtos.emails.candidate_dto import CandidateBookingLinkReminderData,CandidateInterviewReminderData
from src.modules.reminders.reminder_dtos import CreateReminderDTO
from src.modules.reminders.model.reminder_enum import EntityType, RecipientType, ReminderType
from configs.log_config import get_logger
from src.utils.time_helper import serialize_datetime
from workers_async.email_tasks_producer import EmailProducer,EnqueueReminderPayload
from src.modules.reminders.reminder_repository  import ReminderRepository

# TODO: Implemented later
class InterviewReminderHelper:
    def __init__(
        self,
        reminder_repository:ReminderRepository,
        email_producer:EmailProducer
                 
        ):
        
        self.reminder_repository = reminder_repository
        self.email_producer = email_producer
        self.logger = get_logger("InterviewReminderHelper")
    
    
              
    def _create_form_reminder_payload_for_panelist(self,requested_panelist,config, panelist_reminder_settings: ReminderSettingsDTO) -> list[CreateReminderDTO]:
        reminders_payload = []
        for panelist in requested_panelist:
            for reminder_sec in set(panelist_reminder_settings.form_reminder_sec):
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
                    next_run_at= datetime.now(timezone.utc) + timedelta(seconds=reminder_sec)  #! for now doing in minutes, change to hours later       
                ))
                
        return reminders_payload
    
    def _create_booking_reminder_payload_candidate(self, candidate, round_config, candidate_reminder_settings:ReminderSettingsDTO,booking_link,application_id) -> list[CreateReminderDTO]:
        reminders_payload = []
        if candidate_reminder_settings and candidate_reminder_settings.enabled and candidate_reminder_settings.form_reminder_sec:
            for reminder_sec in candidate_reminder_settings.form_reminder_sec:
                reminders_payload.append(CreateReminderDTO(
                    entity_id=str(round_config.id),
                    entity_type=EntityType.INTERVIEW,
                    payload=CandidateBookingLinkReminderData(
                        candidate_email=candidate.email,
                        candidate_name=candidate.full_name or candidate.email,
                        interview_round_title=round_config.title,
                        booking_link=booking_link
                    ).model_dump(),
                    recipient_id=str(application_id),
                    recipient_type=RecipientType.CANDIDATE,
                    reminder_type=ReminderType.BOOKING_LINK,
                    next_run_at= datetime.now(timezone.utc) + timedelta(seconds=reminder_sec)  #! for now doing in minutes, change to hours later       
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
        """Enqueues interview reminder emails for candidate based on their reminder settings."""
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
    
    