"""
Job Service — handles all business logic for job + rubric lifecycle.

Key design principles:
  - DB writes ONLY happen when user clicks "Set Rubric" (for new job)
    or "Update Rubric" (for existing job).
  - extract_jd() is a pure AI operation — no DB writes.
  - All mutations are wrapped in a single transaction with rollback on failure.
  - Backward compatibility: reads v1 rubrics and converts them on-the-fly.
"""

from fastapi import UploadFile, BackgroundTasks,status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from typing import Optional, List
from src.services.errors.base import DomainError
from src.models import Job, Rubric, BulkUploadBatches
from src.schemas.rubric_schemas import (
    SetRubricRequest,
    UpdateRubricRequest,
    read_rubric_criteria,
)
from src.schemas.job_schemas import NewJobSchema,JobOverviewResponseNew,JobOverviewInfo,DashboardInfo,CriteriaOverview,RubricVersionInfo
from src.services.errors.user_errors import JobNotFound, RubricNotFound
from src.services.errors.pipeline_errors import (
    JDTooShort,
    JDNotReadable,
)
from src.repositories.job_repository import JobRepository
from src.repositories.batch_repositoy import BatchRepository
from src.repositories.application_repository import ApplicationRepository
from src.repositories.resume_respositoy import ResumeRepository
from async_workers.new_producer import ARQProducer
from src.repositories.org_repository import OrganizationRepository
from src.utils.extract_pdf import extract_text_from_pdf
from src.utils.file_manager import FileManagerService, fileManager
from src.pipelines.generate_rubric import generate_rubric_from_jd
from src.pipelines.jd_basic_analysis import analyze_jd_basic
from workers.producer import enqueue_resumes_parsing
from configs.env_config import SUPABASE_PUBLIC_URL
from configs.log_config import get_logger
from src.repositories.document_repository import DocumentRepository
from uuid import UUID
import time
import json


def _job_status_for_api(status) -> str:
    """Normalize job status for API: DB enum may be 'OPEN'; API contract is lowercase."""
    v = status.value
    return v if v == "draft" else v.lower()


