"""
Public Apply Routes — unauthenticated endpoints for the candidate-facing application portal.

Endpoints:
  GET  /api/public/apply/{slug}  — Fetch job info + form questions for rendering the form
  POST /api/public/apply/{slug}  — Submit a candidate application (multipart: form data + resume)
"""

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from pydantic import EmailStr

from src.dependency import get_public_apply_service
from src.services.public_apply_service import PublicApplyService
from src.schemas.public_apply_schemas import (
    PublicApplyRequest,
    PublicApplyResponse,
    PublicJobInfoResponse,
)

unprotected_router = APIRouter(
    prefix="/api/public/apply",
    tags=["Public Apply"],
)


@unprotected_router.get(
    "/{slug}",
    response_model=PublicJobInfoResponse,
    status_code=status.HTTP_200_OK,
)
async def get_apply_page(
    slug: str,
    service: PublicApplyService = Depends(get_public_apply_service),
):
    """
    Return the minimal job info and form question set needed to render the
    public application form. No authentication required.
    """
    return await service.get_job_for_apply_page(slug)


@unprotected_router.post(
    "/{slug}",
    response_model=PublicApplyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_application(
    slug: str,
    # Core required fields
    full_name: str = Form(..., description="Applicant's full name"),
    email: EmailStr = Form(..., description="Applicant's email address"),
    # Optional fields
    phone: str | None = Form(None, description="Applicant's phone number"),
    linkedin_url: str | None = Form(None, description="LinkedIn profile URL"),
    portfolio_url: str | None = Form(None, description="Portfolio or personal website"),
    cover_letter: str | None = Form(None, description="Cover letter text"),
    years_of_experience: int | None = Form(None, description="Total years of experience"),
    current_location: str | None = Form(None, description="Current city/location"),
    notice_period: str | None = Form(None, description="Notice period (e.g. '2 weeks')"),
    current_ctc: str | None = Form(None, description="Current compensation"),
    expected_ctc: str | None = Form(None, description="Expected compensation"),
    # Resume file — always required
    resume: UploadFile = File(..., description="Resume file (PDF or DOCX, max 5 MB)"),
    service: PublicApplyService = Depends(get_public_apply_service),
):
    """
    Submit a candidate application via the public apply link.
    Accepts a multipart form with candidate details and a resume file upload.
    """
    form_data = PublicApplyRequest(
        full_name=full_name,
        email=email,
        phone=phone,
        linkedin_url=linkedin_url,
        portfolio_url=portfolio_url,
        cover_letter=cover_letter,
        years_of_experience=years_of_experience,
        current_location=current_location,
        notice_period=notice_period,
        current_ctc=current_ctc,
        expected_ctc=expected_ctc,
    )

    return await service.submit_application(
        slug=slug,
        form_data=form_data,
        resume_file=resume,
    )
