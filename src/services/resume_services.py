# ! : This service uses synchronous DB session for workers.

from configs.postgress_db import AsyncSession
from src.utils.extract_pdf import extract_text_from_pdf_sync
import os
from src.schemas.user_schemas import ResumeDataSchema,ResumeDataSchemaURL
from src.models.enums import ResumeStatus, DocumentProcessingStatus
from src.models import Document
from configs.env_config import SUPABASE_PUBLIC_URL
import os
import mimetypes
from src.services.errors.base import DomainError 
from src.pipelines.score_resumes import score_resume_with_text
from src.pipelines.score_img_format_resumes import score_resume_with_url
from src.repositories.resume_respositoy import ResumeRepository
from configs.log_config import get_logger
from src.utils.extract_pdf import pdf_text_extractor,PDFTextExtractor
from src.schemas.score_schema import ScoreRecordSchema,ResumeScoreFailure,ResumeScoreResult,Candidate_info_task,ResumeDataSchemaURL
import asyncio


from src.repositories.resume_respositoy import ResumeRepository
from src.repositories.application_repository import ApplicationRepository
from src.repositories.batch_repositoy import BatchRepository
from src.repositories.job_repository import JobRepository
from src.repositories.document_repository import DocumentRepository
from src.utils.manage_supabase_buckets import supbase_file_manager,SupabaseFileHandler
from workers.new_producer import ARQProducer 
from src.repositories.score_repository import ScoreRepository
from datetime import datetime
from typing import Optional,List



class BaseResumeService:
    def __init__(self, job_repository: JobRepository, resume_repository: ResumeRepository, application_repository: ApplicationRepository, batch_repository: BatchRepository, document_repository: DocumentRepository, db: AsyncSession, *, job_producer: ARQProducer = None, score_repository: ScoreRepository = None):
        self.db = db
        self.resume_repository: ResumeRepository = resume_repository
        self.job_repository: JobRepository = job_repository
        self.application_repository: ApplicationRepository = application_repository
        self.batch_repository: BatchRepository = batch_repository
        self.pdf_text_extractor: PDFTextExtractor = pdf_text_extractor
        self.supbase_file_manager: SupabaseFileHandler = supbase_file_manager
        self.document_repository: DocumentRepository = document_repository
        self.score_repository: ScoreRepository = score_repository
        self.job_producer: ARQProducer = job_producer
        






