from fastapi import status,UploadFile,BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from src.models import Job,Rubric,BulkUploadBatches

from  configs.log_config import get_logger

from src.schemas.user_schemas import NewJobSchema
from src.schemas.job_schemas import JobOverviewResponse,JobOverviewResponseNew,JobOverviewInfo,DashboardInfo,CriteriaOverview,RubricVersionInfo

from src.services.errors.user_errors import JDExtractionFailed,JobNotFound,RubricNotFound
from src.services.errors.base import DomainError
from typing import Optional,List
from src.repositories.batch_repositoy import BatchRepository 
from src.utils.extract_pdf import extract_text_from_pdf
from src.pipelines.generate_rubric import generate_rubric_from_jd
# from workers.producer import enqueue_resumes_parsing
from src.repositories.job_repository import JobRepository
from src.repositories.org_repository import OrganizationRepository 
from src.repositories.application_repository import ApplicationRepository
from src.utils.file_manager import FileManagerService
from src.utils.file_manager import fileManager
from configs.env_config import SUPABASE_PUBLIC_URL
# from src.pipelines.score_resume_ocr import score_img_format_resume_files
# from src.pipelines.score_resume_ocr import score_image_resumes_async
from src.repositories.resume_respositoy import ResumeRepository
from workers.new_producer import ARQProducer
import json


