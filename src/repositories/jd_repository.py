from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from configs.log_config import get_logger
from src.models.job_description_model import JobDescription
from src.models.job_model import Job


class JDRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = get_logger("JD_REPOSITORY")

    # ── Version numbering ──────────────────────────────────────────────────────

    async def next_version_number(self, job_id: UUID) -> int:
        result = await self.db.execute(
            select(func.coalesce(func.max(JobDescription.version_number), 0)).where(
                JobDescription.job_id == job_id
            )
        )
        return result.scalar() + 1

    # ── Write operations ───────────────────────────────────────────────────────

    async def create(
        self,
        job_id: UUID,
        organization_id: UUID,
        title: str,
        content: str,
        created_by_id: UUID,
        generation_method: str = "manual",
        raw_answers: Optional[dict] = None,
    ) -> JobDescription:
        version_number = await self.next_version_number(job_id)
        jd = JobDescription(
            job_id=job_id,
            organization_id=organization_id,
            version_number=version_number,
            title=title,
            content=content,
            generation_method=generation_method,
            raw_answers=raw_answers,
            status="draft",
            created_by_id=created_by_id,
        )
        self.db.add(jd)
        await self.db.flush()
        return jd

    async def update(
        self,
        jd_id: UUID,
        title: Optional[str] = None,
        content: Optional[str] = None,
    ) -> None:
        values: dict = {}
        if title is not None:
            values["title"] = title
        if content is not None:
            values["content"] = content
        if values:
            await self.db.execute(
                update(JobDescription).where(JobDescription.id == jd_id).values(**values)
            )

    async def archive_active(self, job_id: UUID) -> None:
        """Set the current active JD for this job to 'archived'."""
        await self.db.execute(
            update(JobDescription)
            .where(
                JobDescription.job_id == job_id,
                JobDescription.status == "active",
                JobDescription.deleted_at == None,
            )
            .values(status="archived")
        )

    async def set_status(self, jd_id: UUID, status: str) -> None:
        await self.db.execute(
            update(JobDescription).where(JobDescription.id == jd_id).values(status=status)
        )

    async def soft_delete(self, jd_id: UUID) -> None:
        await self.db.execute(
            update(JobDescription)
            .where(JobDescription.id == jd_id)
            .values(deleted_at=datetime.now(timezone.utc))
        )

    # ── Job pointer ────────────────────────────────────────────────────────────

    async def set_active_jd_on_job(self, job_id: UUID, jd_id: Optional[UUID]) -> None:
        await self.db.execute(
            update(Job).where(Job.id == job_id).values(active_jd_id=jd_id)
        )

    # ── Read operations ────────────────────────────────────────────────────────

    async def get_by_id(self, jd_id: UUID) -> Optional[JobDescription]:
        result = await self.db.execute(
            select(JobDescription).where(
                JobDescription.id == jd_id,
                JobDescription.deleted_at == None,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_and_job(self, jd_id: UUID, job_id: UUID) -> Optional[JobDescription]:
        result = await self.db.execute(
            select(JobDescription).where(
                JobDescription.id == jd_id,
                JobDescription.job_id == job_id,
                JobDescription.deleted_at == None,
            )
        )
        return result.scalar_one_or_none()

    async def get_active(self, job_id: UUID) -> Optional[JobDescription]:
        result = await self.db.execute(
            select(JobDescription).where(
                JobDescription.job_id == job_id,
                JobDescription.status == "active",
                JobDescription.deleted_at == None,
            )
        )
        return result.scalar_one_or_none()

    async def list_versions(self, job_id: UUID) -> List[JobDescription]:
        result = await self.db.execute(
            select(JobDescription)
            .where(
                JobDescription.job_id == job_id,
                JobDescription.deleted_at == None,
            )
            .order_by(JobDescription.version_number.desc())
        )
        return list(result.scalars().all())
