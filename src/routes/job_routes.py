"""
Job Routes — API endpoints for job + rubric lifecycle.

Endpoints:
  POST /upload-jd          — Extract JD text and generate rubric preview (no DB)
  POST /set-rubric         — Create new Job + Rubric (single transaction)
  PUT  /{job_id}/rubric    — Update rubric on existing job (new version)
  DELETE /{job_id}         — Delete job and all associated data
  POST /{job_id}/regenerate-rubric  — Re-generate rubric from new JD for existing job
  GET  /get-jobs           — List jobs
  GET  /get-job/{job_id}   — Job overview with rubric + analytics
  GET  /{job_id}/rubric/export — Download active rubric as JSON
  POST /process-applications-zip-file/{job_id}  — Upload resumes
  POST /process-resumes/{job_id}   — Trigger scoring (internal/testing)
  GET  /get-applications/{job_id}  — Paginated applications list
"""

import json
from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    Request,
    status,
    File,
    UploadFile,
    BackgroundTasks,
    Body,
    Query,
)
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Dict, Any
from configs.postgress_db import get_db
from src.schemas.rubric_schemas import SetRubricRequest, UpdateRubricRequest, GenerateRubricPreviewRequest
from src.schemas.job_schemas import JobOverviewResponseNew, RubricVersionsResponse
from src.services.resume_services import score_resumes_service
from src.dependency import get_job_service, JobService, get_application_service
from src.services.application_service import ApplicationService
from src.utils.file_manager import fileManager
from src.dtos.job_settings_dto import CreateJobSettingsDTO,UpdateJobSettingsDTO

router = APIRouter(prefix="/api/jobs", tags=["Job Management"])


# ─── 1. Extract JD (AI preview, no DB writes) ────────────────────────

@router.post("/upload-jd", status_code=status.HTTP_200_OK)
async def extract_jd(
    file: UploadFile = File(...),
    job_service: JobService = Depends(get_job_service),
):
    """Upload a JD file -> fast AI analysis for job form prefill (no DB writes)."""
    result = await job_service.extract_jd(file)
    return result


# ─── 1.5 Generate Rubric Preview (Step 2 → Step 3) ───────────────────

@router.post("/generate-rubric-preview", status_code=status.HTTP_200_OK)
async def generate_rubric_preview(
    data: GenerateRubricPreviewRequest,
    job_service: JobService = Depends(get_job_service),
):
    """
    Generate grouped + weighted rubric JSON from raw JD text.
    Returns validated rubric for UI editing (no DB writes).
    """
    return await job_service.generate_rubric_preview(
        raw_jd_text=data.raw_jd_text,
        job_data=data.job_data.model_dump(),
    )


# ─── 2. Set Rubric (Create Job + Rubric) ─────────────────────────────

@router.post("/set-rubric", status_code=status.HTTP_201_CREATED)
async def set_rubric(
    request: Request,
    data: SetRubricRequest,
    job_service: JobService = Depends(get_job_service),
):
    """
    Create a new Job and its first Rubric in a single atomic transaction.
    Called when the user clicks "Set Rubric" on the create-job wizard.
    """
    user_id = request.state.user.id
    ctx = request.state.context

    org_id = ctx.org_id if ctx.type == "org" else None

    if ctx.type not in ("org", "personal"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid context type",
        )

    result = await job_service.set_rubric(
        data=data,
        user_id=user_id,
        org_id=org_id,
    )

    return {
        "status": "success",
        "message": "Job and rubric created successfully",
        **result,
    }


# ─── 2.5. Re-parse JD for Existing Job ──────────────────────────────

@router.post("/{job_id}/jd/reparse", status_code=status.HTTP_200_OK)
async def reparse_jd(
    job_id: str,
    file: UploadFile = File(...),
    job_service: JobService = Depends(get_job_service),
):
    """Upload new JD for existing job → create new document → enqueue parsing."""
    result = await job_service.reparse_jd(job_id, file)
    return result


# ─── 3. Update Rubric on Existing Job ────────────────────────────────

