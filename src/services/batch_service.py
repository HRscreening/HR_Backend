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
from workers.new_producer import ARQProducer
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
        
        if batch.error_log is None:
            batch.error_log = {}
        if message:
            batch.error_log[file_name] = message

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

    
        if batch.error_log is None:
            batch.error_log = {}
        
        batch.error_log[file_name] = reason if reason else "Unknown error"

        if batch.processed_count >= batch.total_files:
            batch.status = "completed"

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

    # TODO 
    # async def finalize_batch_parsed(self,batch_id: str):
    #     try:
    #         batch = await self.batch_repository.get_batch_by_id(batch_id)
            
    #         if not batch:
    #             raise ValueError(f"Batch {batch_id} not found")
                

    #         # ✅ batch not fully processed yet
    #         if batch.total_files != (batch.failed_count + batch.success_count):
    #             self.logger.info(f"Batch {batch_id} is not fully processed yet. Total: {batch.total_files}, Processed: {batch.processed_count}")
    #             return

    #         # ✅ idempotency guard USING EXISTING STATUS
    #         if batch.status != BulkUploadStatus.PENDING:
    #             self.logger.info(f"Batch {batch_id} is already finalized. Skipping...")
    #             return

    #         job_id = batch.job_id
            
    #         # May be Job status can be checked if needed
            
    #         if not job_id:
    #             self.logger.error(f"Batch {batch_id} has no associated job_id")
    #             raise ValueError(f"Batch {batch_id} has no associated job_id")


    #         resume_ids = await self.resume_repositoy.lock_and_mark_parsed_resumes_for_scoring(job_id=job_id)
            
    #         if not resume_ids:
    #             self.logger.error(f"No parsed resumes found for job_id {job_id}")
    #             raise ValueError(f"No parsed resumes found for job_id {job_id}")
                

    #         # TODO: Dispatching all resumes in a single batch can be a problem if there are too many resumes,
    #         # so we can dispatch in batches of N (e.g., 10 or 20) to avoid overwhelming the worker and also to have better control and monitoring of the processing.
    #         # For now, we are dispatching all at once for simplicity.
    #         await self.dispatch_scoring_batch(
    #             db_job_id=job_id,
    #             resume_ids=resume_ids,
    #             batch_id=batch_id,
    #         )
            
            
    #         batch.status = BulkUploadStatus.PROCESSING
    #         await self.db.commit()
        
    #     except Exception as e:
    #         await self.db.rollback()
    #         self.logger.exception(f"Error finalizing batch {batch_id}: {str(e)}")

    # async def finalize_batch_parsed(self, batch_id: str):
    #     try:
    #         batch = await self.batch_repository.get_batch_by_id(batch_id)

    #         if not batch:
    #             raise ValueError(f"Batch {batch_id} not found")

    #         # ✅ idempotency guard
    #         if batch.status != BulkUploadStatus.PENDING:
    #             self.logger.info(f"Batch {batch_id} already finalized or processing")
    #             return

    #         job_id = batch.job_id
    #         if not job_id:
    #             raise ValueError(f"Batch {batch_id} has no job_id")

    #         # ! here not  checking for batch total files with success + failed count.Assuming redis is the source of truth for it 
    #         # This is to avoid race condition between workers updating batch counts and this finalize method being called before counts are updated in DB but they are updated in Redis which is the source of truth for counts and status of batch processing for workers. So as long as Redis counts are correct, we can proceed with finalization even if DB counts are not yet updated due to async nature of DB updates and commits.
            
            
    #         for _ in range(5):
    #             resume_ids = await self.resume_repositoy.lock_and_mark_parsed_resumes_for_scoring(job_id)

    #             if resume_ids:
    #                 break

    #             await asyncio.sleep(0.2)

    #         if not resume_ids:
    #             self.logger.warning("No resumes found — assuming already processed")
            
            
            
    #         resume_ids = await self.resume_repositoy.lock_and_mark_parsed_resumes_for_scoring(job_id=job_id)

    #         if resume_ids:
    #             await self.dispatch_scoring_batch(
    #                 db_job_id=job_id,
    #                 resume_ids=resume_ids,
    #                 batch_id=batch_id,
    #             )

    #         # ✅ Mark transition
    #         batch.status = BulkUploadStatus.PROCESSING

    #         await self.db.commit()

    #     except Exception:
    #         await self.db.rollback()
    #         raise
    # In finalize_batch_parsed — single transaction
    
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
            await self.db.commit()  # ← single commit covers everything

        except Exception:
            await self.db.rollback()
            raise