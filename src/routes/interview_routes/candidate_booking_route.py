from fastapi import APIRouter, Depends, Query, Body, status
from src.dependency import get_interview_service
from src.services.interview_services.interview_service import InterviewService
from src.dtos.interviews_dtos.interviews_dto import BookSlotRequest, BookSequentialSlotsRequest


unprotected_router = APIRouter(
    prefix="/api/interview/booking",
    tags=["Candidate Slot Booking"],
)


@unprotected_router.get("/form", status_code=status.HTTP_200_OK)
async def get_booking_form(
    token: str = Query(..., description="Candidate booking JWT"),
    interview_service: InterviewService = Depends(get_interview_service),
):
    """Return available slots for the candidate to pick from."""
    return await interview_service.get_booking_form(token=token)


@unprotected_router.post("/book-panel", status_code=status.HTTP_200_OK)
async def book_slot(
    body: BookSlotRequest = Body(...),
    token: str = Query(..., description="Candidate booking JWT"),
    interview_service: InterviewService = Depends(get_interview_service),
):
    """PANEL mode: candidate picks one slot from the shared pool."""
    return await interview_service.book_slot(token=token, slot_id=str(body.slot_id))


@unprotected_router.post("/book-sequential", status_code=status.HTTP_200_OK)
async def book_sequential_slots(
    body: BookSequentialSlotsRequest = Body(...),
    token: str = Query(..., description="Candidate booking JWT"),
    interview_service: InterviewService = Depends(get_interview_service),
):
    """SEQUENTIAL mode: candidate picks one slot per panelist."""
    bookings = [
        {"panelist_email": b.panelist_email, "slot_id": str(b.slot_id)}
        for b in body.bookings
    ]
    return await interview_service.book_sequential_slots(token=token, bookings=bookings)
