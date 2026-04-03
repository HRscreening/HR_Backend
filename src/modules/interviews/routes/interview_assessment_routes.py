# FOR 
from fastapi import APIRouter, Depends, Query, Body, status
from fastapi.responses import FileResponse
from src.dependency import get_interview_assessment_service
from src.modules.interviews.services import InterviewAssessmentService
from src.modules.interviews.dtos.interviews_dto import BookSlotRequest, BookSequentialSlotsRequest,SequentialBookingItem
from src.modules.interviews.dtos.interview_assessment_dtos import InterviewAssessmentCreate

router = APIRouter(prefix="/api/assessment",tags=["Interview Assessments"],)
unprotected_router = APIRouter(prefix="/api/assessment",tags=["Interview Assessments - Unprotected"],)

@router.get("/generate-assessment-tags/{job_id}", status_code=status.HTTP_200_OK)
async def generate_assessment_tags(
    job_id: str ,
    title: str = Query(..., description="Title of the interview round, e.g. 'Technical Round', 'HR Round' etc. This is used to generate relevant assessment tags based on the job role and round type."),
    interview_assessment_service: InterviewAssessmentService = Depends(get_interview_assessment_service),
):
    """Return interview details for a given application ID."""
    return await interview_assessment_service.generate_assessment_tags(job_id, title)


@unprotected_router.get("/get-criterias", status_code=status.HTTP_200_OK)
async def get_criterias(
    token: str = Query(..., description="Token containing interview and panelist details"),
    interview_assessment_service: InterviewAssessmentService = Depends(get_interview_assessment_service),
):
    """Return interview details for a given application ID."""
    return await interview_assessment_service.get_interview_assessment_form_parameters(token)

@router.post("/request-assessment/{interview_id}", status_code=status.HTTP_200_OK)
async def request_assessment(
    interview_id: str,
    interview_assessment_service: InterviewAssessmentService = Depends(get_interview_assessment_service),
):
    """Return interview details for a given application ID."""
    return await interview_assessment_service.request_interview_assessment_to_panelist(interview_id)



@unprotected_router.post("/submit/{token}", status_code=status.HTTP_200_OK)
async def submit_assessment(
    token: str,
    assessment_data: InterviewAssessmentCreate = Body(..., description="Assessment data submitted by the panelist"),
    interview_assessment_service: InterviewAssessmentService = Depends(get_interview_assessment_service),
):
    """Return interview details for a given application ID."""
    return await interview_assessment_service.submit_interview_assessment(token, assessment_data)




@unprotected_router.post("/analyze-transcript/{interview_id}", status_code=status.HTTP_200_OK)
async def analyze_transcript(
    interview_id: str,
    interview_assessment_service: InterviewAssessmentService = Depends(get_interview_assessment_service),
):
    """Endpoint to trigger analysis of interview transcript and return feedback."""
    return await interview_assessment_service.analyze_interview_transcript(interview_id)



@unprotected_router.post("/interview-post-processing/{interview_id}", status_code=status.HTTP_200_OK)
async def interview_post_processing(
    interview_id: str,
    interview_assessment_service: InterviewAssessmentService = Depends(get_interview_assessment_service),
):
    """Endpoint to trigger all post processing tasks after an interview is completed, including transcript analysis, panelist assessment requests, and final report generation."""
    return await interview_assessment_service.interview_post_processing(interview_id)


@router.get("/get-assessment/{interview_id}",status_code=status.HTTP_200_OK)
async def get_interview_assessment(interview_id: str,interview_service: InterviewAssessmentService = Depends(get_interview_assessment_service)):
    """Get the AI generated assessment and panelist assessments for a given interview ID."""
    return await interview_service.get_interview_assessment(interview_id)
