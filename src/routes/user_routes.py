from fastapi import APIRouter,Request,Depends,status
from  typing import Optional

router = APIRouter(prefix="/api/user", tags=["User Management"])
from src.dependency import get_user_service,UserService


@router.get("/get-user",status_code=status.HTTP_200_OK)
async def get_user(request: Request, user_service: UserService = Depends(get_user_service)):
    user_id = request.state.user.id
    user =  await user_service.get_user_by_id(user_id)
    return {
        "status": "success",
        "user": user
    }
