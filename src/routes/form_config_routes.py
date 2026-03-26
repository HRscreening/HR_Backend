"""
Form Config Routes — manage the customisable candidate application form per job.

Endpoints:
  GET    /api/jobs/{job_id}/form-config                           — Get/create current form config
  GET    /api/jobs/{job_id}/form-config/versions                  — List all form config versions
  PUT    /api/jobs/{job_id}/form-config/{config_id}               — Update a draft config's questions
  POST   /api/jobs/{job_id}/form-config/{config_id}/activate      — Activate a config version
  POST   /api/jobs/{job_id}/form-config/new-version               — Create a new draft version
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from src.dependency import get_form_config_service, FormConfigService
from src.schemas.public_apply_schemas import (
    ApplicationFormConfigResponse,
    UpdateFormConfigRequest,
)

router = APIRouter(prefix="/api/jobs", tags=["Application Form Config"])


@router.get(
    "/{job_id}/form-config",
    response_model=ApplicationFormConfigResponse,
)
async def get_form_config(
    job_id: UUID,
    request: Request,
    form_config_service: FormConfigService = Depends(get_form_config_service),
):
    """
    Return the active form config for a job.
    If no config exists yet, creates and returns a draft with the default question set.
    """
    user_id = request.state.user.id
    return await form_config_service.get_or_create_form_config(job_id, user_id)


@router.get(
    "/{job_id}/form-config/versions",
    response_model=list[ApplicationFormConfigResponse],
)
async def list_form_config_versions(
    job_id: UUID,
    form_config_service: FormConfigService = Depends(get_form_config_service),
):
    """List all form config versions for a job (newest first)."""
    return await form_config_service.list_form_config_versions(job_id)


@router.put(
    "/{job_id}/form-config/{config_id}",
    response_model=ApplicationFormConfigResponse,
)
async def update_form_config(
    job_id: UUID,
    config_id: UUID,
    data: UpdateFormConfigRequest,
    form_config_service: FormConfigService = Depends(get_form_config_service),
):
    """
    Update the question list on a draft form config.
    Core fields (full_name, email, resume) cannot be removed.
    """
    return await form_config_service.update_form_config(
        config_id=config_id,
        job_id=job_id,
        questions=data.questions,
    )


@router.post(
    "/{job_id}/form-config/{config_id}/activate",
    response_model=ApplicationFormConfigResponse,
)
async def activate_form_config(
    job_id: UUID,
    config_id: UUID,
    form_config_service: FormConfigService = Depends(get_form_config_service),
):
    """
    Activate a form config version.
    Archives the previously active version and updates the job's active_form_config_id.
    """
    return await form_config_service.activate_form_config(config_id, job_id)


@router.post(
    "/{job_id}/form-config/new-version",
    status_code=status.HTTP_201_CREATED,
    response_model=ApplicationFormConfigResponse,
)
async def create_form_config_version(
    job_id: UUID,
    request: Request,
    data: UpdateFormConfigRequest | None = None,
    form_config_service: FormConfigService = Depends(get_form_config_service),
):
    """
    Create a new draft form config version.
    If questions are provided in the body, use them.
    Otherwise copies the current active config (or uses defaults if none exists).
    """
    user_id = request.state.user.id
    questions = data.questions if data else None
    return await form_config_service.create_new_version(job_id, user_id, questions)
