from fastapi import APIRouter,HTTPException,Depends,Request,Query,status,File, UploadFile
from fastapi.responses import JSONResponse
from configs.postgress_db import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from src.middlewares.verify_user import auth_required
# from src.utils.verify_token import verify_token

from src.schemas.user_schemas import NewOrgSchema,NewJobSchema
from src.services import user_services
# from services.errors.auth_errors import EmailAlreadyExists
from  typing import Optional

router = APIRouter(prefix="/api/user", tags=["Organization Management"])


# @router.post("/create-organization",status_code=status.HTTP_201_CREATED)
# async def create_user(request: Request,org_data: NewOrgSchema, db: AsyncSession = Depends(get_db)):
    
#         user_id = request.state.user.id
#         result = await user_services.create_organization(org_data,user_id,db)
        
#         return {
#             "status": "success",
#             "message": "Organization created successfully",
#             "organization_id": result
#         }

