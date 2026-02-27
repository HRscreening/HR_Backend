from fastapi import status,UploadFile,BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from src.models import BulkUploadBatches

from  configs.log_config import get_logger
from src.services.errors.base import DomainError
from typing import Optional,List
from src.repositories.batch_repositoy import BatchRepository 
from src.repositories.resume_respositoy import ResumeRepository
from src.models.enums import BulkUploadStatus,ResumeStatus
from async_workers.producer import ARQProducer
import asyncio


# TODO : Follow this pattern for other service as well if needed

class BaseBatchService:
    def __init__(self, batch_repository: BatchRepository, db: AsyncSession):
        self.db = db
        self.batch_repository = batch_repository
        
        
    async def get_batch_by_id(self, batch_id: int) -> Optional[BulkUploadBatches]:
        batch = await self.batch_repository.get_batch_by_id(batch_id)
        if not batch:
            self.logger.error(f"Batch with id {batch_id} not found")
            raise DomainError(status_code=status.HTTP_404_NOT_FOUND, message="Batch not found")
        return batch


class BatchService(BaseBatchService):
    def __init__(self, batch_repository: BatchRepository, db: AsyncSession):
        super().__init__(batch_repository,db)
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
   



class BatchService_ForWorker(BaseBatchService):
    def __init__(self,batch_repository:BatchRepository,resume_repository:ResumeRepository,job_producer:ARQProducer,db: AsyncSession):
        super().__init__(batch_repository,db)
        self.logger = get_logger("BATCH_WORKER_SERVICE")
        # self.job_producer : ARQProducer = job_producer 
        self.job_producer :ARQProducer  = job_producer 
        self.resume_repositoy : ResumeRepository = resume_repository
        
     
    async def mark_success_job(
        self,
        batch_id: int,
        file_name: str,
        message: str | None = None,
    ):

        batch = await self.batch_repository.increment_success(batch_id)

        if not batch:
            raise ValueError(f"Batch {batch_id} not found")
        
        results = batch.processing_results or {}

        results[file_name] = message or "Processed successfully"

        batch.processing_results = results  # reassign for SQLAlchemy

        if batch.processed_count >= batch.total_files:
            batch.status = BulkUploadStatus.COMPLETED

        await self.db.commit()

  
  
  
    async def mark_fail_job(
        self,
        batch_id: int,
        file_name: str,
        reason: str | None = None,
    ):

        batch = await self.batch_repository.increment_failure(batch_id)

        if not batch:
            raise ValueError(f"Batch {batch_id} not found")


        results = batch.error_log or {}

        # Always record success
        results[file_name] = reason or "Processed Unknown error"


        if batch.processed_count >= batch.total_files:
            batch.status = BulkUploadStatus.COMPLETED

        await self.db.commit()



    async def dispatch_scoring_batch(
        self,
        db_job_id: str,
        resume_ids: list[str],
        batch_id: str,
    ):
        # Resumes are already QUEUED_FOR_SCORING (transitioned by lock_and_mark_parsed_resumes_for_scoring).
        # We only need to check which have parsed text vs which need URL-based scoring.
        resumes = await self.resume_repositoy.get_resumes_by_ids(resume_ids)

        text_ids = []  # for resumes with parsed text
        url_ids = []   # for resumes without parsed text (to be scored based on URL of resume)

        for r in resumes:
            if r.parsed_text and r.parsed_text.strip():
                text_ids.append(r.id)
            else:
                url_ids.append(r.id)

        if text_ids:
            await self.job_producer.enqueue_text_scoring(
                job_id=db_job_id,
                resume_ids=text_ids,
                db_batch_id=batch_id,
            )

        if url_ids:
            await self.job_producer.enqueue_url_scoring(
                job_id=db_job_id,
                resume_ids=url_ids,
                db_batch_id=batch_id,
            )

        return len(resumes)






    async def finalize_batch_parsed(self, batch_id: str):
        try:
            batch = await self.batch_repository.get_batch_by_id(batch_id)
            if not batch:
                raise ValueError(f"Batch {batch_id} not found")
            if batch.status != BulkUploadStatus.PENDING:
                self.logger.info(f"Batch {batch_id} already finalized, skipping")
                return

            job_id = batch.job_id

            resume_ids = await self.resume_repositoy.lock_and_mark_parsed_resumes_for_scoring(job_id)

            if resume_ids:
                await self.dispatch_scoring_batch(
                    db_job_id=job_id,
                    resume_ids=resume_ids,
                    batch_id=batch_id,
                )
            else:
                self.logger.warning(f"Batch {batch_id}: no PARSED resumes found")

            await self.batch_repository.update_batch_status(batch_id, BulkUploadStatus.PROCESSING)
            await self.db.commit()  

        except Exception:
            await self.db.rollback()
            raise