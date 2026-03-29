from fastapi import APIRouter,HTTPException,Depends,Request,status,Query
from  typing import Optional,List
from uuid import UUID
from src.dependency import get_application_service,ApplicationService
from src.models.enums import ApplicationStatus
from src.schemas.candidate_schemas import CandidateCreateSchema,CandidateUpdateSchema
from src.schemas.application_schema import UpdateApplicationStatusRequest ,FlagApplicationRequest,MoveApplicationRequest

router = APIRouter(prefix="/api/application", tags=["Application Management"])


@router.patch("/change-status/{application_id}",status_code=status.HTTP_200_OK)
async def change_application_status(application_id: UUID, body: UpdateApplicationStatusRequest, request: Request,application_service: ApplicationService = Depends(get_application_service)):
    user_id = request.state.user.id
    ctx_type = request.state.context.type

    if ctx_type == "org":
        await application_service.change_application_status(
            application_id=application_id,
            new_status=body.new_status,
        )
    elif ctx_type == "personal":
        await application_service.change_application_status(
            application_id=application_id,
            new_status=body.new_status,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid context type",
        )

    return {
        "status": "success",
        "message": f"Application status changed to {body.new_status.value} successfully"
    }


# creates a new candidate and attaches it to application, this is used in application flow when candidate info is filled for the first time. For subsequent edits of candidate info, candidate edit endpoint will be used which will directly update candidate info without creating new candidate or attachment.
@router.post("/attach-candidate/{application_id}",status_code=status.HTTP_200_OK)
async def attach_candidate_to_application(application_id: UUID, candidate_info: CandidateCreateSchema, request: Request,application_service: ApplicationService = Depends(get_application_service)):
    user_id = request.state.user.id
    ctx_type = request.state.context.type

    if ctx_type == "org":
        await application_service.attach_candidate_to_application(
            application_id=application_id,
            candidate_data=candidate_info,
            org_id=request.state.context.org_id,
        )
    elif ctx_type == "personal":
        await application_service.attach_candidate_to_application(
            application_id=application_id,
            candidate_data=candidate_info,
            org_id=None,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid context type",
        )

    return {
        "status": "success",
        "message": f"Candidate attached to application successfully"
    }


@router.patch("/flag/{application_id}",status_code=status.HTTP_200_OK)
async def flag_application(application_id: UUID, request: Request, body:FlagApplicationRequest,application_service: ApplicationService = Depends(get_application_service)):
    user_id = request.state.user.id
    ctx_type = request.state.context.type
    

    if ctx_type == "org":
        await application_service.flag_application(
            application_id=application_id,
            flag_reason=body.flag_reason
        )
    elif ctx_type == "personal":
        await application_service.flag_application(
            application_id=application_id,
            flag_reason=body.flag_reason,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid context type",
        )

    return {
        "status": "success",
        "message": "Application flagged successfully"
    }
    
      
@router.patch("/unflag/{application_id}",status_code=status.HTTP_200_OK)
async def flag_application(application_id: UUID, request: Request, application_service: ApplicationService = Depends(get_application_service)):
    user_id = request.state.user.id
    ctx_type = request.state.context.type
    

    if ctx_type == "org":
        await application_service.unflag_application(
            application_id=application_id,
            org_id=request.state.context.org_id,
        )
    elif ctx_type == "personal":
        await application_service.unflag_application(
            application_id=application_id,
            org_id=None,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid context type",
        )

    return {
        "status": "success",
        "message": "Application unflagged successfully"
    }
   
   
   
    
@router.patch("/star/{application_id}",status_code=status.HTTP_200_OK)
async def star_application(application_id: UUID, request: Request,application_service: ApplicationService = Depends(get_application_service)):
    user_id = request.state.user.id
    ctx_type = request.state.context.type
    

    if ctx_type == "org":
        await application_service.star_application(
            application_id=application_id,
            org_id=request.state.context.org_id,
        )
    elif ctx_type == "personal":
        await application_service.star_application(
            application_id=application_id,
            org_id=None,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid context type",
        )

    return {
        "status": "success",
        "message": "Application flagged successfully"
    }
    
      
@router.patch("/unstar/{application_id}",status_code=status.HTTP_200_OK)
async def unstar_application(application_id: UUID, request: Request, application_service: ApplicationService = Depends(get_application_service)):
    user_id = request.state.user.id
    ctx_type = request.state.context.type
    

    if ctx_type == "org":
        await application_service.unstar_application(
            application_id=application_id,
            org_id=request.state.context.org_id,
        )
    elif ctx_type == "personal":
        await application_service.unstar_application(
            application_id=application_id,
            org_id=None,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid context type",
        )

    return {
        "status": "success",
        "message": "Application unflagged successfully"
    }



@router.delete("/delete/{application_id}",status_code=status.HTTP_200_OK)     
async def delete_application(application_id: UUID, request: Request,application_service: ApplicationService = Depends(get_application_service)):
    user_id = request.state.user.id
    ctx_type = request.state.context.type

    if ctx_type == "org":
        await application_service.delete_application(
            application_id=application_id,
            org_id=request.state.context.org_id,
        )
    elif ctx_type == "personal":
        await application_service.delete_application(
            application_id=application_id,
            org_id=None,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid context type",
        )

    return {
        "status": "success",
        "message": "Application deleted successfully"
    }




@router.post("/move-to-round/{application_id}",status_code=status.HTTP_200_OK)
async def move_application_to_round(application_id: UUID, data:MoveApplicationRequest,application_service: ApplicationService = Depends(get_application_service)):
    return await application_service.move_to_round(
        application_id=application_id,
        round_number=data.target_round,
        job_id=data.job_id
    )
    
