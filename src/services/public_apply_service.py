"""
Public Apply Service — handles anonymous candidate applications via a public job link.

Flow for a single submission:
  1. Resolve slug → job (guards: public_apply_enabled, status=OPEN)
  2. Validate resume file (type, size)
  3. Reject duplicate application (same email + job_id)
  4. Find-or-create Candidate by email within the organisation
  5. Create Application with source='public_apply'
  6. Stage file locally → upload to Supabase
  7. Create Resume record
  8. Create a single-file BulkUploadBatch (reuses existing worker infrastructure)
  9. Update Application.current_resume_id
 10. Enqueue resume_parser worker
"""

import os
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from fastapi import UploadFile, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from configs.env_config import BASE_UPLOAD_DIR
from configs.log_config import get_logger
from src.models import Application, BulkUploadBatches, Candidate, Resume
from src.models.application_model import Application
from src.models.bulk_upload_batches_model import BulkUploadBatches
from src.models.enums import BulkUploadStatus, ResumeStatus
from src.models.job_model import Job
from src.repositories.candidiate_repository import CandidateRepository
from src.repositories.form_config_repository import FormConfigRepository
from src.repositories.jd_repository import JDRepository
from src.repositories.job_repository import JobRepository
from src.schemas.candidate_schemas import CandidateCreateSchema
from src.schemas.public_apply_schemas import PublicApplyRequest, PublicApplyResponse, PublicJobInfoResponse, FormQuestionSchema
from src.services.errors.base import DomainError
from src.utils.file_manager import FileManagerService
from src.utils.manage_supabase_buckets import save_file_from_path
from workers.producer import enqueue_resumes_parsing


# ── Error classes ──────────────────────────────────────────────────────────────

class PublicApplyJobNotFound(DomainError):
    code = "PUBLIC_APPLY_JOB_NOT_FOUND"
    message = "This job is no longer accepting applications."
    status_code = 404


class PublicApplyJobClosed(DomainError):
    code = "PUBLIC_APPLY_JOB_CLOSED"
    message = "This position is no longer accepting applications."
    status_code = 410


class DuplicateApplication(DomainError):
    code = "DUPLICATE_APPLICATION"
    message = "You have already applied for this position."
    status_code = 409


class InvalidResumeFile(DomainError):
    code = "INVALID_RESUME_FILE"
    message = "Invalid resume file. Please upload a PDF or DOCX file (max 5 MB)."
    status_code = 400


# ── Service ────────────────────────────────────────────────────────────────────

