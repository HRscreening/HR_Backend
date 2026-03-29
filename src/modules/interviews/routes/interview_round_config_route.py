from fastapi import APIRouter,Request,Depends,status
from  typing import Optional
from src.modules.interviews.dtos.interview_round_config_dto import CreateInterviewRoundConfigDTO, UpdateInterviewRoundConfigDTO, BulkCreateInterviewRoundConfigDTO,RequestPanelistsForSlotsDTO
from src.dependency import get_interview_round_config_service,InterviewRoundConfigService,get_interview_service, InterviewService 

# TODO: Api endpoint_need to be changed
router = APIRouter(prefix="/api/round", tags=["Interview Round Configurations Management"])


@router.get("/{job_id}/get-round-configs",status_code=status.HTTP_200_OK)
async def get_round_configs(request: Request,job_id:str, interview_round_config_service: InterviewRoundConfigService = Depends(get_interview_round_config_service)):
    user_id = request.state.user.id
    ctx_type = request.state.context.type

    round_configs = await interview_round_config_service.get_interview_round_configs_by_job(job_id=job_id)
    
    return round_configs



@router.get("/get-round-config/{round_config_id}",status_code=status.HTTP_200_OK)
async def get_round_config(request: Request,round_config_id:str, interview_round_config_service: InterviewRoundConfigService = Depends(get_interview_round_config_service)):
    user_id = request.state.user.id
    ctx_type = request.state.context.type

    round_config = await interview_round_config_service.get_interview_round_config_by_id(round_config_id=round_config_id)
    
    return round_config


@router.delete("/delete-round-config/{round_config_id}",status_code=status.HTTP_200_OK)
async def get_round_config(request: Request,round_config_id:str, interview_round_config_service: InterviewRoundConfigService = Depends(get_interview_round_config_service)):
    user_id = request.state.user.id
    ctx_type = request.state.context.type

    round_config = await interview_round_config_service.delete_interview_round_config_by_id(round_config_id=round_config_id)
    
    return round_config


@router.post("/create-round-config/{job_id}",status_code=status.HTTP_201_CREATED)
async def create_round_config(request: Request,job_id:str, config_data:CreateInterviewRoundConfigDTO,interview_round_config_service: InterviewRoundConfigService = Depends(get_interview_round_config_service)):
    user_id = request.state.user.id
    ctx_type = request.state.context.type

    new_config = await interview_round_config_service.create_interview_round_config(job_id=job_id, config_data=config_data)
    
    return new_config


@router.post("/bulk-create-round-configs", status_code=status.HTTP_201_CREATED)
async def bulk_create_round_configs(
    request: Request,
    data: BulkCreateInterviewRoundConfigDTO,
    interview_round_config_service: InterviewRoundConfigService = Depends(get_interview_round_config_service),
):
    """Create all interview round configs for a job in a single request."""
    user_id = request.state.user.id
    created = await interview_round_config_service.bulk_create_interview_round_configs(data=data)
    return {"created": len(created), "job_id": data.job_id}



@router.put("/update-round-config/{round_config_id}",status_code=status.HTTP_200_OK)
async def update_round_config(request: Request,round_config_id:str, config_data:UpdateInterviewRoundConfigDTO,interview_round_config_service: InterviewRoundConfigService = Depends(get_interview_round_config_service)):
    user_id = request.state.user.id
    ctx_type = request.state.context.type
    updated_config = await interview_round_config_service.update_interview_round_config(round_config_id=round_config_id, config_data=config_data)
    return updated_config



@router.post("/request-all-panelists-for-slots/{round_config_id}",status_code=status.HTTP_200_OK)
async def update_round_config(request: Request,round_config_id:str,interview_round_config_service: InterviewRoundConfigService = Depends(get_interview_round_config_service)):
    user_id = request.state.user.id
    ctx_type = request.state.context.type
    
    return await interview_round_config_service.request_all_panelist_for_slots(round_config_id=round_config_id)

@router.post("/request-panelists-for-slots/{round_config_id}", status_code=status.HTTP_200_OK)
async def update_round_config(
    request: Request,
    round_config_id: str,
    body: RequestPanelistsForSlotsDTO,
    interview_round_config_service: InterviewRoundConfigService = Depends(get_interview_round_config_service)
):
    user_id = request.state.user.id
    ctx_type = request.state.context.type

    return await interview_round_config_service.request_panelists_for_slots(
        round_config_id,
        body.panelist_ids
    )


# ! it should not be in this route but for now we can keep it here as it is related to interview round config and it is only for hr dashboard
@router.get("/timeline/{interview_id}", status_code=status.HTTP_200_OK)
async def get_interview_timeline(
    request: Request,
    interview_id: str,
    interview_service: InterviewService = Depends(get_interview_service),
):
    """Get formatted timeline events for an interview (HR dashboard)."""
    return await interview_service.get_timeline(interview_id=interview_id)




@router.get("/{job_id}/rounds/overview", status_code=status.HTTP_200_OK)
async def get_rounds_overview(request: Request, job_id: str, interview_round_config_service: InterviewRoundConfigService = Depends(get_interview_round_config_service)):
    """Get an overview of all rounds for a job, including number of applications in each round."""
    user_id = request.state.user.id
    ctx_type = request.state.context.type

    overview = await interview_round_config_service.get_intervew_round_config_overview_by_job(job_id=job_id)
    return overview

@router.get("/{round_config_id}/slots", status_code=status.HTTP_200_OK)
async def get_round_config_slots(request: Request, round_config_id: str, interview_round_config_service: InterviewRoundConfigService = Depends(get_interview_round_config_service)):
    """Get available slots for a round config along with panelist details."""
    user_id = request.state.user.id
    ctx_type = request.state.context.type

    return await interview_round_config_service.get_round_slots(round_config_id=round_config_id)