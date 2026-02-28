from fastapi import APIRouter,Request,Depends,status
from  typing import Optional
from src.dtos.interviews_dtos.interview_round_config_dto import CreateInterviewRoundConfigDTO, UpdateInterviewRoundConfigDTO

router = APIRouter(prefix="/api/interview", tags=["Interview Round Configurations Management"])
from src.dependency import get_interview_round_config_service,InterviewRoundConfigService


@router.get("/get-round-configs/{job_id}",status_code=status.HTTP_200_OK)
async def get_round_configs(request: Request,job_id:str, interview_round_config_service: InterviewRoundConfigService = Depends(get_interview_round_config_service)):
    user_id = request.state.user.id
    ctx_type = request.state.context.type

    round_configs = await interview_round_config_service.get_interview_round_configs_by_job(job_id=job_id)
    
    return round_configs



@router.post("/create-round-config/{job_id}",status_code=status.HTTP_201_CREATED)
async def create_round_config(request: Request,job_id:str, config_data:CreateInterviewRoundConfigDTO,interview_round_config_service: InterviewRoundConfigService = Depends(get_interview_round_config_service)):
    user_id = request.state.user.id
    ctx_type = request.state.context.type

    new_config = await interview_round_config_service.create_interview_round_config(job_id=job_id, config_data=config_data)
    
    return new_config



@router.put("/update-round-config/{round_config_id}",status_code=status.HTTP_200_OK)
async def update_round_config(request: Request,round_config_id:str, config_data:UpdateInterviewRoundConfigDTO,interview_round_config_service: InterviewRoundConfigService = Depends(get_interview_round_config_service)):
    user_id = request.state.user.id
    ctx_type = request.state.context.type
    updated_config = await interview_round_config_service.update_interview_round_config(round_config_id=round_config_id, config_data=config_data)
    return updated_config

