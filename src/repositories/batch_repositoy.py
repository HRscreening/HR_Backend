from sqlalchemy.ext.asyncio import AsyncSession
from  configs.log_config import get_logger

from sqlalchemy import select,func,update
from sqlalchemy.orm import selectinload

from fastapi import Depends, status,UploadFile,BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from src.models import Organization,User,Job,Rubric,Application,BulkUploadBatches,Score,Resume
from src.models.enums import ApplicationStatus,BulkUploadStatus
from pydantic import EmailStr
from src.schemas.job_schemas import NewJobSchema
from typing import Optional,List

class BatchRepository:
    def __init__(self,db: AsyncSession):
        self.db = db
    
    async def get_batch_by_id(self, batch_id: int) -> Optional[BulkUploadBatches]:
        result = await self.db.execute(
            select(BulkUploadBatches).where(BulkUploadBatches.id == batch_id)
        )
        return result.scalar_one_or_none()
        
    async def get_batch_info(self, batch_id: int) -> Optional[BulkUploadBatches]:
        result = await self.db.execute(
            select(BulkUploadBatches).where(BulkUploadBatches.id == batch_id)
        )
        return result.scalar_one_or_none()
    
    async def create_batch(self, job_id: str,uploaded_by_id:str,source_file_url:List[str],batch_name: str, total_files: int) -> BulkUploadBatches:
        batch = BulkUploadBatches(
                job_id=job_id,
                uploaded_by=uploaded_by_id,
                batch_name=batch_name,
                source_file_url=source_file_url,
                total_files = total_files,
            )
        self.db.add(batch)
        await self.db.flush()  
        return batch
    
    async def increment_success(self, batch_id: int,increased_processed_count_by: int = 1):

        stmt = (
            update(BulkUploadBatches)                                       #TODO : add more condition to check
            .where(BulkUploadBatches.id == batch_id )
            .values(
                processed_count=BulkUploadBatches.processed_count + increased_processed_count_by,
                success_count=BulkUploadBatches.success_count + increased_processed_count_by,
            )
            .returning(BulkUploadBatches)
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    
    
    async def increment_failure(self, batch_id: int,increased_failed_count_by: int = 1):
        stmt = (
            update(BulkUploadBatches)
            .where(BulkUploadBatches.id == batch_id)
            .values(
                processed_count=BulkUploadBatches.processed_count + increased_failed_count_by,
                failed_count=BulkUploadBatches.failed_count + increased_failed_count_by,
            )
            .returning(BulkUploadBatches)
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def update_batch_status(self, batch_id: int, status:BulkUploadStatus ):
        stmt = (
            update(BulkUploadBatches)
            .where(BulkUploadBatches.id == batch_id)
            .values(status=status)
            .returning(BulkUploadBatches)
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    
    
    
    

    