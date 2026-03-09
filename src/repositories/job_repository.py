from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete
from sqlalchemy.orm import selectinload

from typing import Optional, List

from src.models import Job, Rubric, Application, Score, Resume, BulkUploadBatches, Document
from configs.log_config import get_logger


class JobRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = get_logger("JOB_REPOSITORY")

    # ─── Job CRUD ────────────────────────────────────────────────────

    async def create_job(self, job_data, user_id: str) -> Job:
        """Create a new Job record. Does NOT commit (caller manages transaction)."""
        job = Job(
            title=job_data.title,
            description=job_data.description,
            location=job_data.location,
            salary=getattr(job_data, "salary", None),
            target_headcount=job_data.target_headcount,
            voice_ai_enabled=getattr(job_data, "voice_ai_enabled", False),
            manual_rounds_count=getattr(job_data, "manual_rounds_count", 0),
            is_confidential=getattr(job_data, "is_confidential", False),
            created_by_id=user_id,
        )
        self.db.add(job)
        await self.db.flush()
        return job

    async def get_job_by_id(self, job_id: str) -> Optional[Job]:
        result = await self.db.execute(
            select(Job).where(Job.id == job_id)
        )
        return result.scalar_one_or_none()

    async def update_job_jd_text(self, job_id: str, raw_jd_text: str, parsed_jd: dict = None):
        """Persist the raw JD text and parsed JD on an existing job."""
        values = {"raw_jd_text": raw_jd_text}
        if parsed_jd is not None:
            values["parsed_jd"] = parsed_jd
        await self.db.execute(
            update(Job).where(Job.id == job_id).values(**values)
        )

    async def get_jobs_by_organization(self, org_id: str) -> List[Job]:
        result = await self.db.execute(
            select(Job)
            .where(Job.organization_id == org_id)
            .order_by(Job.created_at.desc())
        )
        return result.scalars().all()

    async def get_jobs_by_user_personal(self, user_id: str) -> List[Job]:
        """Get jobs created by the user that are not associated with any organization."""
        result = await self.db.execute(
            select(Job)
            .where(Job.created_by_id == user_id, Job.organization_id == None)
            .order_by(Job.created_at.desc())
        )
        return result.scalars().all()

    async def delete_job(self, job_id: str) -> bool:
        """
        Delete a job and all its related data in dependency order.
        Explicit deletes ensure the transaction commits correctly.
        """
        job = await self.get_job_by_id(job_id)
        if not job:
            return False

        # Subquery: application ids for this job
        app_subq = select(Application.id).where(Application.job_id == job_id)

        # 1. Scores (reference applications and rubrics)
        await self.db.execute(delete(Score).where(Score.application_id.in_(app_subq)))
        # 2. Resumes (reference applications)
        await self.db.execute(delete(Resume).where(Resume.application_id.in_(app_subq)))
        # 3. Applications
        await self.db.execute(delete(Application).where(Application.job_id == job_id))
        # 4. Rubrics
        await self.db.execute(delete(Rubric).where(Rubric.job_id == job_id))
        # 5. Bulk upload batches
        await self.db.execute(delete(BulkUploadBatches).where(BulkUploadBatches.job_id == job_id))
        # 6. Documents linked to this job (e.g. job_description)
        job_uuid = UUID(job_id) if isinstance(job_id, str) else job_id
        await self.db.execute(
            delete(Document).where(
                Document.entity_type == "jobs",
                Document.entity_id == job_uuid,
            )
        )
        # 7. Job
        await self.db.execute(delete(Job).where(Job.id == job_id))

        await self.db.flush()
        return True

    # ─── Rubric CRUD ─────────────────────────────────────────────────

    async def create_rubric(
        self,
        job_id: str,
        criteria: dict,
        threshold_score: float,
        version: int = 1,
        ai_metadata: dict = None,
        source: str = "ai",
        parent_rubric_id: Optional[str] = None,
        created_by_id: Optional[str] = None,
        created_via: Optional[str] = None,
        change_reason: Optional[str] = None,
        change_type: Optional[str] = None,
    ) -> Rubric:
        """Create a new Rubric record. Does NOT commit."""
        from src.models.enums import RubricSource
        source_enum = RubricSource(source) if source in [e.value for e in RubricSource] else RubricSource.AI

        rubric = Rubric(
            job_id=job_id,
            version=version,
            threshold_score=threshold_score,
            criteria=criteria,
            is_active=True,
            # DB column is VARCHAR; persist the enum value (e.g. "combined")
            source=source_enum.value,
            ai_metadata=ai_metadata,
            parent_rubric_id=parent_rubric_id,
            created_by_id=created_by_id,
            created_via=created_via,
            change_reason=change_reason,
            change_type=change_type,
        )
        self.db.add(rubric)
        await self.db.flush()
        return rubric

    async def deactivate_all_rubrics(self, job_id: str):
        """Deactivate all existing rubrics for a job (before creating a new active one)."""
        await self.db.execute(
            update(Rubric)
            .where(Rubric.job_id == job_id, Rubric.is_active == True)
            .values(is_active=False)
        )

    async def get_active_rubric(self, job_id: str) -> Optional[Rubric]:
        result = await self.db.execute(
            select(Rubric).where(Rubric.job_id == job_id, Rubric.is_active == True)
        )
        return result.scalar_one_or_none()

    async def get_all_rubrics(self, job_id: str) -> List[Rubric]:
        result = await self.db.execute(
            select(Rubric).where(Rubric.job_id == job_id).order_by(Rubric.version.desc())
        )
        return result.scalars().all()

    async def get_rubric_by_id(self, rubric_id: str) -> Optional[Rubric]:
        result = await self.db.execute(select(Rubric).where(Rubric.id == rubric_id))
        return result.scalar_one_or_none()

    async def activate_rubric(self, job_id: str, rubric_id: str) -> Optional[Rubric]:
        """Set a specific rubric as active for the job (single-writer invariant)."""
        rubric = await self.get_rubric_by_id(rubric_id)
        if not rubric or str(rubric.job_id) != str(job_id):
            return None

        # Deactivate all existing rubrics, then activate the selected one.
        await self.deactivate_all_rubrics(job_id)
        await self.db.execute(
            update(Rubric)
            .where(Rubric.id == rubric_id)
            .values(is_active=True)
        )
        await self.db.flush()
        return rubric

    async def get_latest_rubric_version(self, job_id: str) -> int:
        """Get the highest version number for rubrics of a job."""
        result = await self.db.execute(
            select(func.max(Rubric.version)).where(Rubric.job_id == job_id)
        )
        max_version = result.scalar_one_or_none()
        return max_version if max_version else 0

    # ─── Application Queries ─────────────────────────────────────────

    async def get_applications_by_group(self, job_id: str):
        result = await self.db.execute(
            select(Application.status, func.count(Application.id))
            .where(
                Application.job_id == job_id,
                Application.deleted_at.is_(None),
            )
            .group_by(Application.status)
        )
        return result.all()

    async def get_total_applications_count(self, job_id: str) -> int:
        result = await self.db.execute(
            select(func.count(Application.id))
            .where(
                Application.job_id == job_id,
                Application.deleted_at.is_(None),
            )
        )
        return result.scalar_one()

    async def get_applications_of_job(
        self,
        job_id: str,
        current_rubric_id: str,
        page_size: int = 15,
        offset: int = 0,
        sort: str = "score_desc",
    ):
        stmt = (
            select(Application, Score)
            .outerjoin(
                Score,
                (Score.application_id == Application.id)
                & (Score.rubric_id == current_rubric_id)
                & (Score.is_active.is_(True)),
            )
            .where(
                Application.job_id == job_id,
                Application.deleted_at.is_(None),
            )
            .options(
                selectinload(Application.candidate),
                selectinload(Application.resume),
            )
        )

        if sort == "score_desc":
            stmt = stmt.order_by(
                Score.overall_score.desc().nulls_last(),
                Application.created_at.desc(),
            )
        else:
            stmt = stmt.order_by(Application.created_at.desc())

        stmt = stmt.limit(page_size).offset(offset)
        result = await self.db.execute(stmt)
        return result.all()

    # ─── Transaction Helpers ─────────────────────────────────────────

    async def commit(self):
        await self.db.commit()

    async def rollback(self):
        await self.db.rollback()
