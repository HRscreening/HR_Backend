from fastapi import APIRouter,HTTPException,Depends,Request,Query,status,File, UploadFile
from fastapi.responses import JSONResponse
from configs.postgress_db import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from middlewares.verify_user import auth_required
from utils.verify_token import verify_token

from schemas.user_schemas import NewOrgSchema,NewJobSchema
from services import user_services
# from services.errors.auth_errors import EmailAlreadyExists
from  typing import Optional

router = APIRouter(prefix="/api/user", tags=["User Management"])



@router.post("/create-organization",status_code=status.HTTP_201_CREATED)
async def create_user(request: Request,org_data: NewOrgSchema, db: AsyncSession = Depends(get_db)):
    
        user_id = request.state.user.id
        result = await user_services.create_organization(org_data,user_id,db)
        
        return {
            "status": "success",
            "message": "Organization created successfully",
            "organization_id": result
        }


@router.post("/add-new-job",status_code=status.HTTP_201_CREATED)
async def add_new_job(request: Request,job_data: NewJobSchema, db: AsyncSession = Depends(get_db)):
    
        user_id = request.state.user.id
        
        # have to think how to pass org id
        # org_id = "0e001ed7-2aab-4e9b-a356-9e4c0179ac69"  
        org_id = None  
        
        job_id = await user_services.add_new_job(job_data,user_id,org_id,db)
        
        return {
            "status": "success",
            "message": "Job created successfully",
            "job_id": job_id
        }
        



@router.post("/extract-jd/{job_id}",status_code=status.HTTP_200_OK)
async def extract_jd(
    request: Request,
    job_id = str, 
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
    ):
    
    # user_id = request.state.user.id 

    result = await user_services.extract_jd(file,job_id,db)
    return {
        "status": "success",
        "message": "Rubric Generated successfully",
        "rubric": result
    }