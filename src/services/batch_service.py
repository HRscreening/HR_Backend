from fastapi import status,UploadFile,BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from src.models import BulkUploadBatches

from  configs.log_config import get_logger
from src.services.errors.base import DomainError
from typing import Optional,List
from src.repositories.batch_repositoy import BatchRepository 


class BatchService:
    def __init__(self,batch_repository:BatchRepository,db: AsyncSession):
        self.db = db
        self.batch_repository:BatchRepository = batch_repository
        self.logger = get_logger("BATCH_SERVICE")
    
    async def get_batch_summary(self, batch_id: int) -> Optional[BulkUploadBatches]:
        batch =  await self.batch_repository.get_batch_info(batch_id)
        
        if not batch:
            self.logger.error(f"Batch with id {batch_id} not found")
            raise DomainError(status_code=status.HTTP_404_NOT_FOUND, message="Batch not found")
        
        
          
        return {
            "processed_files":batch.processed_count,
            "failed_files":batch.failed_count,
            "total_files":batch.total_files,
            "status":batch.status,
            "created_at":batch.created_at,
            # TODO: make this error_logs and return list of file names which failed with reason(optional) instead of whole logs | whole logs are for internal use and file names with reason can be shown to users in UI
            "failed_files_names":batch.error_log if batch.error_log else None 
        }
        
    async def get_batch_failed_logs(self, batch_id: int) -> Optional[BulkUploadBatches]:
        batch =  await self.batch_repository.get_batch_info(batch_id)
        
        if not batch:
            self.logger.error(f"Batch with id {batch_id} not found")
            raise DomainError(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
        
        # TODO: try to pass only file_names which failed with the reason(optional) instead of whole logs | whole logs are for internal use and file names with reason can be shown to users in UI
        return {
            "error_logs":batch.error_logs,
        }
        
