from fastapi import APIRouter,HTTPException,Depends,Request,status,Query
from  typing import Optional,List
from uuid import UUID
from src.dependency import get_candidate_service,CandidateService
from src.models.enums import ApplicationStatus
from src.schemas.candidate_schemas import CandidateCreateSchema,CandidateUpdateSchema
router = APIRouter(prefix="/api/candidate", tags=["Candidate Management"])



@router.patch("/create",status_code=status.HTTP_200_OK)
async def create_candidate(application_id: str, candidate_info: CandidateCreateSchema, request: Request,candidate_service: CandidateService = Depends(get_candidate_service)):
    user_id = request.state.user.id
    ctx_type = request.state.context.type

    if ctx_type == "org":
        await candidate_service.create_candidate(
            application_id=application_id,
            candidate_info=candidate_info,
            org_id=request.state.context.org_id,
        )
    elif ctx_type == "personal":
        await candidate_service.edit_candidate_info(
            application_id=application_id,
            candidate_info=candidate_info,
            org_id=None,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid context type",
        )

    return {
        "status": "success",
        "message": f"Canidate Info edit successfully"
    }

 

@router.patch("/edit/{candidate_id}",status_code=status.HTTP_200_OK)
async def create_candidate(candidate_id: str, candidate_info: CandidateUpdateSchema, request: Request,candidate_service: CandidateService = Depends(get_candidate_service)):
    user_id = request.state.user.id
    ctx_type = request.state.context.type

    if ctx_type == "org":
        await candidate_service.edit_candidate_info(
            candidate_id=candidate_id,
            candidate_info=candidate_info,
            org_id=request.state.context.org_id,
        )
    elif ctx_type == "personal":
        await candidate_service.edit_candidate_info(
            candidate_id=candidate_id,
            candidate_info=candidate_info,
            org_id=None,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid context type",
        )

    return {
        "status": "success",
        "message": f"Canidate Info edit successfully"
    }

 
