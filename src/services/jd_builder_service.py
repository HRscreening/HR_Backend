"""
JD Builder Service — orchestrates the AI JD generation pipeline.

Responsibilities:
  - Call generate_jd_from_answers() with structured Q&A data
  - Optionally persist the generated JD as a new draft version
  - Return the generated content to the caller

No DB writes for preview-only requests; the caller can choose to save.
"""

from typing import Optional
from uuid import UUID

from configs.log_config import get_logger
from src.pipelines.generate_jd import generate_jd_from_answers, generate_jd_from_prompt
from src.repositories.jd_repository import JDRepository
from src.schemas.jd_builder_schemas import (
    GeneratedJDOutput,
    JDBuilderAnswers,
    JDVersionResponse,
)
from src.services.errors.base import DomainError
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("jd_builder_service")


# ── Error classes ───────────────────────────────────────────────────────────────

class JDGenerationFailed(DomainError):
    code = "JD_GENERATION_FAILED"
    message = "Failed to generate job description. Please try again."
    status_code = 502


# ── Service ─────────────────────────────────────────────────────────────────────

class JDBuilderService:
    def __init__(
        self,
        jd_repository: JDRepository,
        db: AsyncSession,
    ):
        self.jd_repo = jd_repository
        self.db = db

    async def preview_jd_from_prompt(self, prompt: str) -> GeneratedJDOutput:
        """Generate a JD preview from a free-form recruiter prompt. Nothing is saved."""
        result = await generate_jd_from_prompt(prompt)
        return GeneratedJDOutput(
            generated_jd_text=result.job_description_markdown,
            suggested_title=result.suggested_title,
            suggested_location=result.suggested_location,
            suggested_salary=result.suggested_salary,
        )

    async def preview_jd(self, answers: JDBuilderAnswers) -> GeneratedJDOutput:
        """
        Generate a JD preview from Q&A answers without saving it.

        Returns the raw LLM output — title, markdown content, and optional
        location/salary suggestions. Nothing is written to the database.
        """
        result = await generate_jd_from_answers(answers)
        return GeneratedJDOutput(
            generated_jd_text=result.job_description_markdown,
            suggested_title=result.suggested_title,
            suggested_location=result.suggested_location,
            suggested_salary=result.suggested_salary,
        )

    async def generate_and_save(
        self,
        answers: JDBuilderAnswers,
        job_id: UUID,
        created_by_id: UUID,
        org_id: Optional[UUID],
    ) -> JDVersionResponse:
        """
        Generate a JD from Q&A answers and persist it as a new draft version.

        The saved version uses the AI-suggested title and stores the raw answers
        in JSONB for auditability / future regeneration.

        Returns the saved JDVersionResponse.
        """
        result = await generate_jd_from_answers(answers)

        version_number = await self.jd_repo.next_version_number(job_id)

        jd = await self.jd_repo.create(
            job_id=job_id,
            organization_id=org_id,
            version_number=version_number,
            title=result.suggested_title,
            content=result.job_description_markdown,  # _JDLLMOutput field
            raw_answers=answers.model_dump(mode="json"),
            generation_method="ai_generated",
            created_by_id=created_by_id,
        )

        await self.db.commit()
        await self.db.refresh(jd)

        logger.info(
            f"[JD_BUILDER] saved ai-generated JD: job={job_id} "
            f"version={version_number} title='{result.suggested_title}'"
        )

        return JDVersionResponse.model_validate(jd)
