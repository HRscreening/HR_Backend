"""
Job Service — handles all business logic for job + rubric lifecycle.

Key design principles:
  - DB writes ONLY happen when user clicks "Set Rubric" (for new job)
    or "Update Rubric" (for existing job).
  - extract_jd() is a pure AI operation — no DB writes.
  - All mutations are wrapped in a single transaction with rollback on failure.
  - Backward compatibility: reads v1 rubrics and converts them on-the-fly.
"""

from fastapi import UploadFile, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from typing import Optional, List

from src.models import Job, Rubric, BulkUploadBatches
from src.models.enums import BulkUploadStatus
from src.schemas.rubric_schemas import (
    SetRubricRequest,
    UpdateRubricRequest,
    read_rubric_criteria,
)
from src.schemas.job_schemas import JobOverviewResponse,JobSettingsResposnse,JobSettings
from src.services.errors.base import DomainError
from src.services.errors.user_errors import JobNotFound, RubricNotFound
from src.services.errors.pipeline_errors import (
    JDTooShort,
    JDNotReadable,
)
from src.repositories.job_repository import JobRepository
from src.repositories.batch_repositoy import BatchRepository
from src.repositories.org_repository import OrganizationRepository
from src.utils.extract_pdf import extract_text_from_pdf
from src.utils.file_manager import FileManagerService, fileManager
from src.utils.manage_supabase_buckets import save_file_from_path
from src.pipelines.generate_rubric import generate_rubric_from_jd
from src.pipelines.jd_basic_analysis import analyze_jd_basic
from workers.producer import enqueue_resumes_parsing
from configs.env_config import SUPABASE_PUBLIC_URL
from configs.log_config import get_logger
from src.repositories.document_repository import DocumentRepository
from src.repositories.interview_respositories.interview_round_configs_repository  import InterviewRoundConfigsRepository 
from src.utils.candidate_name import extract_candidate_full_name
from uuid import UUID
from sqlalchemy import select, func
from src.models import Application, Score
import os
import time
import json


def _job_status_for_api(status) -> str:
    """Normalize job status for API: DB enum may be 'OPEN'; API contract is lowercase."""
    v = status.value
    return v if v == "draft" else v.lower()


