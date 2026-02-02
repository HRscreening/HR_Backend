from fastapi import APIRouter,HTTPException,Depends,Request,status,File, UploadFile,BackgroundTasks
from configs.postgress_db import get_db
from sqlalchemy.ext.asyncio import AsyncSession


from schemas.user_schemas import NewJobSchema
from services import user_services
from  typing import Optional,List
from uuid import UUID
from schemas.job_schemas import JobOverviewResponse



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




@router.get(
    "/get-job/{job_id}",
    response_model=JobOverviewResponse,
    status_code=status.HTTP_200_OK,
)
async def get_job_overview_api(
    job_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ctx = request.state.context

    if ctx.type == "org":
        if not ctx.org_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization context missing org_id",
            )

        return await user_services.get_job_overview(
            job_id=str(job_id),
            db=db,
            organization_id=ctx.org_id,
        )

    if ctx.type == "personal":
        return await user_services.get_job_overview(
            job_id=str(job_id),
            db=db,
            organization_id=None,
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid context type",
    )



@router.post("/process-applications/{job_id}",status_code=status.HTTP_202_ACCEPTED)
async def process_applications(request: Request,job_id: UUID,
                               background_tasks: BackgroundTasks, 
                               db: AsyncSession = Depends(get_db),
                               files: List[UploadFile] = File(...)):
    
        user_id = request.state.user.id
        ctx_type = request.state.context.type
        

        
        if ctx_type == "org":
            msg = await user_services.process_applications(
                job_id=str(job_id),
                db=db,
                background_tasks=background_tasks,
                files=files,
                organization_id=request.state.context.org_id,
            )
            
        elif ctx_type == "personal":
            msg = await user_services.process_applications(
                job_id=str(job_id),
                db=db,
                background_tasks=background_tasks,
                files=files,
                organization_id=None,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid context type",
            )
        
        if not msg:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to start application processing",
            )
        
        return {
            "status": "success",
            "message": msg,
        }