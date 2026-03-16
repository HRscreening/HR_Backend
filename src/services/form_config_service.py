"""
Form Config Service — manages the customisable candidate application form per job.

Key rules:
  - A job always has at most one active form config.
  - Activating a config archives the current active one.
  - The three core questions (full_name, email, resume) are always enforced.
  - A form config can only be updated while it is in 'draft' status.
"""

from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from configs.log_config import get_logger
from src.models.application_form_config_model import ApplicationFormConfig, DEFAULT_QUESTIONS
from src.repositories.form_config_repository import FormConfigRepository
from src.repositories.job_repository import JobRepository
from src.schemas.public_apply_schemas import (
    ApplicationFormConfigResponse,
    FormQuestionSchema,
)
from src.services.errors.base import DomainError
from src.services.errors.user_errors import JobNotFound


# ── Error classes ──────────────────────────────────────────────────────────────

class FormConfigNotFound(DomainError):
    code = "FORM_CONFIG_NOT_FOUND"
    message = "Application form configuration not found"
    status_code = 404


class FormConfigNotEditable(DomainError):
    code = "FORM_CONFIG_NOT_EDITABLE"
    message = "Only draft form configs can be edited. Activate it first or create a new version."
    status_code = 400


# ── Service ────────────────────────────────────────────────────────────────────

class FormConfigService:
    def __init__(
        self,
        form_config_repository: FormConfigRepository,
        job_repository: JobRepository,
        db: AsyncSession,
    ):
        self.form_config_repo = form_config_repository
        self.job_repo = job_repository
        self.db = db
        self.logger = get_logger("FORM_CONFIG_SERVICE")

    async def get_or_create_form_config(self, job_id: UUID, user_id: UUID) -> ApplicationFormConfigResponse:
        """
        Return the active form config if one exists.
        If not, return the latest draft. If none at all, create one with defaults.
        """
        job = await self.job_repo.get_job_by_id(str(job_id))
        if not job:
            raise JobNotFound()

        active = await self.form_config_repo.get_active(job_id)
        if active:
            return ApplicationFormConfigResponse.model_validate(active)

        latest = await self.form_config_repo.get_latest(job_id)
        if latest:
            return ApplicationFormConfigResponse.model_validate(latest)

        # No config exists yet — create a draft with the default question set
        config = await self.form_config_repo.create(
            job_id=job_id,
            organization_id=job.organization_id,
            created_by_id=user_id,
        )
        await self.db.commit()
        await self.db.refresh(config)
        return ApplicationFormConfigResponse.model_validate(config)

    async def list_form_config_versions(self, job_id: UUID) -> List[ApplicationFormConfigResponse]:
        job = await self.job_repo.get_job_by_id(str(job_id))
        if not job:
            raise JobNotFound()
        versions = await self.form_config_repo.list_versions(job_id)
        return [ApplicationFormConfigResponse.model_validate(v) for v in versions]

    async def update_form_config(
        self,
        config_id: UUID,
        job_id: UUID,
        questions: List[FormQuestionSchema],
    ) -> ApplicationFormConfigResponse:
        config = await self.form_config_repo.get_by_id_and_job(config_id, job_id)
        if not config:
            raise FormConfigNotFound()
        if config.status != "draft":
            raise FormConfigNotEditable()

        questions_data = [q.model_dump() for q in questions]
        await self.form_config_repo.update_questions(config_id, questions_data)
        await self.db.commit()

        updated = await self.form_config_repo.get_by_id(config_id)
        return ApplicationFormConfigResponse.model_validate(updated)

    async def activate_form_config(
        self, config_id: UUID, job_id: UUID
    ) -> ApplicationFormConfigResponse:
        config = await self.form_config_repo.get_by_id_and_job(config_id, job_id)
        if not config:
            raise FormConfigNotFound()

        # Archive the current active config (if any)
        await self.form_config_repo.archive_active(job_id)
        # Activate the target config
        await self.form_config_repo.set_status(config_id, "active")
        # Update the pointer on the job
        await self.form_config_repo.set_active_form_config_on_job(job_id, config_id)
        await self.db.commit()

        updated = await self.form_config_repo.get_by_id(config_id)
        return ApplicationFormConfigResponse.model_validate(updated)

    async def create_new_version(
        self,
        job_id: UUID,
        user_id: UUID,
        questions: Optional[List[FormQuestionSchema]] = None,
    ) -> ApplicationFormConfigResponse:
        """
        Create a new draft version of the form config.
        If questions are provided, use them; otherwise copy from the current active config
        or fall back to DEFAULT_QUESTIONS.
        """
        job = await self.job_repo.get_job_by_id(str(job_id))
        if not job:
            raise JobNotFound()

        if questions is not None:
            questions_data = [q.model_dump() for q in questions]
        else:
            # Copy from current active or use defaults
            active = await self.form_config_repo.get_active(job_id)
            questions_data = active.questions if active else list(DEFAULT_QUESTIONS)

        config = await self.form_config_repo.create(
            job_id=job_id,
            organization_id=job.organization_id,
            created_by_id=user_id,
            questions=questions_data,
        )
        await self.db.commit()
        await self.db.refresh(config)
        return ApplicationFormConfigResponse.model_validate(config)
