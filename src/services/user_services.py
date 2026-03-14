from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Organization,User,Job,Rubric,Application,BulkUploadBatches

from  configs.log_config import get_logger

from src.services.errors.auth_errors import UserNotFound
from src.services.errors.base import DomainError

from src.models.enums import CalendarProvider
from src.repositories.user_repository import UserRepository
from src.repositories.interview_respositories.calendar_repository import CalendarRepository



class UserService:
    def __init__(self,userRepository:UserRepository,
                 calendar_repository:CalendarRepository,
                 db: AsyncSession):
        self.db = db
        self.user_repository = userRepository
        self.calendar_repository = calendar_repository
        self.logger = get_logger("USER_SERVICE")


    async def get_user_by_id(self,user_id: str) -> dict:
        try:
            user = await self.user_repository.get_user_by_id(user_id)

            if not user:
                raise UserNotFound(message="User ID not found",status_code=status.HTTP_404_NOT_FOUND)
            
            is_google_calendar_connected = await self.calendar_repository.is_calendar_connected(user.email,CalendarProvider.GOOGLE)

            return {
                "id": user.id,
                "email": user.email,
                "name": user.name,
            }

        except Exception:
            self.logger.exception(f"Error fetching user by ID: {user_id}")
            raise
        
    async def get_user_settings(self,user_id: str) -> dict:
        try:
            user = await self.user_repository.get_user_by_id(user_id)

            if not user:
                raise UserNotFound(message="User ID not found",status_code=status.HTTP_404_NOT_FOUND)

            return {
                "is_google_calendar_connected": await self.calendar_repository.is_calendar_connected(user.email,CalendarProvider.GOOGLE)
            }

        except Exception:
            self.logger.exception(f"Error fetching user settings for ID: {user_id}")
            raise

