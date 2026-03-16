from fastapi import APIRouter,Request,Depends,status,Query,Body
from  typing import Optional,List
from src.dtos.interviews_dtos.panel_dto import AvailableSlot,EditSlotsPayload,RescheduleSlotsPayload
from src.dependency import get_panelist_service , PanelistService

unproducted_router = APIRouter(prefix="/api/panel", tags=["Interview Round Configurations Management"])


@unproducted_router.get("/get-details-for-form", status_code=status.HTTP_200_OK)
async def get_round_configs(
    token: str = Query(...),
    panelist_service: PanelistService = Depends(get_panelist_service)
):
    
    
    round_configs = await panelist_service.get_panelist_form_details(availability_token=token)
    return round_configs


@unproducted_router.get("/get-reschedule-form-details", status_code=status.HTTP_200_OK)
async def get_reschedule_form_details(
    rescheduling_token: str = Query(...),
    panelist_service: PanelistService = Depends(get_panelist_service)
):
    
    
    round_configs = await panelist_service.get_panelist_reschedule_form_details(rescheduling_token=rescheduling_token)
    return round_configs


@unproducted_router.patch("/reschedule-slots", status_code=status.HTTP_200_OK)
async def reschedule_slots(
    rescheduling_token: str = Query(...),
    payload: RescheduleSlotsPayload = Body(...),
    panelist_service: PanelistService = Depends(get_panelist_service)
):
    
    return  await panelist_service.reschedule_slots(rescheduling_token=rescheduling_token,payload=payload)
    


@unproducted_router.post("/submit-availability", status_code=status.HTTP_200_OK)
async def submit_panelist_availability(
    available_slots: list[AvailableSlot] = Body(...),
    token: str = Query(...),
    panelist_service: PanelistService = Depends(get_panelist_service)
):
    
    round_configs = await panelist_service.submit_panelist_availability(availability_token=token, available_slots=available_slots)
    return round_configs


@unproducted_router.patch("/edit-slots", status_code=status.HTTP_200_OK)
async def edit_slots(
    payload: EditSlotsPayload = Body(...),
    token: str = Query(...),
    panelist_service: PanelistService = Depends(get_panelist_service)
):
    
    result = await panelist_service.edit_panelist_availability(availability_token=token, payload=payload)
    return result
