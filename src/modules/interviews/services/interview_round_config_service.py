from sqlalchemy.ext.asyncio import AsyncSession
from  configs.log_config import get_logger
from configs.env_config import FRONTEND_URL
from src.services.errors.base import DomainError
from src.modules.interviews.dtos.interview_round_config_dto import CreateInterviewRoundConfigDTO, UpdateInterviewRoundConfigDTO, BulkCreateInterviewRoundConfigDTO
from src.modules.interviews.repositories.interview_event_repository import InterviewEventRepository
from src.modules.interviews.repositories.panelist_repository import PanelistRepository
from src.modules.interviews.repositories.interview_round_configs_repository import InterviewRoundConfigsRepository
from src.repositories.job_repository import JobRepository
from src.modules.notifications.notification_dispatcher import NotificationDispatcher
from datetime import datetime, timezone
from uuid import UUID
from src.utils.time_helper import format_time_according_to_timezone
from src.dtos.job_settings_dto import ReminderSettingsDTO,ReschedulingSettingsDTO
from src.dtos.notification_dto import Email_Template_Keys
from src.modules.reminders.reminder_dtos import CreateReminderDTO
from src.dtos.emails.panel_dto import PanelistReminderAvailabilityData
from src.modules.reminders.model.reminder_enum import ReminderType, RecipientType, EntityType
from datetime import timedelta
from src.modules.interviews.services.helpers.interview_reminder import (
    build_panelist_form_reminder_payloads,
    build_candidate_form_reminder_payloads,
    build_candidate_interview_reminder_payloads,
    build_panelist_interview_reminder_payloads,
    build_panelist_slot_availability_notifications,
)


