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

class BatchRepository:
    def __init__(self,db: AsyncSession):
        self.db = db
        
    async def get_batch_info(self, batch_id: int) -> Optional[BulkUploadBatches]:
        result = await self.db.execute(
            select(BulkUploadBatches).where(BulkUploadBatches.id == batch_id)
        )
        return result.scalar_one_or_none()
    
    
    
    
    

    