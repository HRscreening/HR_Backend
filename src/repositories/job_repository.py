from fastapi import Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.user_model import User
from src.utils.security import hash_password,verify_password
# from src.utils.jwt import create_jwt
from src.utils.security import hash_password
import random
from src.utils.send_otp import send_otp_email
from  configs.log_config import get_logger
from src.schemas.auth_schemas import NewUserSchema,OtpVerification,UserLogin
from src.services.errors.auth_errors import EmailAlreadyExists,OTPVerificationFailed,UserLoginFailed,UserNotFound,DomainError


from sqlalchemy import select,func

from fastapi import Depends, status,UploadFile,BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from src.models import Organization,User,Job,Rubric,Application,BulkUploadBatches

from  configs.log_config import get_logger

from src.schemas.user_schemas import NewOrgSchema,NewJobSchema
from src.schemas.job_schemas import JobOverviewResponse

from src.services.errors.user_errors import OrganizationAlreadyExists,JDExtractionFailed,JobNotFound,RubricNotFound
from src.services.errors.auth_errors import UserNotFound
from src.services.errors.base import DomainError


from src.models.enums import UserRole
from typing import Optional,List
from src.utils.extract_pdf import extract_text_from_pdf
from src.pipelines.generate_rubric import generate_rubric_from_jd


from src.utils.manage_supabase_buckets import supabase_file_handler
from src.utils.stage_uploaded_files import FileService

from workers.producer import enqueue_resumes_parsing


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
    
    
    
    async def get_active_rubric(self,job_id:str) -> Optional[Rubric]:
        result = await self.db.execute(
            select(Rubric).where(Rubric.job_id == job_id, Rubric.is_active == True)
        )
        return result.scalar_one_or_none()
        
        
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
    
    async def get_jobs_by_user_organization(self, user_id: int) -> List[Job]:
        """Get jobs created by the user that are associated with an organization"""
        
        result = await self.db.execute(
            select(Job).where(Job.created_by_id == user_id
                              ,Job.organization_id != None).order_by(Job.created_at.desc())
        )
        return result.scalars().all()
    
    async def get_applications_by_group(self, job_id: str) -> List[Application]:
        result = await self.db.execute(
            select(Application.status,func.count(Application.id)).where(Application.job_id == job_id).group_by(Application.status)
        )
        
        return result.all()
    
