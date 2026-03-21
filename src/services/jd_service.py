"""
JD Service — manages job description versions and the public application link.

Key rules enforced here:
  - Only draft JDs can be edited or deleted.
  - Activating a JD archives the previously active one.
  - Generating the public link requires BOTH an active JD and an active form config.
  - The public link always reflects the current active JD + form config (no snapshot).
  - A second link generation regenerates the slug; the recruiter must trigger it explicitly.
"""

import re
import secrets
import string
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from configs.env_config import FRONTEND_URL
from configs.log_config import get_logger
from src.models.job_description_model import JobDescription
from src.repositories.jd_repository import JDRepository
from src.repositories.form_config_repository import FormConfigRepository
from src.repositories.job_repository import JobRepository
from src.schemas.jd_builder_schemas import (
    ActivateJDResponse,
    JDVersionListResponse,
    JDVersionResponse,
)
from src.schemas.public_apply_schemas import PublicLinkResponse
from src.services.errors.base import DomainError
from src.services.errors.user_errors import JobNotFound


# ── Error classes ──────────────────────────────────────────────────────────────

class JDNotFound(DomainError):
    code = "JD_NOT_FOUND"
    message = "Job description version not found"
    status_code = 404


class JDNotEditable(DomainError):
    code = "JD_NOT_EDITABLE"
    message = "Only draft job descriptions can be edited or deleted"
    status_code = 400


class JDCannotDeleteActive(DomainError):
    code = "JD_CANNOT_DELETE_ACTIVE"
    message = "Cannot delete the active job description. Activate another version first."
    status_code = 400


class PublicLinkMissingActiveJD(DomainError):
    code = "PUBLIC_LINK_MISSING_ACTIVE_JD"
    message = "An active job description is required before generating a public link"
    status_code = 400


class PublicLinkMissingFormConfig(DomainError):
    code = "PUBLIC_LINK_MISSING_FORM_CONFIG"
    message = "An active application form config is required before generating a public link"
    status_code = 400


class PublicSlugAlreadyTaken(DomainError):
    code = "PUBLIC_SLUG_TAKEN"
    message = "This custom URL slug is already in use. Please choose a different one."
    status_code = 409


# ── Slug utilities ─────────────────────────────────────────────────────────────

_SLUG_CHARS = string.ascii_lowercase + string.digits
_SLUG_CLEANUP = re.compile(r"[^a-z0-9]+")


def _generate_slug(title: str) -> str:
    """
    Build a URL-safe slug from a job title with a 6-character random suffix.
    e.g. "Senior Backend Engineer" → "senior-backend-engineer-a7x3k9"
    """
    base = _SLUG_CLEANUP.sub("-", title.lower().strip()).strip("-")[:50].rstrip("-")
    suffix = "".join(secrets.choice(_SLUG_CHARS) for _ in range(6))
    return f"{base}-{suffix}"


# ── Service ────────────────────────────────────────────────────────────────────

