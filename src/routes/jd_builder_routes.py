"""
JD Builder Routes — AI-powered job description generation.

Endpoints:
  POST /api/jd-builder/preview         — Generate a JD preview (no DB write)
  POST /api/jd-builder/generate-and-save — Generate and save as a new JD draft version
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from src.dependency import get_jd_builder_service
from src.services.jd_builder_service import JDBuilderService
from src.schemas.jd_builder_schemas import (
    GeneratedJDOutput,
    JDBuilderAnswers,
    JDFromPromptRequest,
    JDVersionResponse,
)

router = APIRouter(prefix="/api/jd-builder", tags=["JD Builder (AI)"])


@router.post(
    "/preview-from-prompt",
    response_model=GeneratedJDOutput,
    status_code=status.HTTP_200_OK,
)
async def preview_jd_from_prompt(
    data: JDFromPromptRequest,
    service: JDBuilderService = Depends(get_jd_builder_service),
):
    """Generate a JD from a free-form recruiter prompt. Nothing is saved."""
    return await service.preview_jd_from_prompt(data.prompt)


@router.post(
    "/preview",
    response_model=GeneratedJDOutput,
    status_code=status.HTTP_200_OK,
)
async def preview_jd(
    answers: JDBuilderAnswers,
    service: JDBuilderService = Depends(get_jd_builder_service),
):
    """
    Generate a polished Job Description from Q&A answers without saving it.
    Use this to let the recruiter review the AI output before committing.
    """
    return await service.preview_jd(answers)


@router.post(
    "/generate-and-save",
    response_model=JDVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_and_save_jd(
    answers: JDBuilderAnswers,
    job_id: UUID,
    request: Request,
    service: JDBuilderService = Depends(get_jd_builder_service),
):
    """
    Generate a JD from Q&A answers and save it as a new draft version for the
    specified job. The recruiter can then review, edit, and activate it.
    """
    user_id = request.state.user.id
    ctx = request.state.context
    org_id = ctx.org_id if ctx.type == "org" else None

    return await service.generate_and_save(
        answers=answers,
        job_id=job_id,
        created_by_id=user_id,
        org_id=org_id,
    )
