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
    
    async def create_interview_event(self, interview_id: str, event_type: str, actor: str,summary:str | None ,details: dict = None) -> Interview_TimeLine_Events:
        """Creates a new interview timeline event."""
        interview_event = Interview_TimeLine_Events(
            interview_id=interview_id,
            event_type=event_type,
            actor=actor,
            summary=summary if summary else None,
            details=details    
        )
        self.db.add(interview_event)
        await self.db.flush() 
        return interview_event

    # TODO: Paginate for long timelines
    async def get_events_by_interview_id(self, interview_id: str) -> List[Interview_TimeLine_Events]:
        """Get all timeline events for an interview, ordered chronologically."""
        result = await self.db.execute(
            select(Interview_TimeLine_Events)
            .where(Interview_TimeLine_Events.interview_id == interview_id)
            .order_by(Interview_TimeLine_Events.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_events_by_interview_id_brief(self, interview_id: str):
        result = await self.db.execute(
            select(
                Interview_TimeLine_Events.id,
                Interview_TimeLine_Events.actor,
                Interview_TimeLine_Events.event_type,
                Interview_TimeLine_Events.summary,
                Interview_TimeLine_Events.created_at
            )
            .where(Interview_TimeLine_Events.interview_id == interview_id)
            .order_by(Interview_TimeLine_Events.created_at.desc())
        )

        return result.mappings().all()
