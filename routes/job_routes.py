from fastapi import APIRouter,HTTPException,Depends,Request,Query,status,File, UploadFile
from fastapi.responses import JSONResponse
from configs.postgress_db import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from middlewares.verify_user import auth_required
from utils.verify_token import verify_token

from schemas.user_schemas import NewOrgSchema,NewJobSchema,ExtractedJDSchema
from services import user_services
# from services.errors.auth_errors import EmailAlreadyExists
from  typing import Optional

router = APIRouter(prefix="/api/jobs", tags=["Job Management"])




@router.post("/add-new-job",status_code=status.HTTP_201_CREATED)
async def add_new_job(request: Request,data: NewJobSchema, db: AsyncSession = Depends(get_db)):
    
        user_id = request.state.user.id
        ctx_type = request.state.context.type
        
        if ctx_type == "org":
            job_id = await user_services.add_new_job(
                data=data,
                user_id=user_id,
                org_id=request.state.context.org_id,
                db=db,
            )

        elif ctx_type == "personal":
            job_id = await user_services.add_new_job(
                data=data,
                user_id=user_id,
                org_id=None,
                db=db,
            )

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid context type",
            )
        
        return {
            "status": "success",
            "message": "Job created successfully",
            "job_id": job_id
        }
       
        
@router.get("/get-jobs",status_code=status.HTTP_200_OK)
async def get_jobs(request: Request,db: AsyncSession = Depends(get_db)):
    
        user_id = request.state.user.id
        ctx_type = request.state.context.type
        
        
        if ctx_type == "org":
            jobs = await user_services.get_jobs(user_id,db,organization_id=request.state.context.org_id)
        elif ctx_type == "personal":
            jobs = await user_services.get_jobs(user_id,db,None)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid context type",
            )
        
        return {
            "status": "success",
            "jobs": jobs
        }


@router.post("/upload-jd",status_code=status.HTTP_200_OK)
async def extract_jd(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
    ):
    
    # user_id = request.state.user.id 

    result = await user_services.extract_jd(file,db)
    return result