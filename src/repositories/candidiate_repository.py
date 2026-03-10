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
from src.schemas.candidate_schemas import CandidateCreateSchema,CandidateUpdateSchema
from typing import Optional,List

class CandidateRepository:
    def __init__(self,db: AsyncSession):
        self.db = db
    
    async def create_candidate(self,candidate_info:CandidateCreateSchema ,org_id:str|None=None) -> Candidate:
        candidate = Candidate(
            full_name=candidate_info.full_name,
            email=candidate_info.email,
            phone=candidate_info.phone,
            current_title=getattr(candidate_info, "current_title", None),
            current_company=getattr(candidate_info, "current_company", None),
            organization_id=org_id,
        )
        self.db.add(candidate)
        await self.db.flush() 
        return candidate
    
    
    async def get_candidate_by_email(self,email: EmailStr,org_id: str | None = None) -> Optional[Candidate]:

        stmt = select(Candidate).where(Candidate.email == email)

        if org_id is None:
            stmt = stmt.where(Candidate.organization_id.is_(None))
        else:
            stmt = stmt.where(Candidate.organization_id == org_id)

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_candidate_by_phone(self, phone: str,org_id:str | None = None) -> Optional[Candidate]:
        stmt = select(Candidate).where(Candidate.phone == phone)

        if org_id is None:
            stmt = stmt.where(Candidate.organization_id.is_(None))
        else:
            stmt = stmt.where(Candidate.organization_id == org_id)

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_candidate_by_id(self, candidate_id: str,org_id:str | None = None) -> Optional[Candidate]:
        stmt = select(Candidate).where(Candidate.id == candidate_id)

        if org_id is None:
            stmt = stmt.where(Candidate.organization_id.is_(None))
        else:
            stmt = stmt.where(Candidate.organization_id == org_id)

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    

        
    async def refresh(self,instance):
        await self.db.refresh(instance)

        