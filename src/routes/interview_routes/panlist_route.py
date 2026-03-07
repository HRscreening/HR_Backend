from fastapi import APIRouter,Request,Depends,status,Query,Body
from  typing import Optional,List
from src.dtos.interviews_dtos.panel_dto import AvailableSlot
from src.dependency import get_panelist_service , PanelistService

unproducted_router = APIRouter(prefix="/api/panel", tags=["Interview Round Configurations Management"])


@unproducted_router.get("/get-details-for-form", status_code=status.HTTP_200_OK)
async def get_round_configs(
    token: str = Query(...),
    panelist_service: PanelistService = Depends(get_panelist_service)
):
    
    
    round_configs = await panelist_service.get_panelist_form_details(availability_token=token)
    return round_configs


@unproducted_router.post("/submit-availability", status_code=status.HTTP_200_OK)
async def get_round_configs(
    available_slots: list[AvailableSlot] = Body(...),
    token: str = Query(...),
    panelist_service: PanelistService = Depends(get_panelist_service)
):
    
    round_configs = await panelist_service.submit_panelist_availability(availability_token=token, available_slots=available_slots)
    return round_configs
