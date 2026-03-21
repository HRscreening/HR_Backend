from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from configs.log_config import get_logger
from src.models.application_form_config_model import ApplicationFormConfig, DEFAULT_QUESTIONS
from src.models.job_model import Job


class FormConfigRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = get_logger("FORM_CONFIG_REPOSITORY")

    # ── Version numbering ──────────────────────────────────────────────────────

    async def next_version_number(self, job_id: UUID) -> int:
        result = await self.db.execute(
            select(func.coalesce(func.max(ApplicationFormConfig.version_number), 0)).where(
                ApplicationFormConfig.job_id == job_id
            )
        )
        return result.scalar() + 1

    # ── Write operations ───────────────────────────────────────────────────────

    async def create(
        self,
        job_id: UUID,
        organization_id: UUID,
        created_by_id: UUID,
        questions: Optional[list] = None,
    ) -> ApplicationFormConfig:
        version_number = await self.next_version_number(job_id)
        config = ApplicationFormConfig(
            job_id=job_id,
            organization_id=organization_id,
            version_number=version_number,
            questions=questions if questions is not None else list(DEFAULT_QUESTIONS),
            status="draft",
            created_by_id=created_by_id,
        )
        self.db.add(config)
        await self.db.flush()
        return config

    async def update_questions(self, config_id: UUID, questions: list) -> None:
        await self.db.execute(
            update(ApplicationFormConfig)
            .where(ApplicationFormConfig.id == config_id)
            .values(questions=questions)
        )

    async def archive_active(self, job_id: UUID) -> None:
        """Set the current active form config for this job to 'archived'."""
        await self.db.execute(
            update(ApplicationFormConfig)
            .where(
                ApplicationFormConfig.job_id == job_id,
                ApplicationFormConfig.status == "active",
            )
            .values(status="archived")
        )

    async def set_status(self, config_id: UUID, status: str) -> None:
        await self.db.execute(
            update(ApplicationFormConfig)
            .where(ApplicationFormConfig.id == config_id)
            .values(status=status)
        )

    # ── Job pointer ────────────────────────────────────────────────────────────

    async def set_active_form_config_on_job(
        self, job_id: UUID, config_id: Optional[UUID]
    ) -> None:
        await self.db.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(active_form_config_id=config_id)
        )

    # ── Public link columns ────────────────────────────────────────────────────

    async def set_public_link(
        self, job_id: UUID, slug: str, enabled: bool
    ) -> None:
        await self.db.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(public_slug=slug, public_apply_enabled=enabled)
        )

    async def set_public_apply_enabled(self, job_id: UUID, enabled: bool) -> None:
        await self.db.execute(
            update(Job).where(Job.id == job_id).values(public_apply_enabled=enabled)
        )

    # ── Read operations ────────────────────────────────────────────────────────

    async def get_by_id(self, config_id: UUID) -> Optional[ApplicationFormConfig]:
        result = await self.db.execute(
            select(ApplicationFormConfig).where(ApplicationFormConfig.id == config_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_and_job(
        self, config_id: UUID, job_id: UUID
    ) -> Optional[ApplicationFormConfig]:
        result = await self.db.execute(
            select(ApplicationFormConfig).where(
                ApplicationFormConfig.id == config_id,
                ApplicationFormConfig.job_id == job_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_active(self, job_id: UUID) -> Optional[ApplicationFormConfig]:
        result = await self.db.execute(
            select(ApplicationFormConfig).where(
                ApplicationFormConfig.job_id == job_id,
                ApplicationFormConfig.status == "active",
            )
        )
        return result.scalar_one_or_none()

    async def get_latest(self, job_id: UUID) -> Optional[ApplicationFormConfig]:
        """Return the most recently created config regardless of status."""
        result = await self.db.execute(
            select(ApplicationFormConfig)
            .where(ApplicationFormConfig.job_id == job_id)
            .order_by(ApplicationFormConfig.version_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_versions(self, job_id: UUID) -> List[ApplicationFormConfig]:
        result = await self.db.execute(
            select(ApplicationFormConfig)
            .where(ApplicationFormConfig.job_id == job_id)
            .order_by(ApplicationFormConfig.version_number.desc())
        )
        return list(result.scalars().all())