class JobService:        
    def __init__(self,job_repositoy:JobRepository,batch_repository:BatchRepository,org_repository,application_repository:ApplicationRepository,resume_repository:ResumeRepository,job_producer:ARQProducer,db: AsyncSession):
        self.db = db 
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

    # ─── Helpers ─────────────────────────────────────────────────────

    def _generate_batch_name(self, job_id: str) -> str:
        return f"application_processing_{job_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    async def validate_job(self, job_id: str, organization_id: Optional[str] = None) -> Job:
        job = await self.job_repository.get_job_by_id(job_id=job_id)
        if not job:
            raise JobNotFound(status_code=404)
        
        if organization_id and job.organization_id != organization_id:
            raise JobNotFound(status_code=404)

        return job
    
     
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
           
    
    # ─── 1. Extract JD (preview only — NO DB writes) ──────────────────

    async def extract_jd(self, file: UploadFile) -> dict:
        """
        Extract text from a JD file and run a LIGHT basic AI analysis.
        Returns domain + job_data for fast frontend prefill.
        Does NOT write anything to DB.
        """
        try:
            t0 = time.time()
            jd_text = await extract_text_from_pdf(file)
            self.logger.info("JD text extracted in %dms", int((time.time() - t0) * 1000))

            if not jd_text or len(jd_text.strip()) < 50:
                raise JDNotReadable(
                    message="Could not extract readable text from the uploaded file.",
                    status_code=400,
                )

            if len(jd_text) < 100:
                raise JDTooShort(
                    message="The extracted job description is too short (< 100 chars).",
                    status_code=400,
                )

            t1 = time.time()
            analysis = await analyze_jd_basic(jd_text)
            self.logger.info("Basic JD analysis completed in %dms", int((time.time() - t1) * 1000))
            analysis["raw_jd_text"] = jd_text
            return analysis

        except (JDTooShort, JDNotReadable):
            raise
        except Exception as e:
            self.logger.exception("Error extracting JD: %s", e)
            raise

    async def generate_rubric_preview(self, raw_jd_text: str, job_data: dict) -> dict:
        """
        Generate the rubric (groups + weights) from raw JD text + user-entered job_data (temp JSON).
        The job_data is passed to the AI so it can use location/salary/degree/title context
        entered by the user on the basic-details form when creating rubric criteria.
        No DB writes happen here — this is purely an AI operation.
        """
        t0 = time.time()
        rubric_payload = await generate_rubric_from_jd(raw_jd_text, job_data=job_data, use_cache=False)
        self.logger.info("Rubric generation completed in %dms", int((time.time() - t0) * 1000))

        # Keep user-edited job_data as source of truth
        rubric_payload["job_data"] = job_data
        rubric_payload["raw_jd_text"] = raw_jd_text

        # Log resultant JSON for debugging (truncate to keep logs readable)
        try:
            dumped = json.dumps(rubric_payload, ensure_ascii=False)
            max_len = 12000
            if len(dumped) > max_len:
                self.logger.info("Rubric preview JSON (truncated %d chars): %s", len(dumped), dumped[:max_len])
            else:
                self.logger.info("Rubric preview JSON: %s", dumped)
        except Exception as e:
            self.logger.warning("Failed to log rubric JSON: %s", e)

        return rubric_payload

    async def reparse_jd(self, job_id: str, file: UploadFile) -> dict:
        """
        Re-parse JD for existing job (preview only — NO DB writes).
        """
        try:
            jd_text = await extract_text_from_pdf(file)

            if len(jd_text) < 100:
                raise JDTooShort()
            rubric_data = await generate_rubric_from_jd(jd_text)
            rubric_data["raw_jd_text"] = jd_text
            rubric_data["job_id"] = job_id
            return rubric_data

        except Exception as e:
            self.logger.exception(f"Error re-parsing JD for job {job_id}: %s", e)
            raise

    # ─── 2. Set Rubric (Create Job + Rubric in one transaction) ──────

    async def set_rubric(
        self,
        data: SetRubricRequest,
        user_id: str,
        org_id: Optional[str] = None,
    ) -> dict:
        """
        Called when user clicks "Set Rubric" for a NEW job.
        Creates both Job and Rubric in a single atomic transaction.
        """
        try:
            # 1. Create the Job
            new_job = await self.job_repository.create_job(
                job_data=data.job_data,
                user_id=user_id,
            )

            # 2. Link to organization if provided
            if org_id:
                organization = await self.organization_repository.get_organization_by_id(org_id)
                if not organization:
                    raise ValueError("Organization not found")
                new_job.organization = organization

            # 3. Persist raw JD text on the job
            if data.raw_jd_text:
                new_job.raw_jd_text = data.raw_jd_text

            # 4. Store domain info in job_metadata
            new_job.job_metadata = {
                **(new_job.job_metadata or {}),
                "domain": data.domain,
            }

            job_id = str(new_job.id)

            # 5. Build the criteria JSONB (v2 format with schema_version)
            criteria_jsonb = {
                "schema_version": 2,
                "sections": [s.model_dump() for s in data.sections],
            }

            # 6. Create the rubric (version 1, active)
            new_rubric = await self.job_repository.create_rubric(
                job_id=job_id,
                criteria=criteria_jsonb,
                threshold_score=data.threshold_score,
                version=1,
                ai_metadata={
                    "domain": data.domain,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "source": "ai_with_user_edits",
                },
                source="combined",
                parent_rubric_id=None,
                created_by_id=user_id,
                created_via="create_job",
                change_reason="initial",
                change_type="major",
            )

            # 7. Commit the full transaction
            await self.db.commit()
            await self.db.refresh(new_job)

            self.logger.info(
                "Job %s and rubric %s created successfully",
                job_id,
                new_rubric.id,
            )

            return {
                "job_id": job_id,
                "rubric_id": str(new_rubric.id),
                "rubric_version": new_rubric.version,
            }

        except Exception as e:
            await self.db.rollback()
            self.logger.exception("Error in set_rubric: %s", e)
            raise

    # ─── 3. Update Rubric on Existing Job ────────────────────────────

    async def update_rubric(
        self,
        job_id: str,
        data: UpdateRubricRequest,
        user_id: str,
    ) -> dict:
        """
        Creates a new rubric version for an existing job.
        Deactivates old rubrics, creates new one.
        """
        try:
            # Verify job exists
            job = await self.job_repository.get_job_by_id(job_id)
            if not job:
                raise JobNotFound(status_code=404)

            # Capture current active rubric for lineage (before deactivation)
            parent = await self.job_repository.get_active_rubric(job_id)

            # Get next version number
            current_version = await self.job_repository.get_latest_rubric_version(job_id)
            new_version = current_version + 1

            # Deactivate all existing rubrics
            await self.job_repository.deactivate_all_rubrics(job_id)

            # Build criteria JSONB
            criteria_jsonb = {
                "schema_version": 2,
                "sections": [s.model_dump() for s in data.sections],
            }

            # Update raw JD text if provided
            if data.raw_jd_text:
                await self.job_repository.update_job_jd_text(
                    job_id=job_id,
                    raw_jd_text=data.raw_jd_text,
                )

            # Create new rubric version
            new_rubric = await self.job_repository.create_rubric(
                job_id=job_id,
                criteria=criteria_jsonb,
                threshold_score=data.threshold_score,
                version=new_version,
                ai_metadata={
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "updated_by": str(user_id),
                    "source": data.created_via or "ui_edit",
                },
                source=data.source or "manual",
                parent_rubric_id=str(parent.id) if parent else None,
                created_by_id=user_id,
                created_via=data.created_via or "ui_edit",
                change_reason=data.change_reason or "edit",
                change_type=data.change_type or "major",
            )

            await self.db.commit()

            self.logger.info(
                "Rubric v%d created for job %s",
                new_version,
                job_id,
            )

            return {
                "rubric_id": str(new_rubric.id),
                "rubric_version": new_rubric.version,
            }

        except JobNotFound:
            raise
        except Exception as e:
            await self.db.rollback()
            self.logger.exception("Error updating rubric for job %s: %s", job_id, e)
            raise

    # ─── 4. Regenerate Rubric via AI for Existing Job ────────────────

    async def regenerate_rubric(self, job_id: str, file: UploadFile) -> dict:
        """
        Upload a new JD for an existing job and generate a rubric preview only.
        Does NOT save to DB — returns the preview for user editing.
        The user must call update_rubric to save.
        """
        job = await self.job_repository.get_job_by_id(job_id)
        if not job:
            raise JobNotFound(status_code=404)

        jd_text = await extract_text_from_pdf(file)
        if not jd_text or len(jd_text.strip()) < 50:
            raise JDNotReadable(
                message="Could not extract readable text from the uploaded file.",
                status_code=400,
            )
        if len(jd_text) < 100:
            raise JDTooShort(
                message="The extracted job description is too short (< 100 chars).",
                status_code=400,
            )

        rubric_data = await generate_rubric_from_jd(jd_text)
        rubric_data["raw_jd_text"] = jd_text
        return rubric_data

    # ─── Rubric Versioning (audit + switching) ───────────────────────

    async def get_rubric_versions(self, job_id: str) -> dict:
        job = await self.job_repository.get_job_by_id(job_id)
        if not job:
            raise JobNotFound(status_code=404)

        rubrics = await self.job_repository.get_all_rubrics(job_id)
        active = next((r for r in rubrics if r.is_active), None)

        return {
            "job_id": job.id,
            "active_rubric_id": active.id if active else None,
            "versions": [
                {
                    "rubric_id": r.id,
                    "version": r.version,
                    "is_active": bool(r.is_active),
                    "source": r.source,
                    "created_at": r.created_at,
                    "created_by_id": r.created_by_id,
                    "created_via": r.created_via,
                    "change_reason": r.change_reason,
                    "change_type": r.change_type,
                    "parent_rubric_id": r.parent_rubric_id,
                }
                for r in rubrics
            ],
        }

    async def activate_rubric_version(self, job_id: str, rubric_id: str, user_id: str) -> dict:
        job = await self.job_repository.get_job_by_id(job_id)
        if not job:
            raise JobNotFound(status_code=404)

        rubric = await self.job_repository.activate_rubric(job_id=job_id, rubric_id=rubric_id)
        if not rubric:
            raise RubricNotFound(
                message="Rubric not found for the job",
                status_code=404,
            )

        # Record activation audit in ai_metadata (cheap audit; full audit trail is the version table)
        try:
            rubric.ai_metadata = {
                **(rubric.ai_metadata or {}),
                "activated_at": datetime.now(timezone.utc).isoformat(),
                "activated_by": str(user_id),
            }
        except Exception:
            pass

        await self.db.commit()

        return {
            "job_id": job.id,
            "active_rubric_id": rubric.id,
            "active_version": rubric.version,
        }

    # ─── 5. Get Jobs List ────────────────────────────────────────────

    async def get_jobs(self, user_id: str, organization_id: Optional[str] = None) -> list[dict]:
        try:
            if organization_id:
                jobs = await self.job_repository.get_jobs_by_organization(organization_id)
            else:
                jobs = await self.job_repository.get_jobs_by_user_personal(user_id)

            if not jobs:
                return []

            return [
                {
                    "id": job.id,
                    "title": job.title,
                    "location": job.location,
                    "status": _job_status_for_api(job.status),
                    "target_headcount": job.target_headcount,
                    "jd_url": "null",
                    "created_at": job.created_at.isoformat(),
                }
                for job in jobs
            ]

        except Exception as e:
            self.logger.error("Error fetching jobs: %s", e)
            raise

    # ─── 6. Get Job Overview ─────────────────────────────────────────

    async def delete_job(self, job_id: str) -> dict:
        """
        Delete a job and all its associated data (rubrics, applications, scores, etc.).
        Deletes in dependency order then commits; caller must use same session for commit to persist.
        """
        job = await self.job_repository.get_job_by_id(job_id)
        if not job:
            raise JobNotFound(status_code=404)

        job_title = job.title
        try:
            deleted = await self.job_repository.delete_job(job_id)
            if not deleted:
                raise JobNotFound(status_code=404)
            await self.db.commit()
            self.logger.info("Deleted job %s: %s", job_id, job_title)
            return {
                "job_id": str(job_id),
                "job_title": job_title,
                "message": "Job and all associated data deleted successfully",
            }
        except JobNotFound:
            raise
        except Exception as e:
            await self.db.rollback()
            self.logger.exception("Error deleting job %s: %s", job_id, e)
            raise

    async def get_job_overview(
        self,
        job_id: str,
        organization_id: Optional[str] = None,
    ) -> dict:
        try:
            job = await self.job_repository.get_job_by_id(job_id)
            if not job:
                raise JobNotFound(status_code=404)

            rubric = await self.job_repository.get_active_rubric(job_id)
            if not rubric:
                raise RubricNotFound(
                    message="Active rubric not found",
                    status_code=404,
                )

            # Use backward-compatible reader
            criteria_data = read_rubric_criteria(rubric.criteria)

            # Dashboard analytics
            analytics_result = await self.job_repository.get_applications_by_group(job_id)
            analytics = {status.value: count for status, count in analytics_result}
            total_applications = sum(analytics.values())

            response = {
                "job": {
                    "id": job.id,
                    "title": job.title,
                    "status": _job_status_for_api(job.status),
                    "description": job.description,
                    "created_at": job.created_at,
                    "salary": job.salary,
                    "location": job.location,
                    "target_headcount": job.target_headcount,
                    "parsed_jd": job.parsed_jd,  # rrg_final when available
                },
                "dashboard": {
                    "total_applications": total_applications,
                    "by_status": analytics,
                },
                "criteria": {
                    "rubric_id": rubric.id,
                    "version": rubric.version,
                    "threshold_score": rubric.threshold_score,
                    "criteria": criteria_data,
                },
                "settings": {
                    "voice_ai_enabled": job.voice_ai_enabled,
                    "manual_rounds_count": job.manual_rounds_count,
                    "is_confidential": job.is_confidential,
                    "job_metadata": job.job_metadata,
                    "closing_reason": job.closing_reason,
                },
            }
            
            return response

        except (JobNotFound, RubricNotFound):
            raise
        except Exception as e:
            self.logger.exception("Error fetching job overview for %s: %s", job_id, e)
            raise

    # ! For Keshav's Version
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
            
            active_rubric_version = await self.job_repository.get_latest_rubric_version(job_id=job_id)
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
                        current_batch_id=job.id, #! is active_processing id removed from db if yes then handle it accordingly
                    ),
                    dashboard=DashboardInfo(
                        total_applications=total_applications,
                        by_status=analytics,
                        avg_score=float(round(avg_match_score or 0.0, 2)),
                    ),
                    criteria=CriteriaOverview(
                        current_active_version=active_rubric_version,
                        active_rubric_id=active_rubric_version,
                        versions=[
                            RubricVersionInfo(
                                rubric_id=rv["id"],     # map id → rubric_id
                                version=rv["version"],
                                is_active=rv.get("is_active", False),
                                created_at=rv["created_at"],
                                
                            )
                            for rv in rubric_versions
                        ]
                    )
                )

        except Exception as e:
            self.logger.exception(f"Error fetching job overview for job_id {job_id}: {e}")
            raise


    async def get_rubric_export(self, job_id: str) -> dict:
        """
        Return the active rubric for a job as a JSON-serializable dict for download.
        Raises JobNotFound / RubricNotFound if job or active rubric missing.
        """
        job = await self.job_repository.get_job_by_id(job_id)
        if not job:
            raise JobNotFound(status_code=404)
        rubric = await self.job_repository.get_active_rubric(job_id)
        if not rubric:
            raise RubricNotFound(
                message="Active rubric not found",
                status_code=404,
            )
        criteria_data = read_rubric_criteria(rubric.criteria)
        # Ensure all values are JSON-serializable (no UUID, Decimal, datetime objects)
        created_at = rubric.created_at
        updated_at = rubric.updated_at
        return {
            "job_id": str(job.id),
            "job_title": job.title,
            "rubric_id": str(rubric.id),
            "version": int(rubric.version),
            "threshold_score": float(rubric.threshold_score),
            "source": rubric.source,
            "criteria": criteria_data,
            "ai_metadata": rubric.ai_metadata,
            "parent_rubric_id": str(rubric.parent_rubric_id) if rubric.parent_rubric_id else None,
            "created_by_id": str(rubric.created_by_id) if rubric.created_by_id else None,
            "created_via": rubric.created_via,
            "change_reason": rubric.change_reason,
            "change_type": rubric.change_type,
            "created_at": created_at.isoformat() if created_at else None,
            "updated_at": updated_at.isoformat() if updated_at else None,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }

    # ─── 6.5. Get JD Parsing Status (for draft JD upload polling) ─────

    async def get_jd_status(self, job_id: str) -> dict:
        """
        Lightweight status endpoint for JD upload flow.
        Works even when the job has no rubric yet (draft jobs).
        """
        job = await self.job_repository.get_job_by_id(job_id)
        if not job:
            raise JobNotFound(status_code=404)

        doc_repo = DocumentRepository(self.db)
        latest_doc = await doc_repo.get_latest_document_for_entity(
            entity_type="jobs",
            entity_id=UUID(job_id),
            document_type="job_description",
        )

        # Prefer job.parsed_jd once worker writes it
        parsed_jd = job.parsed_jd

        if parsed_jd:
            return {
                "job_id": str(job.id),
                "document_id": str(latest_doc.id) if latest_doc else None,
                "parsing_status": "parsed",
                "parsing_error": None,
                "parsed_jd": parsed_jd,
            }

        return {
            "job_id": str(job.id),
            "document_id": str(latest_doc.id) if latest_doc else None,
            "parsing_status": getattr(latest_doc, "parsing_status", None),
            "parsing_error": getattr(latest_doc, "parsing_error", None),
            "parsed_jd": getattr(latest_doc, "ai_parsed_data", None),
        }

    # ─── 7. Process Applications (unchanged, for resume upload) ──────

    async def process_applications(
        self,
        job_id: str,
        user_id: str,
        files: List[UploadFile],
        background_tasks: BackgroundTasks = None,
        organization_id: Optional[str] = None,
    ) -> dict:
        try:
            job = await self.job_repository.get_job_by_id(job_id)
            if not job:
                raise JobNotFound(status_code=404)

            batch_name = self._generate_batch_name(job_id)

            files_uploaded_dir, saved_paths = await self.file_manager.stage_uploaded_files(
                dir_name=batch_name,
                files=files,
            )

            batch = BulkUploadBatches(
                job_id=job.id,
                uploaded_by_id=user_id,
                batch_name=batch_name,
                source_file_url=files_uploaded_dir,
                total_files=len(files),
            )
            self.db.add(batch)
            await self.db.commit()
            await self.db.refresh(batch)

            background_tasks.add_task(
                enqueue_resumes_parsing,
                resume_paths=saved_paths,
                db_job_id=job.id,
                batch_id=batch.id,
                queue_name="resume_parsing",
            )

            return {
                "directory_path": files_uploaded_dir,
                "status": "queued",
            }

        except Exception as e:
            await self.db.rollback()
            self.logger.exception("Error processing applications for job %s: %s", job_id, e)
            raise

    # ! Keshav's Version of processing application
    async def process_applications_with_zip(
        self,
        job_id: str,
        user_id: str,
        raw_files: List[UploadFile],
        organization_id: Optional[str] = None, #TODO: add it
    ) -> dict:

        try:
            
            if len(raw_files) == 0:
                raise DomainError(
                    message="No files uploaded",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            if len(raw_files) > 3:
                raise DomainError(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="Too many files uploaded. Maximum is 3.",
                )
            
            files = await fileManager.validate_and_extract(raw_files)
            
            
            # 1. Fetch job
            job : Job | None = await self.validate_job(job_id=job_id, organization_id=organization_id)


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
    
    
    

    # ─── 8. Get Applications ─────────────────────────────────────────
    
    
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

    