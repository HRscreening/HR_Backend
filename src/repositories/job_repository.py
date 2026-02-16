from sqlalchemy.ext.asyncio import AsyncSession
from  configs.log_config import get_logger

from sqlalchemy import select,func
from sqlalchemy.orm import selectinload

from fastapi import Depends, status,UploadFile,BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from src.models import Organization,User,Job,Rubric,Application,BulkUploadBatches,Score,Resume

from  configs.log_config import get_logger

from src.schemas.user_schemas import NewJobSchema
from typing import Optional,List



class JobRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = get_logger("JOB_REPOSITORY")

    # Implement job-related database operations here
    
    
    async def create_job(self, job_data,user_id:str)-> Optional[Job]:
        job = Job(
           title=job_data.title,
            description=job_data.description,
            location=job_data.location,
            target_headcount=job_data.target_headcount,
            voice_ai_enabled=job_data.voice_ai_enabled,
            manual_rounds_count=job_data.manual_rounds_count,
            is_confidential=job_data.is_confidential,
            created_by_id=user_id,
        )
        self.db.add(job)
        await self.db.flush() 
        return job
    
    async def create_job_with_rubric(self, job_data: NewJobSchema):
        job = Job(
            title=job_data.title,
            description=job_data.description,
            location=job_data.location,
            target_headcount=job_data.target_headcount,
            voice_ai_enabled=job_data.voice_ai_enabled,
            manual_rounds_count=job_data.manual_rounds_count,
            is_confidential=job_data.is_confidential,
        )
        self.db.add(job)
        return job
        
           
    async def get_job_by_id(self, job_id: str) -> Optional[Job]:
        result = await self.db.execute(
            select(Job).where(Job.id == job_id)
        )
        return result.scalar_one_or_none()
        
    async def get_all_rubrics(self,job_id:str) -> List[Rubric]:
        result = await self.db.execute(
            select(Rubric).where(Rubric.job_id == job_id)
        )
        return result.scalars().all()
      
    async def get_all_rubrics_versions(self,job_id:str) -> List[Rubric]:
        result = await self.db.execute(
            select(Rubric.version,Rubric.id,Rubric.created_at).where(Rubric.job_id == job_id)
        )
        return result.mappings().all()
    
    async def get_active_rubric(self,job_id:str) -> Optional[Rubric]:
        result = await self.db.execute(
            select(Rubric).where(Rubric.job_id == job_id, Rubric.is_active == True)
        )
        return result.scalar_one_or_none()
    
    async def get_active_rubric_version(self,job_id:str):
        result = await self.db.execute(
            select(Rubric.version,Rubric.id).where(Rubric.job_id == job_id, Rubric.is_active == True)
        )
        return result.mappings().one_or_none()
        
        
    async def get_jobs_by_organization(self, org_id: str) -> List[Job]:
        result = await self.db.execute(
            select(Job).where(Job.organization_id == org_id).order_by(Job.created_at.desc())
        )
        return result.scalars().all()
    
    
    async def get_jobs_by_user_personal(self, user_id: int) -> List[Job]:
        """Get jobs created by the user that are not associated with any organization"""
        
        result = await self.db.execute(
            select(Job).where(Job.created_by_id == user_id
                              ,Job.organization_id == None).order_by(Job.created_at.desc())
        )
        return result.scalars().all() 
    

    
    async def commit(self):
        await self.db.commit()

    async def rollback(self):
        await self.db.rollback()


        