class JobService:
    def __init__(self,job_repositoy:JobRepository,batch_repository:BatchRepository,org_repository,application_repository:ApplicationRepository,resume_repository:ResumeRepository,job_producer:ARQProducer,db: AsyncSession):
        self.db = db #TODO: remove this from service layer 
        self.PUBLIC_URL = SUPABASE_PUBLIC_URL
        self.job_repository:JobRepository = job_repositoy
        self.application_repository:ApplicationRepository = application_repository
        self.resume_repository:ResumeRepository = resume_repository
        self.batch_repository:BatchRepository = batch_repository    
        self.organization_repository:OrganizationRepository = org_repository
        self.job_producer: ARQProducer = job_producer
        # self.job_producer: ARQProducer = job_producer
        self.file_manager:FileManagerService = fileManager
        self.logger = get_logger("JOB_SERVICE")
        
    
    def generate_batch_name(self,job_id:str) -> str:
        return f"application_processing_{job_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        
 
    async def add_new_job(self, data: NewJobSchema, user_id: str, org_id: Optional[str]):
        
        try:
            new_job = await self.job_repository.create_job(job_data=data.job_data,user_id=user_id)
            
            if org_id:
                organization = await self.organization_repository.get_organization_by_id(org_id)
                if not organization:
                    raise ValueError("Organization not found")
                new_job.organization = organization
           

            job_id = new_job.id

            existing_rubrics = await self.job_repository.get_all_rubrics(job_id=job_id)

            new_version = 1
            for rubric in existing_rubrics:
                rubric.is_active = False
                new_version = max(new_version, rubric.version + 1)
            
            # TODO: make a repo method to handle rubric versioning and creation in one transaction to avoid race conditions
            # 5. Create rubric
            new_rubric = Rubric(
                version=new_version,
                threshold_score=data.threshold_score,
                criteria=data.criteria.model_dump(),
                job_id=job_id,
                is_active=True,
            )

            self.db.add(new_rubric)

            # 6. Commit transaction
            await self.db.commit()
            await self.db.refresh(new_job)

            return job_id
        except Exception as e:
            await self.db.rollback()
            self.logger.exception(f"Error adding new job: {e}")
            raise
            
    # TODO: later pagination and filters
    async def get_jobs(self,user_id : str, organization_id: Optional[str] = None) -> list[dict]:
        try:
            
            Jobs = []
            
            if organization_id:
                Jobs  = await self.job_repository.get_jobs_by_organization(organization_id)
            else:
                Jobs = await self.job_repository.get_jobs_by_user_personal(user_id)
                
            if len(Jobs) == 0:
                return []
            
            job_list = []
            for job in Jobs:
                job_list.append({
                    "id": job.id,
                    "title": job.title,
                    "location": job.location,
                    "status": job.status.value,
                    "target_headcount": job.target_headcount,
                    "jd_url":"null",
                    "created_at": job.created_at.isoformat(),
                })
            
            return job_list
        
        except Exception as e:
            self.logger.error(f"Error fetching jobs: {e}")
            raise

    async def extract_jd(self,file: UploadFile) -> dict:
        try:
        
            jd_input = await extract_text_from_pdf(file)

            if len(jd_input) < 100:
                raise JDExtractionFailed(
                    message="Extracted JD content is too short",
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            # 3. Generate rubric via LLM
            rubric_data = await generate_rubric_from_jd(jd_input)
            rubric_dict = rubric_data.model_dump()

            
            # 7. Return clean response
            return {
                "job_data": rubric_dict["job_data"],
                "threshold_score": rubric_dict["threshold_score"],
                "criteria": {
                    "mandatory_criteria":rubric_dict["mandatory_criteria"],
                    "screening_criteria":rubric_dict["screening_criteria"]
                    }
            }

        except Exception as e:
            self.logger.exception(f"Error extracting JD: {e}")
            await self.db.rollback()
            raise

    async def get_job_overview(
        self,
        job_id: str,
        organization_id: Optional[str] = None
        ) :
        # ---------- Job ----------
        
        try:
            job:Job | None = await self.job_repository.get_job_by_id(job_id=job_id)
            
            #TODO: should check orgid if job is org specific

            if not job:
                raise JobNotFound(status_code=404)

            # ---------- Active Rubric (Criteria) ----------
            
            rubric:Rubric | None = await self.job_repository.get_active_rubric(job_id=job_id)
            if not rubric:
                raise RubricNotFound(
                    message="Active rubric not found",
                    status_code=404
                )

            # ---------- Dashboard Analytics ----------

            analytics_result = await self.application_repository.get_applications_by_group(job_id=job_id)
            analytics = {
                status.value: count
                for status, count in analytics_result
            }

            total_applications = sum(analytics.values())

            # ---------- Response ----------
            return {
                "job": {
                    "id": job.id,
                    "title": job.title,
                    "status": job.status,
                    "description": job.description,
                    "created_at": job.created_at,
                    "salary": job.salary,
                    "location": job.location,
                    "target_headcount": job.target_headcount,
                    "current_batch_id": job.active_processing_queue_id,
                },
                "dashboard": {
                    "total_applications": total_applications,
                    "by_status": analytics,
                },
                "criteria": {
                    "rubric_id": rubric.id,
                    "version": rubric.version,
                    "threshold_score": rubric.threshold_score,
                    "criteria": rubric.criteria,
                },
                "settings": {
                    "voice_ai_enabled": job.voice_ai_enabled,
                    "manual_rounds_count": job.manual_rounds_count,
                    "is_confidential": job.is_confidential,
                    "job_metadata": job.job_metadata,
                    "closing_reason": job.closing_reason,
                }
            }
        except Exception as e:
            self.logger.exception(f"Error fetching job overview for job_id {job_id}: {e}")
            raise
        
    async def get_job_overview2(
        self,
        job_id: str,
        organization_id: Optional[str] = None
        ) -> JobOverviewResponseNew:
        # ---------- Job ----------
        
        try:
            job:Job | None = await self.job_repository.get_job_by_id(job_id=job_id)
            
            #TODO: should check orgid if job is org specific

            if not job:
                raise JobNotFound(status_code=404)

            # ---------- Active Rubric (Criteria) ----------
            
            active_rubric_version = await self.job_repository.get_active_rubric_version(job_id=job_id)
            if not active_rubric_version:
                raise RubricNotFound(
                    message="No active rubric version found for the job",
                    status_code=404
                )
                
            rubric_versions = await self.job_repository.get_all_rubrics_versions(job_id=job_id)
            
            if not rubric_versions:
                rubric_versions = []

            # ---------- Dashboard Analytics ----------

            analytics_result = await self.application_repository.get_applications_by_group(job_id=job_id)
            analytics = {
                status.value: count
                for status, count in analytics_result
            }
            avg_match_score = await self.application_repository.get_avg_match_score(job_id=job_id)

            total_applications = sum(analytics.values())

            # ---------- Response ----------
            return JobOverviewResponseNew(
                    job=JobOverviewInfo(
                        id=job.id,
                        title=job.title,
                        status=job.status,
                        description=job.description,
                        created_at=job.created_at,
                        salary=job.salary,
                        location=job.location,
                        target_headcount=job.target_headcount,
                        current_batch_id=job.active_processing_queue_id,
                    ),
                    dashboard=DashboardInfo(
                        total_applications=total_applications,
                        by_status=analytics,
                        avg_score=float(avg_match_score or 0.0),
                    ),
                    criteria=CriteriaOverview(
                        current_active_version=active_rubric_version["version"],
                        active_rubric_id=active_rubric_version["id"],
                        versions=[
                            RubricVersionInfo(**rv)
                            for rv in rubric_versions
                        ]
                    )
                )

        except Exception as e:
            self.logger.exception(f"Error fetching job overview for job_id {job_id}: {e}")
            raise

    async def process_applications(
        self,
        job_id: str,
        user_id: str,
        files: List[UploadFile],
        background_tasks: BackgroundTasks = None,
        organization_id: Optional[str] = None, #TODO: add it
    ) -> dict:

        try:
            # 1. Fetch job
            job : Job | None = await self.job_repository.get_job_by_id(job_id=job_id)

            if not job:
                raise JobNotFound(status_code=404)

            # 2. Prevent duplicate processing
            #! activate for production
            # if job.active_processing_queue_id:
            #     raise DomainError(
            #         message="An active application processing job already exists for this job.",
            #         status_code=status.HTTP_409_CONFLICT
            #     )

            
            batch_name = self.generate_batch_name(job_id=job_id)
            
            
            # 4. Stage files to storage
            files_uploaded_dir,saved_paths = await self.file_manager.stage_uploaded_files(
                dir_name = batch_name,
                files=files,
            )
            

            # 5. Create processing job
            batch = await self.batch_repository.create_batch(
                job_id=job_id,
                user_id=user_id,
                source_file_url=json.dumps(saved_paths), #TODO: change this to array in DB
                batch_name=batch_name,
                total_files=len(saved_paths)
            )

            job.active_processing_queue_id = batch.id
            await self.db.commit()
            await self.db.refresh(job)


            # TODO:
            # For very large uploads (>500–1000 resumes),
            # replace per-resume enqueueing with a single job that processes the batch in one go to avoid overwhelming Redis and the worker queue with too many jobs at once. The worker can then read the batch info, iterate over the files, and process them sequentially or in controlled parallelism.
            # batch-orchestrator job that fans out work
            # from a worker to keep API latency low.
            await self.job_producer.enqueue_resumes_parsing(
                resume_paths=saved_paths,
                db_job_id=job.id,
                batch_id=batch.id,
                )

            return {
                # "processing_job_id": batch.id,
                "directory_path": files_uploaded_dir,
                "status": "queued"
            }
        
        except Exception as e:
            await self.db.rollback()
            self.logger.exception(f"Error processing applications for job {job_id}: {e}")
            raise
    
    async def get_applications(
        self,
        job_id: str,
        page: int = 1,
        page_size: int = 20,
    ):
        if page < 1:
            page = 1

        offset = (page - 1) * page_size

    
        total = await self.application_repository.get_total_applications_count(job_id=job_id)
        active_rubric = await self.job_repository.get_active_rubric(job_id=job_id)
        
        if not active_rubric:
            raise RubricNotFound( message="Active rubric not found for the job", status_code=404 )
        
        # TODO: need to pass current rubric id of the job to fetch score on that basis either it can come from user too
        applications = await self.application_repository.get_applications_of_job(job_id=job_id, current_rubric_id=active_rubric.id, page_size=page_size, offset=offset )
        
        response = []

        for app,score in applications:
            # 🔹 active score only
            active_score =  score if score else None
            # 🔹 fetch ONLY current resume
            resume = app.resume if app.resume else None

            app_data = {
                "id": str(app.id),
                "current_round": app.current_round,
                "is_starred": app.is_starred,
                "denormalized_rank": app.denormalized_rank,
                "is_flagged": app.is_flagged,
                "offer_letter_url": app.offer_letter_url,
                "flag_reason": app.flag_reason,
                "tags": app.tags,
                "last_activity_at": (
                    app.last_activity_at.isoformat()
                    if app.last_activity_at else None
                ),
                "deleted_at": (
                    app.deleted_at.isoformat()
                    if app.deleted_at else None
                ),
                "status": app.status.value,
                "created_at": app.created_at.isoformat(),
                "updated_at": app.updated_at.isoformat(),
                "ai_analysis": app.ai_analysis,
            }

            
            # ✅ candidate (minimal)
            app_data["candidate"] = {
                "id": str(app.candidate.id),
                "full_name": app.candidate.full_name,
                "email": app.candidate.email,
                "phone": app.candidate.phone,
            } if app.candidate else None

            # ✅ resume (current only)
            app_data["resume"] = {
                "id": str(resume.id),
                "raw_file_url": f"{self.PUBLIC_URL}/{resume.raw_file_url}",
                "status": resume.status,
                "page_count": resume.page_count,
                "uploaded_at": resume.uploaded_at.isoformat(),
            } if resume else None

            # ✅ active score only
            app_data["scores"] = {
                    "is_active": active_score.is_active,
                    "overall_score": active_score.overall_score,
                    "ai_confidence": active_score.ai_confidence,
                    "created_at": active_score.created_at.isoformat(),
                    "grounding_data": active_score.grounding_data,
                    "breakdown": active_score.breakdown,
                    "is_overridden": active_score.is_overridden,
                    "version": active_score.version,
                    "is_latest": active_score.is_latest,
                } if active_score else {}

            response.append(app_data)

        return {
            "applications": response,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size
            }
        }

    # async def score_resume_ocr(self,job_id:str,resume_url:List[str]):
    #     try:
    #         rubric = await self.job_repository.get_active_rubric(job_id=job_id)
    #         # score = await score_img_format_resume_files(
    #         #     resume_url=resume_url,
    #         #     criteria=rubric.criteria if rubric else None
    #         # )
            
            
    #         score = await score_image_resumes_async(
    #             resume_urls=resume_url,
    #             criteria=rubric.criteria if rubric else None
    #         )
            
    #         return score
            
    #     except Exception as e:
    #         self.logger.exception(f"Error scoring resume OCR: {e}")
    #         raise