class PublicApplyService:
    _ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}
    _MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

    def __init__(
        self,
        job_repository: JobRepository,
        jd_repository: JDRepository,
        form_config_repository: FormConfigRepository,
        candidate_repository: CandidateRepository,
        file_manager: FileManagerService,
        db: AsyncSession,
    ):
        self.job_repo = job_repository
        self.jd_repo = jd_repository
        self.form_config_repo = form_config_repository
        self.candidate_repo = candidate_repository
        self.file_manager = file_manager
        self.db = db
        self.logger = get_logger("PUBLIC_APPLY_SERVICE")

    # ── Public endpoints ───────────────────────────────────────────────────────

    async def get_job_for_apply_page(self, slug: str) -> PublicJobInfoResponse:
        """Return the minimal job info needed to render the public application form."""
        job = await self._resolve_slug(slug)

        # Get form questions from the active form config
        form_config = await self.form_config_repo.get_active(job.id)
        questions = (
            [FormQuestionSchema(**q) for q in form_config.questions]
            if form_config and form_config.questions
            else []
        )

        # Resolve org name (lazy — may be None for personal jobs)
        org_name = None
        if job.organization:
            org_name = getattr(job.organization, "name", None)

        return PublicJobInfoResponse(
            job_id=job.id,
            title=job.title,
            location=job.location,
            description=job.description,
            organization_name=org_name,
            form_questions=questions,
        )

    async def submit_application(
        self,
        slug: str,
        form_data: PublicApplyRequest,
        resume_file: UploadFile,
    ) -> PublicApplyResponse:
        """Process a public job application end-to-end."""
        job = await self._resolve_slug(slug)

        # 1. Validate resume file
        await self._validate_resume_file(resume_file)

        # 2. Duplicate check
        await self._check_duplicate(email=str(form_data.email), job_id=job.id)

        # 3. Find-or-create candidate
        candidate = await self._find_or_create_candidate(form_data, job.organization_id)

        # 4. Create application
        application = Application(
            job_id=job.id,
            candidate_id=candidate.id,
            source="public_apply",
        )
        self.db.add(application)
        await self.db.flush()

        # 5. Stage file locally
        safe_name = self.file_manager.sanitize_filename(resume_file.filename or "resume.pdf")
        local_dir = os.path.join(BASE_UPLOAD_DIR, str(job.id), "public_apply")
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, f"{application.id}_{safe_name}")

        file_bytes = await resume_file.read()
        with open(local_path, "wb") as f:
            f.write(file_bytes)

        # 6. Upload to Supabase
        supabase_path = f"{job.id}/public_apply/{application.id}_{safe_name}"
        try:
            storage_path = save_file_from_path(
                local_file_path=local_path,
                bucket_name="resumes",
                destination_path=supabase_path,
            )
        finally:
            # Always clean up local staging file
            try:
                os.remove(local_path)
            except OSError:
                pass

        # 7. Create Resume record
        resume = Resume(
            application_id=application.id,
            candidate_id=candidate.id,
            raw_file_url=storage_path,
            status=ResumeStatus.UPLOADED,
        )
        self.db.add(resume)
        await self.db.flush()

        # 8. Update application with resume pointer
        await self.db.execute(
            update(Application)
            .where(Application.id == application.id)
            .values(current_resume_id=resume.id)
        )

        # 9. Create a single-file batch for worker tracking
        batch = BulkUploadBatches(
            job_id=job.id,
            uploaded_by_id=job.created_by_id,  # use job owner since public submission has no auth user
            batch_name=f"public_apply_{application.id}",
            source_file_url=storage_path,
            status=BulkUploadStatus.PENDING,
            total_files=1,
            batch_metadata={"source": "public_apply", "application_id": str(application.id)},
        )
        self.db.add(batch)
        await self.db.flush()

        await self.db.commit()

        # 10. Enqueue parser (runs outside the transaction)
        enqueue_resumes_parsing(
            storage_paths=[storage_path],
            db_job_id=str(job.id),
            batch_id=str(batch.id),
        )

        self.logger.info(
            f"[PUBLIC_APPLY] submitted: job={job.id} application={application.id} "
            f"candidate={candidate.id} batch={batch.id}"
        )

        return PublicApplyResponse(
            status="success",
            message="Application submitted successfully. We will review your profile shortly.",
            application_id=application.id,
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    async def _resolve_slug(self, slug: str) -> Job:
        """Find an active, public-enabled job by its public slug."""
        result = await self.db.execute(
            select(Job).where(
                Job.public_slug == slug,
                Job.public_apply_enabled == True,
                Job.deleted_at == None,
            )
        )
        job = result.scalar_one_or_none()
        if not job:
            raise PublicApplyJobNotFound()

        # Check job is still open
        from src.models.enums import JobStatus
        if job.status not in (JobStatus.OPEN, "OPEN", "open"):
            raise PublicApplyJobClosed()

        return job

    async def _validate_resume_file(self, file: UploadFile) -> None:
        if not file.filename:
            raise InvalidResumeFile("Please attach a resume file.")

        _, ext = os.path.splitext(file.filename)
        if ext.lower() not in self._ALLOWED_EXTENSIONS:
            raise InvalidResumeFile(
                f"File type '{ext}' is not supported. Please upload a PDF or DOCX file."
            )

        # Peek at the size without consuming the stream permanently
        contents = await file.read()
        await file.seek(0)
        if len(contents) > self._MAX_FILE_SIZE_BYTES:
            raise InvalidResumeFile(
                f"File is too large ({len(contents) // (1024*1024)} MB). Maximum size is 5 MB."
            )

    async def _check_duplicate(self, email: str, job_id: UUID) -> None:
        """Raise if the same email already has an application for this job."""
        result = await self.db.execute(
            select(Application.id)
            .join(Candidate, Candidate.id == Application.candidate_id)
            .where(
                Application.job_id == job_id,
                Candidate.email == email,
                Application.deleted_at == None,
            )
            .limit(1)
        )
        if result.scalar_one_or_none() is not None:
            raise DuplicateApplication()

    async def _find_or_create_candidate(
        self, form_data: PublicApplyRequest, org_id: Optional[UUID]
    ) -> Candidate:
        """Return existing candidate or create a new one."""
        existing = await self.candidate_repo.get_candidate_by_email(
            str(form_data.email), org_id=str(org_id) if org_id else None
        )
        if existing:
            return existing

        schema = CandidateCreateSchema(
            full_name=form_data.full_name,
            email=form_data.email,
            phone=form_data.phone,
        )
        return await self.candidate_repo.create_candidate(
            schema, org_id=str(org_id) if org_id else None
        )
