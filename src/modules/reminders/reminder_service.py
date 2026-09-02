from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from configs.log_config import get_logger
from typing import List
from src.services.errors.base import DomainError

from src.modules.reminders.reminder_repository import ReminderRepository
from src.modules.reminders.reminder_dtos import CreateReminderDTO


class ReminderAPIService:
    def __init__(self, reminder_repository: ReminderRepository, db: AsyncSession):
        self.db = db
        self.reminder_repository = reminder_repository
        self.logger = get_logger("Reminder_API_Service")

    async def create_reminder(self, reminder_dto: List[CreateReminderDTO]) -> dict:
        """Creates reminders based on the provided DTOs."""
        try:
            reminders = await self.reminder_repository.create_reminders(reminder_dto)
            await self.db.commit()
            return {"reminders": reminders}
        except Exception:
            self.logger.exception("Error creating reminder")
            await self.db.rollback()
            raise DomainError(message="Failed to create reminder", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)