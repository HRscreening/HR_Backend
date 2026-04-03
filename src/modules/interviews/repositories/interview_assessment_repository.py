from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,func
from sqlalchemy.orm import selectinload,joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Interview,Application
from datetime import datetime, timezone, timedelta
from typing import Optional,List
from src.models.enums import InterviewStatus
from configs.log_config import get_logger
from src.utils.jwt import JWTService
from src.modules.interviews.models import InterviewAssessment




class InterviewAssessmentRepository:
    def __init__(self,db: AsyncSession):
        self.db = db
        
        
    async def create_interview_assessment(self,interview_id:int,panelist_id:int,token:str,token_expiry:datetime):
        interview_assessment = InterviewAssessment(
            interview_id=interview_id,
            panelist_id=panelist_id,
            feedback_token=token,
            token_expires_at=token_expiry
        )
        self.db.add(interview_assessment)
        await self.db.flush()
        return interview_assessment
    
    
    async def get_interview_assessment_by_id(self,assessment_id:int) -> Optional[InterviewAssessment]:
        result = await self.db.execute(
            select(InterviewAssessment).where(InterviewAssessment.id == assessment_id)
        )
        return result.scalar_one_or_none()
    
    
    async def get_interview_assessment_by_interview_id(self,interview_id:str) -> Optional[InterviewAssessment]:
        result = await self.db.execute(
            select(InterviewAssessment).where(
                InterviewAssessment.interview_id == interview_id,
            )
        )
        return result.scalar_one_or_none()
        
    # async def 
    
    
    
    