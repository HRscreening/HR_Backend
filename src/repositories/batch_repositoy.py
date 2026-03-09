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
        
    async def get_batch_info(self, batch_id: str) -> Optional[BulkUploadBatches]:
        result = await self.db.execute(
            select(BulkUploadBatches).where(BulkUploadBatches.id == batch_id)
        )
        return result.scalar_one_or_none()

    async def get_batch_by_id(self, batch_id: str) -> Optional[BulkUploadBatches]:
        return await self.get_batch_info(batch_id)

    async def get_latest_batch_for_job(self, job_id: str) -> Optional[BulkUploadBatches]:
        result = await self.db.execute(
            select(BulkUploadBatches)
            .where(BulkUploadBatches.job_id == job_id)
            .order_by(BulkUploadBatches.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def increment_success(self, batch_id: str) -> Optional[BulkUploadBatches]:
        batch = await self.get_batch_info(batch_id)
        if batch:
            batch.success_count += 1
            batch.processed_count += 1
        return batch

    async def increment_failure(self, batch_id: str) -> Optional[BulkUploadBatches]:
        batch = await self.get_batch_info(batch_id)
        if batch:
            batch.failed_count += 1
            batch.processed_count += 1
        return batch

    async def update_batch_status(self, batch_id: str, status) -> Optional[BulkUploadBatches]:
        batch = await self.get_batch_info(batch_id)
        if batch:
            batch.status = status
        return batch
