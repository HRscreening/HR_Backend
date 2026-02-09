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

from sqlalchemy import select, update, delete

class OrganizationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = get_logger("ORG_REPOSITORY")
        
    async def create_organization(self, org_data: NewOrgSchema, owner_id: int) -> Organization:
        # 1️⃣ Check if organization with the same name already exists
        existing_org = await self.db.execute(
            select(Organization).where(Organization.name == org_data.name)
        )
        existing_org = existing_org.scalars().first()

        if existing_org:
            raise OrganizationAlreadyExists("An organization with this name already exists.")

        # 2️⃣ Create new organization
        new_org = Organization(
            name=org_data.name,
            description=org_data.description,
            owner_id=owner_id,
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(new_org)
        await self.db.commit()
        await self.db.refresh(new_org)

        return new_org
    
    
    async def get_organization_by_id(self, org_id: int) -> Optional[Organization]:
        result = await self.db.execute(
            select(Organization).where(Organization.id == org_id)
        )
        return result.scalars().first()