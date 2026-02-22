from sqlalchemy.ext.asyncio import AsyncSession
from  configs.log_config import get_logger

from sqlalchemy import select,func
from sqlalchemy.orm import selectinload

from fastapi import Depends, status,UploadFile,BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from src.models import Organization,User,Job,Rubric,Application,Candidate
from src.models.enums import ApplicationStatus
from pydantic import EmailStr
from src.schemas.candidate_schema import CandidateInfoSchema
from typing import Optional,List

class CandidateRepository:
    def __init__(self,db: AsyncSession):
        self.db = db
    
    async def create_candidate(self,candidate_info:CandidateInfoSchema , resume_id: str,org_id:str|None=None) -> Candidate:
        candidate = Candidate(
            full_name=candidate_info.full_name,
            email=candidate_info.email,
            org_id=org_id,
            phone=candidate_info.phone,
            organization_id=org_id,  
            total_applications=1,  # Initialize total applications to 1 when creating a new candidate ,Assuming this is the first application for the candidate
            
        )
        self.db.add(candidate)
        await self.db.flush() 
        return candidate
    
    async def get_candidate_by_email(self, email: EmailStr,org_id:str) -> Optional[Candidate]:
        result = await self.db.execute(
            select(Candidate).where(Candidate.email == email,Candidate.organization_id == org_id)
        )
        return result.scalar_one_or_none()
    
    async def get_candidate_by_phone(self, phone: str,org_id:str) -> Optional[Candidate]:
        result = await self.db.execute(
            select(Candidate).where(Candidate.phone == phone,Candidate.organization_id == org_id)
        )
        return result.scalar_one_or_none()
    
    async def get_candidate_by_id(self, candidate_id: str,org_id:str) -> Optional[Application]:
        result = await self.db.execute(
            select(Candidate).where(Candidate.id == candidate_id,Candidate.organization_id == org_id)
        )
        return result.scalar_one_or_none()
    

    async def commit(self):
        await self.db.commit()

    async def rollback(self):
        await self.db.rollback()


        