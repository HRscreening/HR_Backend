from fastapi import APIRouter,HTTPException,Depends,Request,status,Query
from  typing import Optional,List
from uuid import UUID
from src.dependency import get_batch_service,BatchService
from src.models.enums import ApplicationStatus

router = APIRouter(prefix="/api/batch", tags=["Bathc Management"])


@router.get("/get-summary/{batch_id}",status_code=status.HTTP_200_OK)
async def get_batch_summary(batch_id: str,request: Request,batch_service: BatchService= Depends(get_batch_service)):
    user_id = request.state.user.id
    ctx_type = request.state.context.type
    
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    elif ctx_type not in ["org","personal"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid context type")

    summary = await batch_service.get_batch_summary(batch_id)
    
    return  {**summary}