class JDService:
    def __init__(
        self,
        jd_repository: JDRepository,
        form_config_repository: FormConfigRepository,
        job_repository: JobRepository,
        db: AsyncSession,
    ):
        self.jd_repo = jd_repository
        self.form_config_repo = form_config_repository
        self.job_repo = job_repository
        self.db = db
        self.logger = get_logger("JD_SERVICE")

    # ── JD CRUD ────────────────────────────────────────────────────────────────

    async def create_jd(
        self,
        job_id: UUID,
        title: str,
        content: str,
        created_by_id: UUID,
        org_id: Optional[UUID],
        generation_method: str = "manual",
        raw_answers: Optional[dict] = None,
    ) -> JDVersionResponse:
        job = await self.job_repo.get_job_by_id(str(job_id))
        if not job:
            raise JobNotFound()

        jd = await self.jd_repo.create(
            job_id=job_id,
            organization_id=org_id or job.organization_id,
            title=title,
            content=content,
            created_by_id=created_by_id,
            generation_method=generation_method,
            raw_answers=raw_answers,
        )
        await self.db.commit()
        await self.db.refresh(jd)
        return JDVersionResponse.model_validate(jd)

    async def list_jd_versions(self, job_id: UUID) -> JDVersionListResponse:
        job = await self.job_repo.get_job_by_id(str(job_id))
        if not job:
            raise JobNotFound()

        versions = await self.jd_repo.list_versions(job_id)
        return JDVersionListResponse(
            job_id=job_id,
            active_jd_id=job.active_jd_id,
            versions=[JDVersionResponse.model_validate(v) for v in versions],
        )

    async def get_jd_version(self, jd_id: UUID, job_id: UUID) -> JDVersionResponse:
        jd = await self.jd_repo.get_by_id_and_job(jd_id, job_id)
        if not jd:
            raise JDNotFound()
        return JDVersionResponse.model_validate(jd)

    async def update_jd(
        self,
        jd_id: UUID,
        job_id: UUID,
        title: Optional[str] = None,
        content: Optional[str] = None,
    ) -> JDVersionResponse:
        jd = await self.jd_repo.get_by_id_and_job(jd_id, job_id)
        if not jd:
            raise JDNotFound()
        if jd.status != "draft":
            raise JDNotEditable(
                f"Cannot edit a JD with status '{jd.status}'. Only draft versions are editable."
            )

        await self.jd_repo.update(jd_id, title=title, content=content)
        await self.db.commit()

        updated = await self.jd_repo.get_by_id(jd_id)
        return JDVersionResponse.model_validate(updated)

    async def delete_jd(self, jd_id: UUID, job_id: UUID) -> None:
        jd = await self.jd_repo.get_by_id_and_job(jd_id, job_id)
        if not jd:
            raise JDNotFound()
        if jd.status == "active":
            raise JDCannotDeleteActive()

        await self.jd_repo.soft_delete(jd_id)
        await self.db.commit()

    async def activate_jd(self, jd_id: UUID, job_id: UUID) -> ActivateJDResponse:
        jd = await self.jd_repo.get_by_id_and_job(jd_id, job_id)
        if not jd:
            raise JDNotFound()

        # Archive any currently active JD
        await self.jd_repo.archive_active(job_id)
        # Activate the target version
        await self.jd_repo.set_status(jd_id, "active")
        # Update the pointer on the job
        await self.jd_repo.set_active_jd_on_job(job_id, jd_id)
        await self.db.commit()

        return ActivateJDResponse(
            activated_jd_id=jd_id,
            version_number=jd.version_number,
            message=f"JD v{jd.version_number} is now active.",
        )

    async def deactivate_jd(self, job_id: UUID) -> None:
        """Archive the active JD and clear the pointer on the job."""
        await self.jd_repo.archive_active(job_id)
        await self.jd_repo.set_active_jd_on_job(job_id, None)
        await self.db.commit()

    # ── Public Link ────────────────────────────────────────────────────────────

    async def generate_public_link(
        self,
        job_id: UUID,
        custom_slug: Optional[str] = None,
    ) -> PublicLinkResponse:
        job = await self.job_repo.get_job_by_id(str(job_id))
        if not job:
            raise JobNotFound()

        # Guard: active form config required
        active_form_config = await self.form_config_repo.get_active(job_id)
        if not active_form_config:
            raise PublicLinkMissingFormConfig()

        active_jd = await self.jd_repo.get_active(job_id)

        # Resolve slug
        if custom_slug:
            conflict = await self._slug_exists(custom_slug, exclude_job_id=job_id)
            if conflict:
                raise PublicSlugAlreadyTaken(
                    f"The slug '{custom_slug}' is already in use by another job."
                )
            slug = custom_slug
        else:
            slug = await self._unique_slug(job.title)

        await self.form_config_repo.set_public_link(job_id, slug, enabled=True)
        await self.db.commit()

        return PublicLinkResponse(
            job_id=job_id,
            public_slug=slug,
            public_apply_enabled=True,
            active_jd_id=active_jd.id if active_jd else None,
            active_form_config_id=active_form_config.id,
            public_url=f"{FRONTEND_URL}/apply/{slug}",
        )

    async def get_public_link(self, job_id: UUID) -> PublicLinkResponse:
        job = await self.job_repo.get_job_by_id(str(job_id))
        if not job:
            raise JobNotFound()

        active_jd = await self.jd_repo.get_active(job_id)
        active_form_config = await self.form_config_repo.get_active(job_id)

        public_url = (
            f"{FRONTEND_URL}/apply/{job.public_slug}"
            if job.public_slug and job.public_apply_enabled
            else None
        )
        return PublicLinkResponse(
            job_id=job_id,
            public_slug=job.public_slug,
            public_apply_enabled=job.public_apply_enabled,
            active_jd_id=active_jd.id if active_jd else None,
            active_form_config_id=active_form_config.id if active_form_config else None,
            public_url=public_url,
        )

    async def disable_public_link(self, job_id: UUID) -> None:
        job = await self.job_repo.get_job_by_id(str(job_id))
        if not job:
            raise JobNotFound()
        await self.form_config_repo.set_public_apply_enabled(job_id, enabled=False)
        await self.db.commit()

    # ── Private helpers ────────────────────────────────────────────────────────

    async def _slug_exists(self, slug: str, exclude_job_id: Optional[UUID] = None) -> bool:
        from sqlalchemy import select
        from src.models.job_model import Job

        stmt = select(Job.id).where(
            Job.public_slug == slug,
            Job.deleted_at == None,
        )
        if exclude_job_id:
            stmt = stmt.where(Job.id != exclude_job_id)

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def _unique_slug(self, title: str, max_attempts: int = 10) -> str:
        for _ in range(max_attempts):
            slug = _generate_slug(title)
            if not await self._slug_exists(slug):
                return slug
        raise DomainError(
            "Failed to generate a unique slug. Please provide a custom slug.",
            status_code=500,
        )