class JobService:
    def __init__(
        self,
        job_repositoy: JobRepository,
        batch_repository: BatchRepository,
        org_repository: OrganizationRepository,
        round_config_repository: InterviewRoundConfigsRepository,
        db: AsyncSession,
    ):
        self.db = db
        self.PUBLIC_URL = SUPABASE_PUBLIC_URL
        self.job_repository = job_repositoy
        self.batch_repository = batch_repository
        self.organization_repository = org_repository
        self.file_manager: FileManagerService = fileManager
        self.round_config_repository = round_config_repository
        self.logger = get_logger("JOB_SERVICE")

    # ─── Helpers ─────────────────────────────────────────────────────

    def _generate_batch_name(self, job_id: str) -> str:
        return f"application_processing_{job_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

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

            # Rubrics are optional at this stage: we still want the job page to load
            # so users can (re)create a rubric after a reset/cleanup.
            rubrics = await self.job_repository.get_all_rubrics(job_id)
            active_rubric = next((r for r in rubrics if r.is_active), None)
            if not active_rubric and rubrics:
                # Fallback: if none marked active, use latest by version
                active_rubric = rubrics[0]

            # Use backward-compatible reader when present
            criteria_data = read_rubric_criteria(active_rubric.criteria) if active_rubric else {}

            # Dashboard analytics
            analytics_result = await self.job_repository.get_applications_by_group(job_id)
            analytics = {status.value: count for status, count in analytics_result}
            total_applications = sum(analytics.values())

            # Avg match score (optional; 0 when no scores)
            avg_score = await self.db.scalar(
                select(func.avg(Score.overall_score)).join(
                    Application, Application.id == Score.application_id
                ).where(Application.job_id == job_id)
            )

            latest_batch = await self.batch_repository.get_latest_batch_for_job(job_id)

            # Criteria versions overview (works even when there is no rubric)
            criteria_overview = {
                "current_active_version": active_rubric.version if active_rubric else None,
                "active_rubric_id": active_rubric.id if active_rubric else None,
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
            
            available_round_config = await self.round_config_repository.get_available_round_config_by_job(job_id)
            
            
            
            round_slots = []
            
            if available_round_config:
                for round in available_round_config:
                    round_slots.append({
                        "round_config_id": round.id,
                        "round_number": round.round_number,
                        "slots_available": round.slots_available,
                    })
            
            
            
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
                    "current_batch_id": latest_batch.id if latest_batch else None,
                    "manual_rounds_count": job.manual_rounds_count or 0,
                    "parsed_jd": job.parsed_jd,  # rrg_final when available (extra field; safe)
                },
                "round_slots": round_slots if round_slots else None,
                "dashboard": {
                    "total_applications": total_applications,
                    "by_status": analytics,
                    "avg_score": float(avg_score) if avg_score is not None else 0.0,
                },
                "criteria": criteria_overview,
                "settings": {
                    "voice_ai_enabled": job.voice_ai_enabled,
                    "manual_rounds_count": job.manual_rounds_count,
                    "is_confidential": job.is_confidential,
                    "job_metadata": job.job_metadata,
                    "closing_reason": job.closing_reason,
                },
            }
            
            return response

        except JobNotFound:
            raise
        except Exception as e:
            self.logger.exception("Error fetching job overview for %s: %s", job_id, e)
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

            # Pre-check: ensure an active rubric exists before accepting files
            active_rubric = await self.job_repository.get_active_rubric(str(job.id))
            if not active_rubric:
                raise DomainError(
                    f"No active rubric found for this job. Please set up a rubric before uploading resumes."
                )

            batch_name = self._generate_batch_name(job_id)

            files_uploaded_dir, saved_paths = await self.file_manager.stage_uploaded_files(
                dir_name=batch_name,
                files=files,
            )

            self.logger.info(
                "[PROCESS_APPS] staged %d files for job_id=%s",
                len(saved_paths),
                job_id,
            )

            # Upload every file to Supabase NOW, before returning or enqueuing.
            # Workers download from Supabase — no dependency on local disk state after this point.
            storage_paths: list[str] = []
            for local_path in saved_paths:
                filename = os.path.basename(local_path)
                storage_path = save_file_from_path(
                    local_file_path=local_path,
                    bucket_name="resumes",
                    destination_path=f"{job_id}/{filename}",
                )
                storage_paths.append(storage_path)
                self.logger.info("[PROCESS_APPS] uploaded %s → %s", filename, storage_path)
                try:
                    os.unlink(local_path)
                except OSError:
                    pass

            batch = BulkUploadBatches(
                job_id=job.id,
                uploaded_by_id=user_id,
                batch_name=batch_name,
                source_file_url=f"resumes/{job_id}",
                total_files=len(storage_paths),
            )
            self.db.add(batch)
            await self.db.commit()
            await self.db.refresh(batch)

            self.logger.info(
                "[PROCESS_APPS] enqueueing batch_id=%s job_id=%s total=%d",
                batch.id,
                job.id,
                len(storage_paths),
            )
            background_tasks.add_task(
                enqueue_resumes_parsing,
                storage_paths=storage_paths,
                db_job_id=job.id,
                batch_id=batch.id,
                queue_name="resume_parsing",
            )

            return {
                "batch_id": str(batch.id),
                "total_files": len(storage_paths),
                "status": "queued",
            }

        except Exception as e:
            await self.db.rollback()
            self.logger.exception("Error processing applications for job %s: %s", job_id, e)
            raise

    # ─── 8. Get Applications ─────────────────────────────────────────

    async def get_applications(
        self,
        job_id: str,
        page: int = 1,
        page_size: int = 20,
        sort: str = "score_desc",
    ):
        if page < 1:
            page = 1

        offset = (page - 1) * page_size

        total = await self.job_repository.get_total_applications_count(job_id)
        active_rubric = await self.job_repository.get_active_rubric(job_id)

        if not active_rubric:
            raise RubricNotFound(
                message="Active rubric not found for the job",
                status_code=404,
            )

        applications = await self.job_repository.get_applications_of_job(
            job_id=job_id,
            current_rubric_id=active_rubric.id,
            page_size=page_size,
            offset=offset,
            sort=sort,
        )

        response = []
        for app, score in applications:
            active_score = score if score else None
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
                "last_activity_at": app.last_activity_at.isoformat() if app.last_activity_at else None,
                "deleted_at": app.deleted_at.isoformat() if app.deleted_at else None,
                "status": app.status.value,
                "created_at": app.created_at.isoformat(),
                "updated_at": app.updated_at.isoformat(),
                "ai_analysis": app.ai_analysis,
            }

            # Prefer linked candidate; fallback to extracted candidate_info from latest score (e.g. before candidate_extraction worker runs)
            if app.candidate:
                app_data["candidate"] = {
                    "id": str(app.candidate.id),
                    "full_name": app.candidate.full_name,
                    "email": app.candidate.email,
                    "phone": app.candidate.phone,
                }
            else:
                candidate_info = None
                if active_score and isinstance(active_score.grounding_data, dict):
                    candidate_info = active_score.grounding_data.get("candidate_info")
                if not (candidate_info and isinstance(candidate_info, dict)):
                    candidate_info = {}

                # Final fallback: infer name from resume text if scoring/candidate extraction didn't populate it.
                # This keeps the UI usable even when LLM candidate_info is null due to strictness.
                if resume and isinstance(candidate_info, dict) and not candidate_info.get("full_name"):
                    inferred = extract_candidate_full_name(resume.parsed_text or "")
                    if inferred:
                        candidate_info["full_name"] = inferred

                if candidate_info and isinstance(candidate_info, dict) and any(candidate_info.get(k) for k in ("full_name", "email", "phone")):
                    app_data["candidate"] = {
                        "id": None,
                        "full_name": candidate_info.get("full_name"),
                        "email": candidate_info.get("email"),
                        "phone": candidate_info.get("phone"),
                    }
                else:
                    app_data["candidate"] = None

            app_data["resume"] = (
                {
                    "id": str(resume.id),
                    "raw_file_url": f"{self.PUBLIC_URL}/{resume.raw_file_url}",
                    "status": resume.status.value,
                    "page_count": resume.page_count,
                    "uploaded_at": resume.uploaded_at.isoformat(),
                }
                if resume
                else None
            )

            app_data["scores"] = (
                [
                    {
                        "is_active": active_score.is_active,
                        "overall_score": float(active_score.overall_score) if active_score.overall_score is not None else 0,
                        "raw_overall_score": float(active_score.raw_overall_score) if active_score.raw_overall_score is not None else None,
                        "ai_confidence": active_score.ai_confidence,
                        "created_at": active_score.created_at.isoformat(),
                        "grounding_data": active_score.grounding_data,
                        "breakdown": active_score.breakdown,
                        "distinguishing_factors": (
                            active_score.grounding_data.get("distinguishing_factors")
                            if active_score.grounding_data and isinstance(active_score.grounding_data, dict)
                            else None
                        ),
                        "scoring_method": active_score.scoring_method,
                        "is_overridden": active_score.is_overridden,
                        "version": active_score.version,
                        "is_latest": active_score.is_latest,
                    }
                ]
                if active_score
                else []
            )

            response.append(app_data)

        return {
            "applications": response,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            },
        }

    # ─── 9. Batch Progress ──────────────────────────────────────────

    async def get_batch_progress(self, job_id: str, batch_id: str = None) -> dict:
        """Return parsing + scoring progress for a batch upload."""
        if batch_id:
            batch = await self.batch_repository.get_batch_info(batch_id)
        else:
            batch = await self.batch_repository.get_latest_batch_for_job(job_id)

        if not batch:
            return {"status": "no_batch", "job_id": job_id}

        # Parsing is done when the batch has been finalized (set atomically in finalize_batch_parsed).
        # Falling back to counter check handles batches created before this field was reliable.
        parsing_done = (
            batch.status == BulkUploadStatus.COMPLETED
            or (batch.success_count + batch.failed_count) >= batch.total_files
        )

        # Scoring is done when:
        #   - parsing isn't done yet (can't score before parsing)
        #   - OR nothing to score (all parsing failed → scoring_total = 0)
        #   - OR scoring status is explicitly COMPLETED
        #   - OR counters confirm all scored/failed
        if not parsing_done:
            scoring_done = False
        elif batch.scoring_total == 0:
            scoring_done = True  # nothing to score = done
        else:
            scoring_done = (
                batch.scoring_status == BulkUploadStatus.COMPLETED
                or (batch.scoring_completed + batch.scoring_failed) >= batch.scoring_total
            )

        all_done = parsing_done and scoring_done

        if all_done:
            phase = "completed"
        elif parsing_done:
            phase = "scoring"
        else:
            phase = "parsing"

        # Build per-file status list from processing_results + error_log
        file_statuses = []
        if isinstance(batch.processing_results, dict):
            for fname, msg in batch.processing_results.items():
                file_statuses.append({
                    "name": fname,
                    "status": "failed" if msg.startswith("failed") else "parsed",
                    "detail": msg,
                })
        if isinstance(batch.error_log, dict):
            # Add any files in error_log that aren't already in processing_results
            existing_names = {f["name"] for f in file_statuses}
            for fname, reason in batch.error_log.items():
                if fname not in existing_names:
                    file_statuses.append({
                        "name": fname,
                        "status": "failed",
                        "detail": reason,
                    })

        # Mark remaining files as "processing" (not yet in results)
        completed_names = {f["name"] for f in file_statuses}
        pending_count = max(0, batch.total_files - len(completed_names))

        return {
            "batch_id": str(batch.id),
            "job_id": job_id,
            "phase": phase,
            "parsing": {
                "total": batch.total_files,
                "success": batch.success_count,
                "failed": batch.failed_count,
                "pending": pending_count,
                "status": batch.status.value if batch.status else "pending",
            },
            "scoring": {
                "total": batch.scoring_total,
                "completed": batch.scoring_completed,
                "failed": batch.scoring_failed,
                "status": batch.scoring_status.value if batch.scoring_status else "pending",
            },
            "file_statuses": file_statuses,
            "all_complete": all_done,
            "created_at": batch.created_at.isoformat(),
        }
        
        
    async def get_job_settings(self, job_id: str) -> dict:
        job = await self.job_repository.get_job_by_id(job_id)
        if not job:
            raise JobNotFound(status_code=404)


        return JobSettingsResposnse(
                job_settings=JobSettings(
                title=job.title,
                location=job.location,
                salary=job.salary,
                status=_job_status_for_api(job.status),
                description=job.description,
                target_headcount=job.target_headcount,
                manual_rounds_count=job.manual_rounds_count,
                
                ),
            voice_ai_enabled=job.voice_ai_enabled,
            is_confidential=job.is_confidential,
            job_metadata=job.job_metadata,
            closing_reason=job.closing_reason,
        )