@router.put("/{job_id}/rubric", status_code=status.HTTP_200_OK)
async def update_rubric(
    job_id: UUID,
    request: Request,
    data: UpdateRubricRequest,
    job_service: JobService = Depends(get_job_service),
):
    """
    Create a new rubric version for an existing job.
    Old rubric is deactivated, new one becomes active.
    """
    user_id = request.state.user.id

    result = await job_service.update_rubric(
        job_id=str(job_id),
        data=data,
        user_id=user_id,
    )

    return {
        "status": "success",
        "message": "Rubric updated successfully",
        **result,
    }


# ─── 3.5 Rubric Versions (audit + switching) ─────────────────────────

@router.get(
    "/{job_id}/rubrics/versions",
    response_model=RubricVersionsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_rubric_versions(
    job_id: UUID,
    job_service: JobService = Depends(get_job_service),
):
    return await job_service.get_rubric_versions(str(job_id))


@router.post(
    "/{job_id}/rubrics/{rubric_id}/activate",
    status_code=status.HTTP_200_OK,
)
async def activate_rubric_version(
    job_id: UUID,
    rubric_id: UUID,
    request: Request,
    job_service: JobService = Depends(get_job_service),
):
    user_id = request.state.user.id
    result = await job_service.activate_rubric_version(
        job_id=str(job_id),
        rubric_id=str(rubric_id),
        user_id=str(user_id),
    )
    return {"status": "success", **result}


@router.get("/{job_id}/rubric/export", status_code=status.HTTP_200_OK)
async def export_rubric_json(
    job_id: UUID,
    request: Request,
    job_service: JobService = Depends(get_job_service),
):
    """
    Download the active rubric for the job as a JSON file.
    Same access rules as job overview (org or personal context).
    """
    ctx = request.state.context
    if ctx.type == "org":
        if not ctx.org_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization context missing org_id",
            )
        data = await job_service.get_rubric_export(str(job_id))
    elif ctx.type == "personal":
        data = await job_service.get_rubric_export(str(job_id))
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid context type",
        )
    filename = f"rubric-v{data['version']}.json"
    body = json.dumps(data, indent=2)
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\"",
        },
    )


@router.delete("/{job_id}", status_code=status.HTTP_200_OK)
async def delete_job(
    job_id: UUID,
    request: Request,
    job_service: JobService = Depends(get_job_service),
):
    """
    Delete a job and all its associated data (rubrics, applications, scores, resumes, etc).
    Requires authorization (org or personal context).
    """
    ctx = request.state.context
    if ctx.type == "org":
        if not ctx.org_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization context missing org_id",
            )
    elif ctx.type != "personal":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid context type",
        )
    
    result = await job_service.delete_job(str(job_id))
    return {"status": "success", **result}


# ─── 4. Regenerate Rubric from New JD (AI preview) ───────────────────

@router.post("/{job_id}/regenerate-rubric", status_code=status.HTTP_200_OK)
async def regenerate_rubric(
    job_id: UUID,
    file: UploadFile = File(...),
    job_service: JobService = Depends(get_job_service),
):
    """
    Upload a new JD for an existing job -> AI generates rubric preview.
    Does NOT save to DB. User must call PUT /{job_id}/rubric to save.
    """
    result = await job_service.regenerate_rubric(
        job_id=str(job_id),
        file=file,
    )
    return result


# ─── 5. Get Jobs List ────────────────────────────────────────────────

@router.get("/get-jobs", status_code=status.HTTP_200_OK)
async def get_jobs(
    request: Request,
    job_service: JobService = Depends(get_job_service),
):
    user_id = request.state.user.id
    ctx = request.state.context

    if ctx.type == "org":
        jobs = await job_service.get_jobs(user_id, organization_id=ctx.org_id)
    elif ctx.type == "personal":
        jobs = await job_service.get_jobs(user_id, None)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid context type",
        )

    return {"status": "success", "jobs": jobs}


# ─── 6. Get Job Overview ─────────────────────────────────────────────

@router.get(
    "/get-job/{job_id}",
    response_model=JobOverviewResponseNew,
    status_code=status.HTTP_200_OK,
)
async def get_job_overview(
    job_id: UUID,
    request: Request,
    job_service: JobService = Depends(get_job_service),
):
    ctx = request.state.context

    if ctx.type == "org":
        if not ctx.org_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization context missing org_id",
            )
        return await job_service.get_job_overview(
            job_id=str(job_id),
            organization_id=ctx.org_id,
        )

    if ctx.type == "personal":
        return await job_service.get_job_overview(
            job_id=str(job_id),
            organization_id=None,
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid context type",
    )


