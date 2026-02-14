from fastapi import APIRouter,HTTPException,Depends,Request,status,File, UploadFile,BackgroundTasks,Query
from configs.postgress_db import get_db
from sqlalchemy.ext.asyncio import AsyncSession


from src.schemas.user_schemas import NewJobSchema
# from src.services import user_services
from  typing import Optional,List
from uuid import UUID
from src.schemas.job_schemas import JobOverviewResponse
from src.services.resume_services import score_resumes_service
from src.dependency import get_job_service,JobService
from src.utils.file_manager import fileManager


router = APIRouter(prefix="/api/jobs", tags=["Job Management"])




@router.post("/add-new-job",status_code=status.HTTP_201_CREATED)
async def add_new_job(request: Request,data: NewJobSchema, job_service: JobService = Depends(get_job_service)):
    
        user_id = request.state.user.id
        ctx_type = request.state.context.type
        
        if ctx_type == "org":
            job_id = await job_service.add_new_job(
                data=data,
                user_id=user_id,
                org_id=request.state.context.org_id,
            )

        elif ctx_type == "personal":
            job_id = await job_service.add_new_job(
                data=data,
                user_id=user_id,
                org_id=None,
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
async def get_jobs(request: Request,job_service: JobService = Depends(get_job_service)):
    
        user_id = request.state.user.id
        ctx_type = request.state.context.type
        
        
        if ctx_type == "org":
            jobs = await job_service.get_jobs(user_id,organization_id=request.state.context.org_id)
        elif ctx_type == "personal":
            jobs = await job_service.get_jobs(user_id,None)
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
    job_service: JobService = Depends(get_job_service)
    ):

    result = await job_service.extract_jd(file)
    return result




@router.get(
    "/get-job/{job_id}",
    response_model=JobOverviewResponse,
    status_code=status.HTTP_200_OK,
)
async def get_job_overview_api(
    job_id: UUID,
    request: Request,
    job_service: JobService = Depends(get_job_service)
):
    ctx = request.state.context

    if ctx.type == "org":
        if not ctx.org_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization context missing org_id",
            )

        return await job_service.get_job_overview(
            job_id=str(job_id),
            organization_id=ctx.org_id,
        )

    if ctx.type == "personal":
        return await job_service.get_job_overview(
            job_id=str(job_id),
            organization_id=None,
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid context type",
    )



@router.post("/process-applications-zip-file/{job_id}",status_code=status.HTTP_202_ACCEPTED)
async def process_applications(
    request: Request,
    job_id: UUID,
    background_tasks: BackgroundTasks,
    zip_file: UploadFile = File(...),
    job_service: JobService = Depends(get_job_service)
):

    
        user_id = request.state.user.id
        ctx_type = request.state.context.type
        
        files = [zip_file]  # Wrap the single file in a list to reuse the validation function
        extracted_files = await fileManager.validate_and_extract(files)
        
        if ctx_type == "org":
            msg = await job_service.process_applications(
                job_id=str(job_id),
                background_tasks=background_tasks,
                user_id=str(user_id),
                files=extracted_files,
                organization_id=request.state.context.org_id,
            )
            
        elif ctx_type == "personal":
            msg = await job_service.process_applications(
                job_id=str(job_id),
                background_tasks=background_tasks,
                user_id=str(user_id),
                files=extracted_files,
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
        


# !INTERNAL - For testing only, not part of public API
@router.post("/process-resumes/{job_id}",status_code=status.HTTP_202_ACCEPTED)
async def process_applications(request: Request,job_id: UUID,
                               db: AsyncSession = Depends(get_db)):
    
        user_id = request.state.user.id
        ctx_type = request.state.context.type
        
        if ctx_type == "org":
            msg = await score_resumes_service(
                job_id=str(job_id),
                db=db,
            )
        elif ctx_type == "personal":
            msg = await score_resumes_service(
                job_id=str(job_id),
                db=db,
            )
        
        return msg
    
    
@router.get("/get-applications/{job_id}", status_code=status.HTTP_200_OK)
async def get_application(
    job_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    job_service: JobService = Depends(get_job_service)
):
    applications = await job_service.get_applications(
        job_id=str(job_id),
        page=page,
        page_size=page_size,
    )

    return applications
