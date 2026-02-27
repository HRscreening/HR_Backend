from sqlalchemy.ext.asyncio import AsyncSession
from  configs.log_config import get_logger

from sqlalchemy import select,func
from sqlalchemy.orm import selectinload

from fastapi import Depends, status,UploadFile,BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from src.models import Organization,User,Job,Rubric,Application,BulkUploadBatches,Score,Resume
from src.models.enums import ApplicationStatus
from pydantic import EmailStr
from typing import Optional,List

class ApplicationRepository:
    def __init__(self,db: AsyncSession):
        self.db = db
    
    async def create_application(self, job_id: str, candidate_id: int = None, resume_id: int = None) -> Application:
        application = Application(
            job_id=job_id,
            candidate_id=candidate_id,
            current_resume_id=resume_id,
            status=ApplicationStatus.APPLIED,
        )
        self.db.add(application)
        await self.db.flush() 
        return application
    
    async def get_application_by_id(self, application_id: int) -> Optional[Application]:
        result = await self.db.execute(
            select(Application).where(Application.id == application_id)
        )
        return result.scalar_one_or_none()
    
    
    async def get_applications_by_candidate(self, candidate_id: int) -> List[Application]:
        result = await self.db.execute(
            select(Application).where(Application.candidate_id == candidate_id).order_by(Application.created_at.desc())
        )
        return result.scalars().all()
        
    
    async def get_applications_by_group(self, job_id: str) -> List[Application]:
        result = await self.db.execute(
            select(Application.status,func.count(Application.id)).where(Application.job_id == job_id).group_by(Application.status)
        )
        
        return result.all()
    
    async def get_total_applications_count(self, job_id: str) -> int:
        total_result = await self.db.execute(
        select(func.count(Application.id))
        .where(Application.job_id == job_id)
    )
        total = total_result.scalar_one()
        
        return total
    
    async def get_applications_of_job(self,job_id:str,current_rubric_id:str,page_size:int=15,offset:int=0):
        stmt = (
            select(Application, Score)
            .join(
                Score,
                (Score.application_id == Application.id) &
                (Score.rubric_id == current_rubric_id)
            )
            .where(Application.job_id == job_id, Application.deleted_at == None)
            .options(
                selectinload(Application.candidate),
                selectinload(Application.resume)
            )
            .order_by(Score.overall_score.desc())
            .limit(page_size)
            .offset(offset)
        )

        result = await self.db.execute(stmt)
        rows = result.all()
        return rows
    
    async def get_avg_match_score(self, job_id: str) -> Optional[float]:
        result = await self.db.execute(
            select(func.avg(Score.overall_score)).join(Application, Application.id == Score.application_id).where(Application.job_id == job_id)
        )
        avg_score = result.scalar_one_or_none()
        return avg_score
    
    async def get_application_by_application_ids(self,application_ids: list[int]) -> List[Application]:
        result = await self.db.execute(
            select(Application).where(Application.id.in_(application_ids))
        )
        return result.scalars().all()
    
    
    async def commit(self):
        await self.db.commit()

    async def rollback(self):
        await self.db.rollback()


        