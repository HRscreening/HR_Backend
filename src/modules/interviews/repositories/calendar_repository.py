from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Interview_TimeLine_Events,CalendarConnection
from src.models.enums import CalendarProvider

from typing import Optional,List
from datetime import datetime,timedelta



class CalendarRepository:
    def __init__(self,db: AsyncSession):
        self.db = db
    
    
    async def save_calendar_connection(
    self,
    provider_email: str,
    provider: CalendarProvider,
    access_token: str,
    token_expires_at: datetime,
    refresh_token: Optional[str] = None,
    provider_user_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> CalendarConnection:
        """Creates a new calendar connection for a user."""
        calendar_connection = CalendarConnection(
            provider_email=provider_email,
            provider=provider,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at = token_expires_at,
            provider_user_id=provider_user_id,
            user_id=user_id
        )
        self.db.add(calendar_connection)
        await self.db.flush() 
        return calendar_connection 
    
    
    
    async def upsert_calendar_connection(
        self,
        provider_email: str,
        provider: CalendarProvider,
        access_token: str,
        token_expires_at: datetime,
        refresh_token: Optional[str] = None,
        provider_user_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> CalendarConnection:

        # Check if connection already exists
        result = await self.db.execute(
            select(CalendarConnection).where(
                CalendarConnection.provider_email == provider_email
            )
        )
        calendar_connection = result.scalar_one_or_none()

        if calendar_connection:
            # Update existing record
            calendar_connection.provider = provider
            calendar_connection.access_token = access_token
            calendar_connection.refresh_token = refresh_token
            calendar_connection.token_expires_at = token_expires_at
            calendar_connection.provider_user_id = provider_user_id
            calendar_connection.user_id = user_id

        else:
            # Create new record
            calendar_connection = CalendarConnection(
                provider_email=provider_email,
                provider=provider,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=token_expires_at,
                provider_user_id=provider_user_id,
                user_id=user_id
            )
            self.db.add(calendar_connection)

        await self.db.flush()
        return calendar_connection
        
        
        
        
    async def save_calendar_connection(
    self,
    provider_email: str,
    provider: CalendarProvider,
    access_token: str,
    token_expires_at: datetime,
    refresh_token: Optional[str] = None,
    provider_user_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> CalendarConnection:
        """Creates a new calendar connection for a user."""
        calendar_connection = CalendarConnection(
            provider_email=provider_email,
            provider=provider,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at = token_expires_at,
            provider_user_id=provider_user_id,
            user_id=user_id
        )
        self.db.add(calendar_connection)
        await self.db.flush() 
        return calendar_connection 
        
        
    async def get_calendar_connection_by_email_and_provider(self, provider_email: str, provider: CalendarProvider) -> Optional[CalendarConnection]:
        """Fetches a calendar connection by user email and provider."""
        result = await self.db.execute(
            select(CalendarConnection)
            .where(
                CalendarConnection.provider_email == provider_email,
                CalendarConnection.provider == provider,
            )
        )
        return result.scalars().first()
    
    async def get_calendar_access_token(self, provider_email: str, provider: CalendarProvider) -> Optional[str]:
        """Fetches a calendar connection by user email and provider."""
        result = await self.db.execute(
            select(CalendarConnection)
            .where(
                CalendarConnection.provider_email == provider_email,
                CalendarConnection.provider == provider,
            )
        )
        calendar =  result.scalar_one_or_none()
        
        return calendar.access_token if calendar else None
    
    
    async def is_calendar_connected(self, provider_email: str, provider: CalendarProvider) -> bool:
        """Checks if a calendar connection exists for the given email and provider."""
        result = await self.db.execute(
            select(func.count(CalendarConnection.id))
            .where(
                CalendarConnection.provider_email == provider_email,
                CalendarConnection.provider == provider,
            )
        )
        count = result.scalar()
        return count > 0
    
    
    
    