# For API
class ResumeService(BaseResumeService):
    def __init__(self, job_repository: JobRepository, resume_repository: ResumeRepository, application_repository: ApplicationRepository, batch_repository: BatchRepository, document_repository: DocumentRepository, db: AsyncSession):
        super().__init__(job_repository, resume_repository, application_repository, batch_repository, document_repository, db)
        self.logger = get_logger("ResumeService")
        
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
# For Workers - can have worker specific methods here and use the common methods from BaseResumeService
class ResumeService_ForWorker(BaseResumeService):
    def __init__(self, job_repository: JobRepository, resume_repository: ResumeRepository, application_repository: ApplicationRepository, batch_repository: BatchRepository, document_repository: DocumentRepository, job_producer: ARQProducer, score_repository: ScoreRepository, db: AsyncSession):
        super().__init__(job_repository, resume_repository, application_repository, batch_repository, document_repository, db, job_producer=job_producer, score_repository=score_repository)
        self.logger = get_logger("ResumeService_ForWorker")
        self.parse_resume_logger = get_logger("Worker:ResumeService:ParseResume")
        self.score_url_logger = get_logger("Worker:ResumeService:ScoreURL")
        self.score_text_logger = get_logger("Worker:ResumeService:ScoreText")
        
        
    async def parse_resume(
        self,
        file_path: str,
        batch_id: str,
    )-> dict:
        """
        Parse a resume PDF file and store metadata in the database.
        
        Extracts text from the PDF, uploads it to Supabase, creates Application,
        Resume, and Document records, and returns the parsing result.
        
        Args:
            file_path (str): Path to the resume PDF file on disk
            batch_id (str): ID of the batch this resume belongs to
            
        Returns:
            dict: Dictionary with keys 'file_name' and 'msg' indicating parse success
            
        Raises:
            FileNotFoundError: If the specified file does not exist
            ValueError: If batch with given batch_id is not found in database
            Exception: On database or file processing errors
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            parsed_text, page_count = extract_text_from_pdf_sync(file_path)
            file_name = os.path.basename(file_path)
            
            batch = await self.batch_repository.get_batch_by_id(batch_id)
            
            if not batch:
                raise ValueError(f"Batch with id {batch_id} not found in DB")
            
            job_id = batch.job_id

            self.parse_resume_logger.info(f"Parsing resume at {file_path} for batch_id={batch_id}, job_id={job_id} at {datetime.now().isoformat()}")
           
            uploaded_file_url = self.supbase_file_manager.save_file_from_path(
                local_path=file_path,
                bucket="resumes",
                destination_path=f"{job_id}/{file_name}"
            )

            application = await self.application_repository.create_application(
                job_id=job_id,
                candidate_id=None,  # will be linked later in candidate extraction step
                resume_id=None  # will be linked after resume record is created
            )
            
            
            resume = await self.resume_repository.add_resume(
                applicaion_id=application.id,
                raw_file_url=uploaded_file_url,
                parsed_text=parsed_text,
                page_count=page_count,
                status=ResumeStatus.PARSED
            )

            mime_type, _ = mimetypes.guess_type(file_path)
            mime_type = mime_type or "application/pdf"

            await self.document_repository.add_document(Document(
                entity_type="resume",
                entity_id=resume.id,
                document_type="Resume",
                file_name=os.path.basename(file_path),
                file_size_bytes=os.path.getsize(file_path),
                mime_type=mime_type,
                storage_provider="supabase",
                file_path=str(uploaded_file_url),
                file_url=f"{SUPABASE_PUBLIC_URL}/{uploaded_file_url}",
                extracted_text=parsed_text,
                parsing_status=DocumentProcessingStatus.PARSED,
            ))
            
            
            application.current_resume_id = resume.id
            
            
            #TODO: Update the batch table with the count of processed files and any errors if needed. This can help in tracking the progress of the batch processing.
            
            parse_result = f"{file_name} parsed successfully"
            
            await self.batch_repository.increment_success(
                batch_id=batch_id,
            )
            
            await self.db.commit()
            
            result = {
                "file_name": file_name,
                "msg": parse_result,
            }
            
            
            return result

        except Exception:
            await self.db.rollback()
            self.parse_resume_logger.exception(f"Error parsing resume at {file_path} for batch_id={batch_id}")
            raise
    
   
    # =========================================================
    # PUBLIC ENTRYPOINT
    # =========================================================

    async def score_parsed_text_resumes(
        self,
        db_job_id: str,
        resume_ids: List[str],
        batch_id: str,
    ) -> Optional[dict]:

        if not resume_ids:
            self.score_text_logger.warning(
                f"Empty resume batch for batch_id={batch_id}"
            )
            return None

        try:
            # 1️⃣ Validate job
            job = await self._validate_job(db_job_id)

            # 2️⃣ Fetch resumes (with status transition)
            resumes = await self._fetch_resumes(
                db_job_id, resume_ids
            )
            
            if not resumes:
                return None

            rubric = await self._get_rubric(db_job_id)

            # 3️⃣ Prepare payload
            payload = self._build_payload_parsed_text(resumes)

            # 4️⃣ Score using LLM
            # ! Currently no retrying to LLM for failed Jobs Directly marking them failed b'coz it's not part of this flow to retry LLM failures. We can have a separate flow to retry LLM failures if needed.
            # Either use Langraph pipelines or have our own retry mechanism here. Langraph has built in retry mechanism which we can leverage if we use their pipelines.
            score_results, scoring_failed = await self._score_batch_parsed_text(
                payload, rubric
            )
            
            
            self.logger.warning(f"Score results count: {len(score_results)}")
            self.logger.warning(f"Returned IDs: {[r.resume_id for r in score_results]}")
            self.logger.warning(f"Expected IDs: {[r.id for r in resumes]}")

            # 5️⃣ Persist successes
            candidate_tasks, processing_failed_ids = (
                await self._persist_success_results(
                    score_results,
                    resumes,
                    rubric,
                    batch_id,
                )
            )

            # 6️⃣ Detect missing results
            missing_ids = self._detect_missing_results(
                score_results, resumes
            )
            processing_failed_ids.extend(missing_ids)

            # 7️⃣ Handle processing failures
            if processing_failed_ids:
                self.score_text_logger.warning(
                    f"Processinng failed for resume_ids: {[f.resume_id for f in scoring_failed]}"
                )
                await self._mark_processing_failures(
                    processing_failed_ids, batch_id
                )
                
            if scoring_failed:
                self.score_text_logger.warning(
                    f"Scoring failed for resume_ids: {[f.resume_id for f in scoring_failed]}"
                )
                scoring_failed_ids = [f.resume_id for f in scoring_failed]
                await self._mark_processing_failures(
                    scoring_failed_ids, batch_id
                )
                # ! Not enqueing again reason given above since we don't want to retry LLM failures in this flow. 
                # If we want to retry only the scoring step without re-processing the resume, we can enqueue the failed resumes for scoring again without changing their status back to QUEUED_FOR_SCORING 
                # since they are already parsed successfully and we only want to retry the scoring step.
                # The job producer will handle enqueuing them to the appropriate scoring queue based on the scoring_type.
                
                # await self._retry_scoring_failures(
                #     scoring_failed, db_job_id, batch_id,
                #     scoring_type="text",
                # )

            # 8️⃣ Commit all DB changes
            await self.db.commit()

            # 9️⃣ Side effects AFTER commit
            if candidate_tasks:
                await asyncio.gather(*candidate_tasks)

            # Retry scoring failures only (text scoring)
            
           

            return self._build_summary(
                resumes,
                processing_failed_ids,
                scoring_failed,
                batch_id,
            )

        except Exception:
            await self.db.rollback()
            self.score_text_logger.exception(
                f"Fatal error scoring batch {batch_id}"
            )
            raise

            

    async def score_url_resumes(
        self,
        db_job_id: str,
        resume_ids: List[str],
        batch_id: str,
    ) -> Optional[dict]:

        if not resume_ids:
            self.score_url_logger.warning(
                f"Empty resume batch for batch_id={batch_id}"
            )
            return None

        try:
            # 1️⃣ Validate job
            job = await self._validate_job(db_job_id)

            # 2️⃣ Fetch resumes (with status transition)
            resumes = await self._fetch_resumes(
                db_job_id, resume_ids
            )
            if not resumes:
                return None

            rubric = await self._get_rubric(db_job_id)

            # 3️⃣ Prepare payload
            payload = self._build_payload_url(resumes)

            # 4️⃣ Score using LLM
            score_results, scoring_failed = await score_resume_with_url(
                resumes=payload,
                criteria=rubric.criteria,
            )

            # 5️⃣ Persist successes
            candidate_tasks, processing_failed_ids = (
                await self._persist_success_results(
                    score_results,
                    resumes,
                    rubric,
                    batch_id,
                )
            )

            # 6️⃣ Detect missing results
            missing_ids = self._detect_missing_results(
                score_results, resumes
            )
            processing_failed_ids.extend(missing_ids)

            # 7️⃣ Handle processing failures
            if processing_failed_ids:
                await self._mark_processing_failures(
                    processing_failed_ids, batch_id
                )
                
            # 10. Retry scoring failures only
            if scoring_failed:
                scoring_failed_ids = [f.resume_id for f in scoring_failed]
                await self._mark_processing_failures(
                    scoring_failed_ids, batch_id
                )
                # ! Not enqueing again reason given above since we don't want to retry LLM failures in this flow. 
                # If we want to retry only the scoring step without re-processing the resume, we can enqueue the failed resumes for scoring again without changing their status back to QUEUED_FOR_SCORING 
                # since they are already parsed successfully and we only want to retry the scoring step.
                
                # await self._retry_scoring_failures(
                #     scoring_failed, db_job_id, batch_id,
                #     scoring_type="url",
                # )
                

            # 8️⃣ Commit all DB changes
            await self.db.commit()
            
            

            # 9️⃣ Side effects AFTER commit
            if candidate_tasks:
                await asyncio.gather(*candidate_tasks)

            

            return self._build_summary(
                resumes,
                processing_failed_ids,
                scoring_failed,
                batch_id,
            )

        except Exception:
            await self.db.rollback()
            self.score_url_logger.exception(
                f"Fatal error scoring batch {batch_id}"
            )
            raise

    # =========================================================
    # PRIVATE HELPERS
    # =========================================================
    
    async def _validate_job(self, db_job_id):
        """Validate that the job exists and is in a valid state for scoring."""
        job = await self.job_repository.get_job_by_id(db_job_id)
        if not job:
            raise DomainError(f"Job {db_job_id} not found")
        return job

    async def _fetch_resumes(self, db_job_id, resume_ids):
        """Fetch resumes for scoring, ensuring they are in the correct status, and transition them to 'SCORING_IN_PROGRESS' atomically to avoid double processing."""
        resumes = await self.resume_repository.fetch_resumes_for_scoring(
            job_id=db_job_id,
            status=ResumeStatus.QUEUED_FOR_SCORING,
            resume_ids=resume_ids,
            new_status=ResumeStatus.SCORING_IN_PROGRESS,
        )

        if not resumes:
            self.logger.warning("No eligible resumes found")
        return resumes

    async def _get_rubric(self, db_job_id):
        """Fetch the active rubric for the job. This is needed to know the scoring criteria and threshold."""
        rubric = await self.job_repository.get_active_rubric(db_job_id)
        if not rubric:
            self.logger.error(f"No active rubric found for job {db_job_id}")
            raise DomainError("No active rubric found")
        return rubric

    def _build_payload_parsed_text(self, resumes):
        """Build the payload for scoring parsed text resumes.Using ResumeDataSchema which has application_id, resume_id and parsed_text."""
        return [
            ResumeDataSchema(
                application_id=r.application_id,
                resume_id=r.id,
                resume_text=r.parsed_text,
            )
            for r in resumes
        ]
        
    def _build_payload_url(self, resumes):
        """Build the payload for scoring URL resumes. Using ResumeDataSchemaURL which has application_id, resume_id and resume_url."""
        return [
            ResumeDataSchemaURL(
                application_id=r.application_id,
                resume_id=r.id,
                resume_url=r.raw_file_url,
            )
            for r in resumes
        ]

    async def _score_batch_parsed_text(self, payload, rubric):
        """Score a batch of parsed text resumes using the LLM pipeline."""
        return await score_resume_with_text(
            resumes=payload,
            criteria=rubric.criteria,
        )
     
    async def _persist_success_results(
        self,
        score_results,
        resumes,
        rubric,
        batch_id,
    ):
        """
        Persist successful scoring results to the database, update resume and application records, and enqueue candidate extraction tasks if needed.
        """
        applications = await self.application_repository.get_application_by_application_ids(
            application_ids={r.application_id for r in resumes}
        )
        application_map = {a.id: a for a in applications}
        resume_map = {str(r.id): r for r in resumes}


        candidate_tasks = []
        processing_failed_ids = []

        for item in score_results:
            try:
                # item = ResumeScoreResult(**raw)

                appl = application_map.get(item.application_id)
                if appl:
                    appl.ai_analysis = item.score.ai_analysis

                resume = resume_map.get(str(item.resume_id))
                
                if resume:
                    resume.status = ResumeStatus.SCORED

                await self.score_repository.add_score(
                    application_id=item.application_id,
                    criteria=rubric.criteria,
                    model_name="Gemini-2.5-Flash-lite",
                    rubric_id=rubric.id,
                    score=item.score,
                    scored_by="AI",
                    threshold_score=rubric.threshold_score,
                )

                candidate_info = item.score.candidate_info
                if candidate_info and candidate_info.full_name:
                    candidate_tasks.append(
                        self.job_producer.enqueue_candidate_extraction(
                            resume_id=item.resume_id,
                            batch_id=batch_id,
                            candidate=candidate_info,
                        )
                    )

            except Exception as e:
                rid = item.resume_id
                self.logger.exception(
                    f"Processing error resume_id={rid},error is {str(e)}"
                )
                processing_failed_ids.append(rid)

        return candidate_tasks, processing_failed_ids




    def _detect_missing_results(self, score_results, resumes):
        """Detect resumes that were expected to be scored but did not return any results, which can indicate a failure in the scoring process for those resumes. This is a safeguard to ensure we account for all resumes in the batch."""

        returned_ids = {str(r.resume_id).lower() for r in score_results}
        expected_ids = {str(r.id).lower() for r in resumes}

        return list(expected_ids - returned_ids)



    async def _mark_processing_failures(
        self,
        resume_ids,
        batch_id,
    ):
        
        self.logger.error(f"Marking processing failures for resume_ids: {resume_ids} in batch_id: {batch_id}")
        """Mark resumes that failed processing with an error status and update the batch failure count."""
        await self.resume_repository.update_resume_status(
            resume_ids=resume_ids,
            new_status=ResumeStatus.ERROR,
        )

        await self.batch_repository.increment_failure(
            batch_id=batch_id,
            increased_failed_count_by=len(resume_ids),
        )



    async def _retry_scoring_failures(
        self,
        failures,
        db_job_id,
        batch_id,
        scoring_type: str = "text",
    ):
        """
        Retry scoring for resumes that failed scoring. This can be used to retry only the scoring step without re-processing the resume. Depending on the failure reason, you might want to add more sophisticated retry logic or limits here.
        Again Enqueuing the failed resumes for scoring without re-processing since the parsing was successful and we only want to retry the scoring step. The job producer will handle enqueuing them to the appropriate scoring queue based on the scoring_type.
        """
        failed_ids = [f.resume_id for f in failures]

        await self.resume_repository.update_resume_status(
            resume_ids=failed_ids,
            new_status=ResumeStatus.QUEUED_FOR_SCORING,
        )

        if scoring_type == "url":
            await self.job_producer.enqueue_url_scoring(
                job_id=db_job_id,
                resume_ids=failed_ids,
                db_batch_id=batch_id,
            )
        else:
            await self.job_producer.enqueue_text_scoring(
                job_id=db_job_id,
                resume_ids=failed_ids,
                db_batch_id=batch_id,
            )

    def _build_summary(
        self,
        resumes,
        processing_failed,
        scoring_failed,
        batch_id,
    ):
        """Build a summary of the scoring results for the batch, including counts of scored, processing failed, and scoring failed resumes."""
        
        success_count = sum(
            1 for r in resumes if r.status == ResumeStatus.SCORED
        )

        return {
            "status": "BATCH_COMPLETED",
            "batch_id": batch_id,
            "scored_count": success_count,
            "failed_count": len(processing_failed)
            + len(scoring_failed),
        }
