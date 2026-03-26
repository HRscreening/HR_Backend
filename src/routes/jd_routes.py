"""
JD Routes — versioned job descriptions + public application link management.

Endpoints:
  POST   /api/jobs/{job_id}/jd-versions              — Create a new JD version (manual)
  GET    /api/jobs/{job_id}/jd-versions              — List all JD versions for a job
  GET    /api/jobs/{job_id}/jd-versions/{jd_id}     — Get a specific JD version
  PUT    /api/jobs/{job_id}/jd-versions/{jd_id}     — Update a draft JD version
  DELETE /api/jobs/{job_id}/jd-versions/{jd_id}     — Delete a non-active JD version
  POST   /api/jobs/{job_id}/jd-versions/{jd_id}/activate — Activate a JD version

  POST   /api/jobs/{job_id}/public-link             — Generate / regenerate public apply link
  GET    /api/jobs/{job_id}/public-link             — Get current public link status
  DELETE /api/jobs/{job_id}/public-link             — Disable public applications
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from src.dependency import get_jd_service, JDService
from src.schemas.jd_builder_schemas import (
    ActivateJDResponse,
    CreateManualJDRequest,
    JDVersionListResponse,
    JDVersionResponse,
    UpdateJDRequest,
)
from src.schemas.public_apply_schemas import GeneratePublicLinkRequest, PublicLinkResponse

router = APIRouter(prefix="/api/jobs", tags=["JD Versions & Public Link"])


# ── JD version CRUD ────────────────────────────────────────────────────────────

@router.post(
    "/{job_id}/jd-versions",
    status_code=status.HTTP_201_CREATED,
    response_model=JDVersionResponse,
)
async def create_jd_version(
    job_id: UUID,
    data: CreateManualJDRequest,
    request: Request,
    jd_service: JDService = Depends(get_jd_service),
):
    """Create a new draft JD version by writing or pasting content."""
    user_id = request.state.user.id
    ctx = request.state.context
    org_id = ctx.org_id if ctx.type == "org" else None

    return await jd_service.create_jd(
        job_id=job_id,
        title=data.title,
        content=data.content,
        created_by_id=user_id,
        org_id=org_id,
        generation_method="manual",
    )


@router.get(
    "/{job_id}/jd-versions",
    response_model=JDVersionListResponse,
)
async def list_jd_versions(
    job_id: UUID,
    jd_service: JDService = Depends(get_jd_service),
):
    """List all JD versions for a job (newest first)."""
    return await jd_service.list_jd_versions(job_id)


@router.get(
    "/{job_id}/jd-versions/{jd_id}",
    response_model=JDVersionResponse,
)
async def get_jd_version(
    job_id: UUID,
    jd_id: UUID,
    jd_service: JDService = Depends(get_jd_service),
):
    """Get a specific JD version."""
    return await jd_service.get_jd_version(jd_id, job_id)


@router.put(
    "/{job_id}/jd-versions/{jd_id}",
    response_model=JDVersionResponse,
)
async def update_jd_version(
    job_id: UUID,
    jd_id: UUID,
    data: UpdateJDRequest,
    jd_service: JDService = Depends(get_jd_service),
):
    """Update a draft JD version (title and/or content)."""
    return await jd_service.update_jd(
        jd_id=jd_id,
        job_id=job_id,
        title=data.title,
        content=data.content,
    )


@router.delete(
    "/{job_id}/jd-versions/{jd_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_jd_version(
    job_id: UUID,
    jd_id: UUID,
    jd_service: JDService = Depends(get_jd_service),
):
    """Delete a draft or archived JD version. Active versions cannot be deleted."""
    await jd_service.delete_jd(jd_id, job_id)


@router.post(
    "/{job_id}/jd-versions/{jd_id}/activate",
    response_model=ActivateJDResponse,
)
async def activate_jd_version(
    job_id: UUID,
    jd_id: UUID,
    jd_service: JDService = Depends(get_jd_service),
):
    """
    Activate a JD version. Archives the previously active version.
    The job's active_jd_id pointer is updated.
    """
    return await jd_service.activate_jd(jd_id, job_id)


# ── Public link management ─────────────────────────────────────────────────────

@router.post(
    "/{job_id}/public-link",
    status_code=status.HTTP_201_CREATED,
    response_model=PublicLinkResponse,
)
async def generate_public_link(
    job_id: UUID,
    data: GeneratePublicLinkRequest,
    jd_service: JDService = Depends(get_jd_service),
):
    """
    Generate (or regenerate) the public application link for a job.
    Requires an active JD version AND an active form config.
    """
    return await jd_service.generate_public_link(
        job_id=job_id,
        custom_slug=data.custom_slug,
    )


@router.get(
    "/{job_id}/public-link",
    response_model=PublicLinkResponse,
)
async def get_public_link(
    job_id: UUID,
    jd_service: JDService = Depends(get_jd_service),
):
    """Get the current public link status and URL for a job."""
    return await jd_service.get_public_link(job_id)


@router.delete(
    "/{job_id}/public-link",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def disable_public_link(
    job_id: UUID,
    jd_service: JDService = Depends(get_jd_service),
):
    """Disable public applications for a job (keeps the slug, just turns it off)."""
    await jd_service.disable_public_link(job_id)