class InterviewRoundConfigService:
    def __init__(self, 
        
        interview_round_config_repository:InterviewRoundConfigsRepository,
        interview_event_repository:InterviewEventRepository,
        panelist_repository: PanelistRepository,
        job_repository: JobRepository,
        notification_dispatcher: NotificationDispatcher,
        db: AsyncSession):
        
        
        self.db = db
        self.interview_event_repository = interview_event_repository
        self.interview_round_config_repository = interview_round_config_repository
        self.panelist_repository = panelist_repository
        self.job_repository = job_repository
        self.notification_dispatcher = notification_dispatcher

        self.frontend_url = FRONTEND_URL
        self.logger = get_logger("InterviewRoundConfigService")
    
    def _get_expiry_time(self,end_date: datetime) -> int:
        """Calculate remaining time until round end and return in minutes."""
        now = datetime.now(timezone.utc)

        if end_date < now:
            raise DomainError("This round has already ended.", status_code=400)

        remaining_seconds = (end_date - now).total_seconds()

        if remaining_seconds <= 0:
            raise DomainError("Round already expired.")

        return max(1, int(remaining_seconds // 60))
        
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
                    template_key=Email_Template_Keys.FORM_REMINDER,
                    next_run_at= datetime.now(timezone.utc) + timedelta(seconds=reminder_sec)  #! for now doing in minutes, change to hours later       
                ))
                
        return reminders_payload
            
    async def create_interview_round_config(self, job_id: str, config_data: CreateInterviewRoundConfigDTO):
        try:
            
            existing_config = await self.interview_round_config_repository.get_interview_round_config_by_job_and_round(job_id, config_data.round_number)
            
            if existing_config:
                raise DomainError(f"Round number {config_data.round_number} already exists for this job.", status_code=400)
            
            interview_round_config = await self.interview_round_config_repository.create_interview_round_config(job_id, config_data)
            await self.db.commit()
            return interview_round_config
        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Error creating interview round config for job {job_id}: {str(e)}")
            raise 

    # TODO: Opptimization needed
    async def bulk_create_interview_round_configs(self, data: BulkCreateInterviewRoundConfigDTO):
        """Create all rounds for a job in a single transaction."""
        job_id = data.job_id
        try:
            # Check for duplicate round numbers within the request
            round_numbers = [r.round_number for r in data.rounds]
            if len(round_numbers) != len(set(round_numbers)):
                raise DomainError("Duplicate round numbers in request.", status_code=400)

            # Check none of these round numbers already exist for this job
            existing = await self.interview_round_config_repository.get_interview_round_configs_by_job(job_id)
            existing_numbers = {c.round_number for c in existing}
            conflicts = existing_numbers & set(round_numbers)
            if conflicts:
                raise DomainError(
                    f"Round number(s) {sorted(conflicts)} already exist for this job.",
                    status_code=400,
                )
            job_settings = await self.job_repository.get_job_settings(data.job_id) 
            
            if not job_settings:
                raise DomainError("Job settings not found for the job.", status_code=404)
            
            created_rounds = await self.interview_round_config_repository.bulk_create_interview_round_configs(job_id, data.rounds)

            pending_reminder_dispatches = []
            pending_notification_dispatches = []

            for created_row in created_rounds:
                panelist_ids = [panel.id for panel in created_row.panelists]
                expiry_time = self._get_expiry_time(created_row.end_date)
                if panelist_ids:
                    result = await self.panelist_repository.request_panelist_ids_for_availability(
                            created_row.id,
                            panelist_ids,
                            token_expiry_in_min=expiry_time
                        )
                    panelists = result["requested_panelists"]

                    if panelists:
                        notification_payloads = build_panelist_slot_availability_notifications(
                            panelists, created_row, self.frontend_url
                        )
                        prepared_notifications = await self.notification_dispatcher.prepare_notifications(notification_payloads)
                        pending_notification_dispatches.append(prepared_notifications)

                        panelist_reminder_settings = ReminderSettingsDTO.model_validate(job_settings.panel_reminders) if job_settings and job_settings.panel_reminders else None
                        reminders_payload = self._create_form_reminder_payload_for_panelist(panelists, created_row, panelist_reminder_settings) if panelist_reminder_settings and panelist_reminder_settings.enabled else []

                        prepared_reminders = await self.notification_dispatcher.prepare_reminders(reminders_payload)
                        pending_reminder_dispatches.append(prepared_reminders)

            await self.db.commit()

            for reminders in pending_reminder_dispatches:
                await self.notification_dispatcher.dispatch_reminders(reminders)
            for notifications in pending_notification_dispatches:
                await self.notification_dispatcher.dispatch_notifications(notifications)

            self.logger.info(f"Bulk created {len(created_rounds)} round configs for job {job_id}")
            return created_rounds
        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Error bulk creating round configs for job {job_id}: {str(e)}")
            raise
    
    
    async def get_intervew_round_config_overview_by_job(self, job_id: str):

        try:
            rows = await self.interview_round_config_repository.get_interview_round_configs_by_job_with_panelist_count(job_id)

            overview = []

            for row in rows:
                overview.append({
                    "round_config_id": row.id,
                    "round_number": row.round_number,
                    "title": row.title,
                    "start_date": row.start_date.isoformat(),
                    "end_date": row.end_date.isoformat(),
                    "is_slots_available": row.slots_available,
                    "interview_type": row.interview_type,
                    "panelists_count": row.panelists_count,
                })

            return overview

        except Exception as e:
            self.logger.error(
                f"Error fetching interview round config overview for job {job_id}: {str(e)}"
            )
            raise
       

        
    async def get_interview_round_config_by_id(self, round_config_id: str):
        try:
            config = await self.interview_round_config_repository.get_interview_round_config_by_id_with_panelist(round_config_id)
            if not config:
                raise DomainError("Interview round configuration not found.", status_code=404)
            # config.panel_mode = 
            return config
        except Exception as e:
            self.logger.error(f"Error fetching interview round config {round_config_id}: {str(e)}")
            raise


    async def delete_interview_round_config_by_id(self, round_config_id: str):
        try:
            config = await self.interview_round_config_repository.get_interview_round_config_by_id(round_config_id)
            if not config:
                raise DomainError("Interview round configuration not found.", status_code=404)

            await self.interview_round_config_repository.delete_interview_round_config(round_config_id)
            await self.db.commit()
            return {"message": "Interview round configuration deleted successfully."}
        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Error deleting interview round config {round_config_id}: {str(e)}")
            raise
    
    
    # TODO: Make it transcational safe
    async def update_interview_round_config(
        self,
        round_config_id: str,
        config_data: UpdateInterviewRoundConfigDTO
    ):
        """Update interview round config and manage panelists in a single transaction."""
        try:
            prepared_reminders = []
            config = await self.interview_round_config_repository.get_interview_round_config_by_id_with_panelist(round_config_id)

            if not config:
                raise DomainError("Interview round configuration not found.", status_code=404)

            job_settings = await self.job_repository.get_job_settings(config.job_id)

            if not job_settings:
                raise DomainError("Job settings not found for the job.", status_code=404)


            panelists = config_data.panelists  # ✅ keep as DTO objects
            update_data = config_data.model_dump(exclude_none=True, exclude={"panelists"})

            # ✅ Update fields first
            for field, value in update_data.items():
                if hasattr(config, field):
                    setattr(config, field, value)
                    
                    
            new_panelists = []
            reminder_cancelled_panelist_ids = [] #! TODO: Handle This
            if panelists is not None:
                if panelists.add:
                    new_panelists = await self.panelist_repository.bulk_add_panelist_to_round_config(round_config_id, panelists.add)
                    

                if panelists.edit:
                    await self.panelist_repository.bulk_update_panelists(round_config_id,panelists.edit)
                    
                    reminder_cancelled_panelist_ids.extend([p.id for p in panelists.edit if p.id])  # Collect IDs of updated panelists
                    
                if panelists.delete:
                    print("Deleting panelists with ids:", panelists.delete)
                    await self.panelist_repository.delete_panelists_by_ids(round_config_id,panelists.delete)
                   
                    reminder_cancelled_panelist_ids += panelists.delete  # Collect IDs of deleted panelists
            
            await self.db.flush() # ✅ Flush to get updated config and new panelists in the session
            
            await self.db.refresh(config, ["panelists"]) # ✅ Refresh to ensure we have the latest state of config and panelists
            
            panelist_ids = [panel.id for panel in config.panelists]
            print("\nCurrent panelist ids after update:", panelist_ids,"\n\n")
            expiry_time = self._get_expiry_time(config.end_date)
            
            prepared_notifications = []
            if panelist_ids:
                result = await self.panelist_repository.request_panelist_ids_for_availability(
                        config.id,
                        panelist_ids,
                        token_expiry_in_min=expiry_time
                    )
                requested_panelists = result["requested_panelists"]

                if requested_panelists:
                    notification_payloads = build_panelist_slot_availability_notifications(
                        requested_panelists, config, self.frontend_url
                    )
                    prepared_notifications = await self.notification_dispatcher.prepare_notifications(notification_payloads)

                    panelist_reminder_settings = ReminderSettingsDTO.model_validate(job_settings.panel_reminders) if job_settings and job_settings.panel_reminders else None
                    reminders_payload = self._create_form_reminder_payload_for_panelist(requested_panelists, config, panelist_reminder_settings) if panelist_reminder_settings and panelist_reminder_settings.enabled else []

                    prepared_reminders = await self.notification_dispatcher.prepare_reminders(reminders_payload)

            # ✅ Commit once
            await self.db.commit()
            await self.db.refresh(config)

            if prepared_reminders:
                await self.notification_dispatcher.dispatch_reminders(prepared_reminders)
            if prepared_notifications:
                await self.notification_dispatcher.dispatch_notifications(prepared_notifications)

            return config

        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Error updating interview round config {round_config_id}: {str(e)}")
            raise
             
    async def get_interview_round_configs_by_job(self, job_id: str):
        try:
            configs = await self.interview_round_config_repository.get_interview_round_configs_by_job(job_id)
            return configs
        except Exception as e:
            self.logger.error(f"Error fetching interview round configs for job {job_id}: {str(e)}")
            raise 
        
        
    async def request_all_panelist_for_slots(self, round_config_id: str):
        try:
            config = await self.interview_round_config_repository.get_interview_round_config_by_id(round_config_id)
            if not config:
                raise DomainError("Interview round configuration not found.", status_code=404)

            if config.end_date < datetime.now(timezone.utc):
                raise DomainError("This Round has already ended", status_code=400)

            # Ask Panelist for new slots 
            remaining_seconds = (config.end_date - datetime.now(timezone.utc)).total_seconds()

            if remaining_seconds <= 0:
                raise DomainError("Round already expired")

            token_expiry_in_min = max(1, int(remaining_seconds // 60)) 
            requested_panelist = await self.panelist_repository.request_panelist_for_availability(round_config_id, token_expiry_in_min)
            
            if len(requested_panelist) == 0:
                return "All panelists have already been requested and are in pending state."
             
            job_settings = await self.job_repository.get_job_settings(config.job_id)
            panelist_reminder_settings = ReminderSettingsDTO.model_validate(job_settings.panel_reminders) if job_settings and job_settings.panel_reminders else None
            reminders_payload = self._create_form_reminder_payload_for_panelist(requested_panelist, config, panelist_reminder_settings) if panelist_reminder_settings and panelist_reminder_settings.enabled else []

            prepared_reminders = await self.notification_dispatcher.prepare_reminders(reminders_payload)

            notification_payloads = build_panelist_slot_availability_notifications(
                requested_panelist, config, self.frontend_url
            )
            prepared_notifications = await self.notification_dispatcher.prepare_notifications(notification_payloads)

            await self.db.commit()

            if prepared_reminders:
                await self.notification_dispatcher.dispatch_reminders(prepared_reminders)
            if prepared_notifications:
                await self.notification_dispatcher.dispatch_notifications(prepared_notifications)

            return f"Availability requests sent to panelists {len(requested_panelist)}."
                            
        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Error requesting panelist availability for round config {round_config_id}: {str(e)}")
            raise
        
    async def request_panelists_for_slots(
        self,
        round_config_id: str,
        panelist_ids: list[str]
    ):

        try:
            config = await self.interview_round_config_repository.get_interview_round_config_by_id(
                round_config_id
            )

            if not config:
                raise DomainError("Interview round configuration not found.", status_code=404)

            now = datetime.now(timezone.utc)

            if config.end_date < now:
                raise DomainError("This round has already ended.", status_code=400)

            remaining_seconds = (config.end_date - now).total_seconds()

            if remaining_seconds <= 0:
                raise DomainError("Round already expired.")

            token_expiry_in_min = max(1, int(remaining_seconds // 60))

            result = await self.panelist_repository.request_panelist_ids_for_availability(
                round_config_id,
                panelist_ids,
                token_expiry_in_min
            )

            requested_panelists = result["requested_panelists"]
            already_pending_ids = result["already_pending_ids"]
            invalid_ids = result["invalid_ids"]
            
            job_settings = await self.job_repository.get_job_settings(config.job_id)
            panelist_reminder_settings = ReminderSettingsDTO.model_validate(job_settings.panel_reminders) if job_settings and job_settings.panel_reminders else None
            reminders_payload =  self._create_form_reminder_payload_for_panelist(requested_panelists, config, panelist_reminder_settings) if panelist_reminder_settings and panelist_reminder_settings.enabled else []

            prepared_reminders = await self.notification_dispatcher.prepare_reminders(reminders_payload)

            notification_payloads = build_panelist_slot_availability_notifications(
                requested_panelists, config, self.frontend_url
            )
            prepared_notifications = await self.notification_dispatcher.prepare_notifications(notification_payloads)

            await self.db.commit()

            if prepared_reminders:
                await self.notification_dispatcher.dispatch_reminders(prepared_reminders)
            if prepared_notifications:
                await self.notification_dispatcher.dispatch_notifications(prepared_notifications)

            return {
                "message": f"Availability requests sent to {len(requested_panelists)} panelists.",
                "requested_panelist_ids": [str(p.id) for p in requested_panelists],
                "already_pending_ids": already_pending_ids,
                "invalid_panelist_ids": invalid_ids
            }

        except Exception as e:
            await self.db.rollback()
            self.logger.error(
                f"Error requesting panelist availability for round config {round_config_id}: {str(e)}"
            )
            raise
        
    async def get_round_slots(self, round_config_id: str | UUID):
        try:
            config = await self.interview_round_config_repository.get_interview_round_config_by_id(round_config_id)
            if not config:
                raise DomainError("Interview round configuration not found.", status_code=404)

            panelists_list = await self.panelist_repository.get_panelists_by_round_config_id_with_slots(round_config_id)

            data = []

            for panelist in panelists_list:
                data.append({
                    "id": str(panelist.id),
                    "name": panelist.name,
                    "role": panelist.role,
                    "response_status": panelist.response_status.value if panelist.response_status else None,
                    "last_requested_at": panelist.last_requested_at.isoformat() if panelist.last_requested_at else None,
                    "times_requested": panelist.availability_request_count or 0,
                    "is_calendar_connected": panelist.calendar_connected,
                    "available_slots": [
                        {
                            "start_time": slot.slot_start.isoformat(),
                            "end_time": slot.slot_end.isoformat(),
                            "is_booked": slot.is_booked
                        }
                        for slot in panelist.slots
                    ]
                })

            return {
                "round_data": {
                    "title": config.title,
                    "round_number": config.round_number,
                    "timezone": config.timezone,
                    "start_date": config.start_date.isoformat(),
                    "end_date": config.end_date.isoformat(),
                    "interview_type": config.interview_type.value if config.interview_type else None,
                    "duration_minutes": config.duration_minutes,
                },
                "panelists": data
            }

        except Exception as e:
            self.logger.error(f"Error fetching round slots for round config {round_config_id}: {str(e)}")
            raise