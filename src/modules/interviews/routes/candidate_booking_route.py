from fastapi import APIRouter, Depends, Query, Body, status
from src.dependency import get_interview_service
from src.modules.interviews.services import InterviewService
from src.modules.interviews.dtos.interviews_dto import BookSlotRequest, BookSequentialSlotsRequest,SequentialBookingItem


unprotected_router = APIRouter(
    prefix="/api/interview/booking",
    tags=["Candidate Slot Booking"],
)


@unprotected_router.get("/form", status_code=status.HTTP_200_OK)
async def get_booking_form(
    is_reschedule: bool = Query(False, description="Whether this is for rescheduling an existing interview"),
    token: str = Query(..., description="Candidate booking JWT"),
    interview_service: InterviewService = Depends(get_interview_service),
):
    """Return available slots for the candidate to pick from."""
    return await interview_service.get_booking_form(token=token,is_reschedule=is_reschedule)

# @unprotected_router.post("/book-sequential", status_code=status.HTTP_200_OK)
# async def book_sequential_slots(
#     body: BookSequentialSlotsRequest = Body(...),
#     token: str = Query(..., description="Candidate booking JWT"),
#     interview_service: InterviewService = Depends(get_interview_service),
# ):
#     """SEQUENTIAL mode: candidate picks one slot per panelist."""
#     bookings = [
#         {"panelist_email": b.panelist_email, "slot_id": str(b.slot_id)}
#         for b in body.bookings
#     ]
#     return await interview_service.book_sequential_slots(token=token, bookings=bookings)



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
    body: BookSlotRequest = Body(...),
    token: str = Query(..., description="Candidate booking JWT"),
    interview_service: InterviewService = Depends(get_interview_service),
):
    """SEQUENTIAL mode: candidate picks one slot per panelist."""

    return await interview_service.book_sequential_slot(token=token, slot_id=str(body.slot_id))






@unprotected_router.post("/reschedule-to-new-slot", status_code=status.HTTP_200_OK)
async def book_sequential_slots(
    body: BookSlotRequest = Body(...),
    token: str = Query(..., description="Candidate booking JWT"),
    interview_service: InterviewService = Depends(get_interview_service),
):
    """SEQUENTIAL mode: candidate picks one slot per panelist."""
    
    return await interview_service.reschedule_to_new_slot(token=token, new_slot_id=str(body.slot_id))


@unprotected_router.post("/cancel-interview", status_code=status.HTTP_200_OK)
async def book_sequential_slots(
    cancellation_reason: str = Body(..., embed=True, description="Reason for cancellation"),
    token: str = Query(..., description="Candidate booking JWT"),
    interview_service: InterviewService = Depends(get_interview_service),
):
    """SEQUENTIAL mode: candidate picks one slot per panelist."""

    return await interview_service.cancel_interview(token=token, cancellation_reason=cancellation_reason)



@unprotected_router.post("/ask-for-slots", status_code=status.HTTP_200_OK)
async def book_sequential_slots(
    token: str = Query(..., description="Candidate booking JWT"),
    interview_service: InterviewService = Depends(get_interview_service),
):
    """SEQUENTIAL mode: candidate picks one slot per panelist."""

    return await interview_service.request_for_slots(token=token)




