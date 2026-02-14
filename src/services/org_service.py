from fastapi import status,UploadFile,BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from src.models import Job,Rubric,BulkUploadBatches

from  configs.log_config import get_logger

from src.schemas.user_schemas import NewJobSchema
from src.schemas.job_schemas import JobOverviewResponse

from src.services.errors.user_errors import JDExtractionFailed,JobNotFound,RubricNotFound
from src.services.errors.base import DomainError
from typing import Optional,List
from src.utils.extract_pdf import extract_text_from_pdf
from src.pipelines.generate_rubric import generate_rubric_from_jd
from workers.producer import enqueue_resumes_parsing
from src.repositories.org_repository import OrganizationRepository
from src.utils.file_manager import FileManagerService
from src.utils.file_manager import fileManager
from src.schemas.org_schema import NewOrgSchema


class OrgnaziationService:
    def __init__(self,org_repository,db: AsyncSession):
        self.db = db
        self.organization_repository:OrganizationRepository = org_repository
        self.file_manager:FileManagerService = fileManager
        self.logger = get_logger("JOB_SERVICE")
        
    async def create_organization(self, org_data: NewOrgSchema, owner_id: int) -> int:
        try:
            org = await self.organization_repository.get_organization_by_email(org_data.email)
            if org: 
                raise DomainError("An organization with this email already exists.",status_code=status.HTTP_400_BAD_REQUEST)
            
            new_org = await self.organization_repository.create_organization(org_data, owner_id) 
            
            if not new_org: 
                raise DomainError("Failed to create organization.",status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            return new_org
            
        except DomainError as de:
            self.logger.error(f"Domain error while creating organization: {de}") 
            raise
  