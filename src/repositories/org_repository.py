from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from pydantic import EmailStr
from src.models import Organization,User,Job,Rubric,Application,BulkUploadBatches

from  configs.log_config import get_logger

from src.schemas.user_schemas import NewOrgSchema,NewJobSchema

from src.services.errors.user_errors import OrganizationAlreadyExists


from typing import Optional
from sqlalchemy import select, update, delete

class OrganizationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = get_logger("ORG_REPOSITORY")
        
    async def create_organization(self, org_data: NewOrgSchema, owner_id: int) -> Organization:
        
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
    
    
    async def get_organization_by_email(self, email: EmailStr) -> Optional[Organization]:
        result = await self.db.execute( select(Organization).where(Organization.email == email) ) 
        return result.scalars().first()
            
    async def get_organization_by_id(self, org_id: int) -> Optional[Organization]:
        result = await self.db.execute(
            select(Organization).where(Organization.id == org_id)
        )
        return result.scalars().first()
    
    
    async def commit(self):
        await self.db.commit()

    async def rollback(self):
        await self.db.rollback()


        