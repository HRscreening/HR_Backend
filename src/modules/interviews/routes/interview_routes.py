# FOR 
from fastapi import APIRouter, Depends, Query, Body, status
from src.dependency import get_interview_service
from src.modules.interviews.services import InterviewService
from src.modules.interviews.dtos.interviews_dto import BookSlotRequest, BookSequentialSlotsRequest,SequentialBookingItem


router = APIRouter(
    prefix="/api/interview",
    tags=["Interview Management"],
)


@router.get("/get-interview-details/{application_id}", status_code=status.HTTP_200_OK)
async def get_booking_form(
    application_id: str ,
    interview_service: InterviewService = Depends(get_interview_service),
):
    """Return interview details for a given application ID."""
    return await interview_service.get_interview_details(application_id)




