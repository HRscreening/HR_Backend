from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Interview

from typing import Optional,List
from src.dtos.interviews_dtos.interview_event_dto import CreateInterviewEventDTO




class InterviewRepository:
    def __init__(self,db: AsyncSession):
        self.db = db
    
    async def create_interview(self, round_config_id: str,application_id: str,round_number:int ) -> Interview:
        """Creates a new interview ."""
        interview = Interview(
               round_config_id=round_config_id,
                application_id=application_id,
                round_number=round_number   
        )
        self.db.add(interview)
        await self.db.flush() 
        return interview
    
    
    async def get_interview_by_id(self, interview_id: str) -> Optional[Interview]:
        result = await self.db.execute(
            select(Interview).where(Interview.id == interview_id)
        )
        return result.scalar_one_or_none()
