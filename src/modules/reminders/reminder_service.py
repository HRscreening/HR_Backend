from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Organization,User,Job,Rubric,Application,BulkUploadBatches

from  configs.log_config import get_logger
from typing import List
from src.services.errors.auth_errors import UserNotFound
from src.services.errors.base import DomainError

from src.modules.reminders.reminder_repository import ReminderRepository
from src.modules.reminders.reminder_dtos import CreateReminderDTO
from src.modules.notifications.notification_service import NotificationService
from src.modules.reminders.model.reminder_enum import RecipientType,EntityType,ReminderStatus,ReminderType
from src.modules.interviews.repositories.interview_event_repository import InterviewEventRepository
from src.dtos.emails.panel_dto import PanelistReminderAvailabilityData,PanelistInterviewReminderData,PanelistFeedbackData
from src.dtos.emails.candidate_dto import CandidateBookingLinkReminderData,CandidateInterviewReminderData


class BaseReminderService:
    def __init__(self,reminder_repository: ReminderRepository,interview_event_repository:InterviewEventRepository,db: AsyncSession):
        self.db = db
        self.reminder_repository = reminder_repository
        self.interview_event_repository = interview_event_repository
        self.logger = get_logger("Base_Reminder_Service")

            
    def _check_reminder_validity(self,reminder):
        """Checks if the reminder is valid for sending an email."""
        if not reminder:
                raise DomainError(message="Reminder not found for the given worker job ID", status_code=status.HTTP_404_NOT_FOUND)
            
        if reminder.status != ReminderStatus.PENDING:
            raise DomainError(message="Reminder is not in a valid state to send email", status_code=status.HTTP_400_BAD_REQUEST)
        
    


class ReminderAPIService(BaseReminderService):
    def __init__(self,reminder_repository: ReminderRepository,db: AsyncSession):
        super().__init__(reminder_repository,db)

    
    
    async def create_reminder(self, reminder_dto: List[CreateReminderDTO]) -> dict:
        """Creates reminders based on the provided DTOs."""
        try:
            reminders = await self.reminder_repository.create_reminders(reminder_dto)
            await self.db.commit()
            return {"reminders": reminders}
        except Exception as e:
            self.logger.exception("Error creating reminder")
            await self.db.rollback()
            raise DomainError(message="Failed to create reminder", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        


class ReminderWorkerService(BaseReminderService):
    def __init__(self,reminder_repository: ReminderRepository,notification_service:NotificationService,interview_event_repository:InterviewEventRepository,db: AsyncSession):
        super().__init__(reminder_repository,interview_event_repository,db)
        self.notification_service : NotificationService = notification_service


    async def send_reminder_email(self, reminder_id: str) -> dict:
        try:
            reminder = await self.reminder_repository.get_reminder_by_id(reminder_id)

            self._check_reminder_validity(reminder)

            # ✅ idempotency check
            if reminder.status == ReminderStatus.COMPLETED:
                self.logger.info(f"Reminder {reminder_id} already completed")
                return {"message": "Already sent"}

            payload_dict = reminder.payload

            if not payload_dict:
                raise ValueError(f"Payload missing for reminder {reminder_id}")

            # ✅ DTO conversion
            if reminder.recipient_type == RecipientType.PANELIST and reminder.reminder_type == ReminderType.BOOKING_LINK:
                await self.notification_service.send_form_reminder_notification_to_panelist(
                    payload=PanelistReminderAvailabilityData(**payload_dict),
                    channel="EMAIL"
                )

            elif reminder.recipient_type == RecipientType.PANELIST and reminder.reminder_type == ReminderType.INTERVIEW_UPCOMING:
                await self.notification_service.send_interview_reminder_notification_to_panelist(
                    payload=PanelistInterviewReminderData(**payload_dict),
                    channel="EMAIL"
                )
                
            elif reminder.recipient_type == RecipientType.CANDIDATE and reminder.reminder_type == ReminderType.BOOKING_LINK:
               await self.notification_service.send_form_reminder_notification_to_candidate(
                    payload=CandidateBookingLinkReminderData(**payload_dict),
                    channel="EMAIL"
                )
           
            elif reminder.recipient_type == RecipientType.CANDIDATE and reminder.reminder_type == ReminderType.INTERVIEW_UPCOMING:   
                await self.notification_service.send_interview_reminder_notification_to_candidate(
                    payload=CandidateInterviewReminderData(**payload_dict),
                    channel="EMAIL"
                )
                
            elif reminder.reminder_type == ReminderType.FEEDBACK_PENDING:
                await self.notification_service.send_feedback_reminder_notification_to_panelist(
                    payload=PanelistFeedbackData(**payload_dict),
                    channel="EMAIL"
                )

            # ✅ update state
            reminder.status = ReminderStatus.COMPLETED
            reminder.reminder_count += 1

            # TODO
            # await self.interview_event_repository.create_interview_event(
            #     interview_id=reminder.entity_id,
            #     event_type=f"{reminder.reminder_type.value}_SENT",
            #     event_details={
            #         "recipient_type": reminder.recipient_type.value,
            #         "payload": reminder.payload,
            #         "reminder_id": reminder.id
            #     }
            # )
            
            await self.db.commit()

            return {"message": "Reminder email sent successfully"}

        except Exception as e:
            self.logger.exception(f"Error for reminder {reminder_id}: {str(e)}")
            await self.db.rollback()
            raise
        
        
        
    async def mark_failed(self, reminder_id: str, error_message: str) -> dict:
        """Marks the reminder as failed in the database."""
        try:
            updated_reminder = await self.reminder_repository.mark_reminder_as_failed(reminder_id, error_message)
            if not updated_reminder:
                raise DomainError(message="Reminder not found for the given ID", status_code=status.HTTP_404_NOT_FOUND)
            await self.db.commit()
            return {"message": "Reminder marked as failed"}
        except Exception as e:
            self.logger.exception(f"Error marking reminder as failed for ID: {reminder_id}")
            await self.db.rollback()
            raise DomainError(message="Failed to mark reminder as failed", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)