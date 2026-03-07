from src.services.oauth.providers.Calendar_provider_service import GoogleCalendarOAuthService
from src.models.interview_models.calendar_connections import CalendarConnection 
from src.repositories.interview_respositories.calendar_repository import CalendarRepository 
from datetime import datetime,timedelta
from src.models.enums import CalendarProvider
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

class OAuthService:

    def __init__(self,db:AsyncSession, google_calendar_service: GoogleCalendarOAuthService, calendar_repository: CalendarRepository):
        self.db = db
        self.google_calendar_service :GoogleCalendarOAuthService  = google_calendar_service
        self.calendar_repository : CalendarRepository = calendar_repository

    def get_google_calendar_auth_url(self, state: str):
        return self.google_calendar_service.get_authorization_url(state)
    

    
    async def handle_google_calendar_callback(self, code: str, user_id: Optional[str] = None, user_email: Optional[str] = None):

        tokens = await self.google_calendar_service.exchange_code_for_tokens(code)

        access_token = tokens["access_token"]
        refresh_token = tokens.get("refresh_token")
        expires_in = tokens["expires_in"]

        token_expires_at = datetime.now() + timedelta(seconds=expires_in)

        user_info = await self.google_calendar_service.get_google_user_info(access_token)

        await self.calendar_repository.save_calendar_connection(
            provider_email=user_email or user_info["email"],
            provider=CalendarProvider.GOOGLE,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            provider_user_id=user_info.get("id"),
            user_id=user_id
        )
        
        await self.db.commit()  # Commit the transaction to save the connection

        return user_info