# ─── 6.5. JD Parsing Status (for upload polling) ─────────────────────

@router.get("/{job_id}/jd/status", status_code=status.HTTP_200_OK)
async def get_jd_status(
    job_id: UUID,
    job_service: JobService = Depends(get_job_service),
):
    """
    Lightweight JD parsing status endpoint.
    Use this for polling after /jobs/upload-jd (works for draft jobs without rubrics).
    """
    return await job_service.get_jd_status(str(job_id))


# ─── 7. Process Applications (resume upload) ─────────────────────────

@router.post(
    "/process-applications-zip-file/{job_id}",
    status_code=status.HTTP_202_ACCEPTED,
)
async def process_applications(
    request: Request,
    job_id: UUID,
    background_tasks: BackgroundTasks,
    raw_files: list[UploadFile] = File(...),
    job_service: JobService = Depends(get_job_service),
):
    user_id = request.state.user.id
    ctx = request.state.context

    extracted_files = await fileManager.validate_and_extract(raw_files)

    if ctx.type not in ("org", "personal"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid context type",
        )

    msg = await job_service.process_applications(
        job_id=str(job_id),
        background_tasks=background_tasks,
        user_id=str(user_id),
        files=extracted_files,
        organization_id=ctx.org_id if ctx.type == "org" else None,
    )

    if not msg:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start application processing",
        )

    return {
        "status": "success",
        "batch_id": msg.get("batch_id"),
        "total_files": msg.get("total_files"),
        "message": "Resume processing started",
    }


# ─── 8. Process Resumes (internal/testing) ───────────────────────────

@router.post(
    "/process-resumes/{job_id}",
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_scoring(
    request: Request,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Internal endpoint for triggering scoring — for testing only."""
    return await score_resumes_service(
        job_id=str(job_id),
        db=db,
    )


# ─── 9. Batch Progress ───────────────────────────────────────────────

@router.get("/{job_id}/batch-progress", status_code=status.HTTP_200_OK)
async def get_batch_progress(
    job_id: UUID,
    batch_id: UUID = Query(None),
    job_service: JobService = Depends(get_job_service),
):
    return await job_service.get_batch_progress(
        job_id=str(job_id),
        batch_id=str(batch_id) if batch_id else None,
    )


# ─── 10. Get Applications ────────────────────────────────────────────

@router.delete("/{job_id}/applications/{application_id}", status_code=status.HTTP_200_OK)
async def delete_application(
    job_id: UUID,
    application_id: UUID,
    application_service: ApplicationService = Depends(get_application_service),
):
    """Delete an application and all associated data (scores, resumes) for this job."""
    result = await application_service.delete_application(
        application_id=str(application_id),
        job_id=str(job_id),
    )
    return result


@router.get("/get-applications/{job_id}", status_code=status.HTTP_200_OK)
async def get_applications(
    job_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("score_desc"),
    job_service: JobService = Depends(get_job_service),
):
    return await job_service.get_applications(
        job_id=str(job_id),
        page=page,
        page_size=page_size,
        sort=sort,
    )



@router.get("/settings/{job_id}", status_code=status.HTTP_200_OK)
async def get_job_settings(
    job_id: UUID,
    job_service: JobService = Depends(get_job_service)
):
    settings = await job_service.get_job_settings(str(job_id))
    return settings


@router.patch("/{job_id}/edit-settings", status_code=status.HTTP_200_OK)
async def update_job_settings(
    job_id: UUID,
    payload: UpdateJobSettingsDTO,
    job_service: JobService = Depends(get_job_service)
):
    return await job_service.update_job_settings(str(job_id), payload)

@router.post("/create-settings/{job_id}", status_code=status.HTTP_201_CREATED)
async def create_job_settings(
    job_id: UUID,
    request: Request,
    setting_data: CreateJobSettingsDTO,
    job_service: JobService = Depends(get_job_service)
):
    user_id = request.state.user.id
    ctx = request.state.context

    
    return await job_service.create_job_settings(str(job_id),setting_data,user_id)
