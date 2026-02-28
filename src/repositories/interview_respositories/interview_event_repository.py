from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Interview_TimeLine_Events

from typing import Optional,List
from src.dtos.interviews_dtos.interview_event_dto import CreateInterviewEventDTO




class InterviewEventRepository:
    def __init__(self,db: AsyncSession):
        self.db = db
    
    async def create_interview_event(self, interview_id: str, event_type: str, actor: str = None,details: dict = None) -> Interview_TimeLine_Events:
        """Creates a new interview timeline event."""
        interview_event = Interview_TimeLine_Events(
            interview_id=interview_id,
            event_type=event_type,
            actor=actor,
            details=details    
        )
        self.db.add(interview_event)
        await self.db.flush() 
        return interview_event
