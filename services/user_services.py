from fastapi import Depends, status,UploadFile,BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession


from models import Organization,User,Job,Rubric,Application

from  configs.log_config import get_logger

from schemas.user_schemas import NewOrgSchema,NewJobSchema
from schemas.job_schemas import JobOverviewResponse

from services.errors.user_errors import OrganizationAlreadyExists,JDExtractionFailed,JobNotFound,RubricNotFound
from services.errors.auth_errors import UserNotFound
from services.errors.base import DomainError


from models.enums import UserRole
from typing import Optional,List
from utils.extract_pdf import extract_text_from_pdf
from pipelines.generate_rubric import generate_rubric_from_jd
from utils.extract_validate_files import validate_and_extract_files

from utils.manage_supabase_buckets import supabase_file_handler
from utils.stage_uploaded_files import FileService
from workers.process_files import run_application_processing


logger = get_logger(__name__)

from sqlalchemy import select,func






async def get_user_by_id(user_id: str, db: AsyncSession) -> dict:
    try:
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise UserNotFound(message="User ID not found",status_code=status.HTTP_404_NOT_FOUND)

        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
        }

    except Exception:
        logger.exception(f"Error fetching user by ID: {user_id}")
        raise



async def create_organization(
    org_data: NewOrgSchema,
    creator_id: str,
    db: AsyncSession,
) -> str:
    try:
        # check org existence
        existing_org = await db.execute(
            select(Organization).where(Organization.email == org_data.email)
        )

        if existing_org.scalars().first():
            raise OrganizationAlreadyExists(status_code=status.HTTP_409_CONFLICT)

        # fetch user
        result = await db.execute(
            select(User).where(User.id == creator_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise UserNotFound(message="creator id not found",status_code=status.HTTP_404_NOT_FOUND)

        # create org
        new_org = Organization(
            name=org_data.name,
            email=org_data.email,
            address=org_data.address,
            created_by=creator_id,
        )
        db.add(new_org)

        user.organization = new_org  
        user.role = UserRole.ADMIN

        await db.commit()
        await db.refresh(new_org)

        return new_org.id

    except Exception:
        await db.rollback()
        raise


async def add_new_job(
    data: NewJobSchema,
    user_id: str,
    org_id: str | None,
    db: AsyncSession
):
    try:
        # 1. Create Job
        new_job = Job(
            created_by_id=user_id,
            title=data.job_data.title,
            description=data.job_data.description,
            location=data.job_data.location,
            target_headcount=data.job_data.target_headcount,
            voice_ai_enabled=data.job_data.voice_ai_enabled,
            manual_rounds_count=data.job_data.manual_rounds_count,
            is_confidential=data.job_data.is_confidential,
        )

        # 2. Attach organization if provided
        if org_id:
            result = await db.execute(
                select(Organization).where(Organization.id == org_id)
            )
            organization = result.scalar_one_or_none()

            if not organization:
                raise ValueError("Organization not found")

            new_job.organization = organization

        # 3. Persist job to get ID
        db.add(new_job)
        await db.flush()  # ✅ ID is now generated

        job_id = new_job.id

        # 4. Determine rubric version (for safety / future updates)
        result = await db.execute(
            select(Rubric).where(Rubric.job_id == job_id)
        )
        existing_rubrics = result.scalars().all()

        new_version = 1
        for rubric in existing_rubrics:
            rubric.is_active = False
            new_version = max(new_version, rubric.version + 1)

        # 5. Create rubric
        new_rubric = Rubric(
            version=new_version,
            threshold_score=data.threshold_score,
            criteria=data.criteria.model_dump(),
            job_id=job_id,
            is_active=True,
        )

        db.add(new_rubric)

        # 6. Commit transaction
        await db.commit()
        await db.refresh(new_job)

        return new_job.id

    except Exception as e:
        await db.rollback()
        logger.exception("Error adding job")
        raise

    
async def get_jobs(user_id : str,db: AsyncSession, organization_id: Optional[str] = None) -> list[dict]:
    try:
        query = select(Job)
        
        if organization_id:
            query = query.where(Job.organization_id == organization_id ).order_by(Job.created_at.desc())
        else:
            query = query.where(Job.created_by_id == user_id, Job.organization_id == None).order_by(Job.created_at.desc())
            
        
        
        result = await db.execute(query)
        jobs = result.scalars().all()
        
        job_list = []
        for job in jobs:
            job_list.append({
                "id": job.id,
                "title": job.title,
                "location": job.location,
                "status": job.status.value,
                "target_headcount": job.target_headcount,
                "jd_url":"null",
                "created_at": job.created_at.isoformat(),
            })
        
        return job_list
    
    except Exception as e:
        logger.error(f"Error fetching jobs: {e}")
        raise


async def extract_jd(
    file: UploadFile,
    db: AsyncSession
) -> dict:
    try:
    
        jd_input = await extract_text_from_pdf(file)

        if len(jd_input) < 100:
            raise JDExtractionFailed(
                message="Extracted JD content is too short",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # 3. Generate rubric via LLM
        rubric_data = await generate_rubric_from_jd(jd_input)
        rubric_dict = rubric_data.model_dump()

        
        # 7. Return clean response
        return {
            "job_data": rubric_dict["job_data"],
            "threshold_score": rubric_dict["threshold_score"],
            "criteria": {
                "mandatory_criteria":rubric_dict["mandatory_criteria"],
                "screening_criteria":rubric_dict["screening_criteria"]
                }
        }

    except Exception as e:
        logger.exception(f"Error extracting JD: {e}")
        await db.rollback()
        raise





async def get_job_overview(
    job_id: str,
    db: AsyncSession,
    organization_id: Optional[str] = None
) -> JobOverviewResponse:
    # ---------- Job ----------
    job_query = select(Job).where(Job.id == job_id)

    if organization_id:
        job_query = job_query.where(Job.organization_id == organization_id)
    else:
        job_query = job_query.where(Job.organization_id.is_(None))

    job = (await db.execute(job_query)).scalar_one_or_none()
    if not job:
        raise JobNotFound(status_code=404)

    # ---------- Active Rubric (Criteria) ----------
    rubric_stmt = (
        select(Rubric)
        .where(
            Rubric.job_id == job_id,
            Rubric.is_active.is_(True)
        )
    )
    rubric = (await db.execute(rubric_stmt)).scalar_one_or_none()
    if not rubric:
        raise RubricNotFound(
            message="Active rubric not found",
            status_code=404
        )

    # ---------- Dashboard Analytics ----------
    analytics_stmt = (
        select(
            Application.status,
            func.count(Application.id)
        )
        .where(Application.job_id == job_id)
        .group_by(Application.status)
    )

    analytics_result = await db.execute(analytics_stmt)
    analytics = {
        status.value: count
        for status, count in analytics_result.all()
    }

    total_applications = sum(analytics.values())

    # ---------- Response ----------
    return {
        "job": {
            "id": job.id,
            "title": job.title,
            "status": job.status,
            "description": job.description,
            "created_at": job.created_at,
            "salary": job.salary,
            "location": job.location,
            "target_headcount": job.target_headcount,
        },
        "dashboard": {
            "total_applications": total_applications,
            "by_status": analytics,
        },
        "criteria": {
            "rubric_id": rubric.id,
            "version": rubric.version,
            "threshold_score": rubric.threshold_score,
            "criteria": rubric.criteria,
        },
        "settings": {
            "voice_ai_enabled": job.voice_ai_enabled,
            "manual_rounds_count": job.manual_rounds_count,
            "is_confidential": job.is_confidential,
            "job_metadata": job.job_metadata,
            "closing_reason": job.closing_reason,
        }
    }



async def process_applications(
    job_id: str,
    files: List[UploadFile],
    db: AsyncSession,
    background_tasks: BackgroundTasks,
    organization_id: Optional[str] = None,
) -> dict:

    # 1. Fetch job
    job_query = select(Job).where(Job.id == job_id)

    if organization_id:
        job_query = job_query.where(Job.organization_id == organization_id)
    else:
        job_query = job_query.where(Job.organization_id.is_(None))

    job = (await db.execute(job_query)).scalar_one_or_none()

    if not job:
        raise JobNotFound(status_code=404)

    # 2. Prevent duplicate processing
    # if job.active_application_processing_job_id:
    #     raise DomainError(
    #         message="An active application processing job already exists for this job.",
    #         status_code=status.HTTP_409_CONFLICT
    #     )

    # 3. Validate files
    resumes = await validate_and_extract_files(files)

    # 4. Stage files to storage
    dir_path = await FileService.stage_uploaded_files(
        job_id=job_id,
        files=resumes,
    )

    # 5. Create processing job
    # processing_job = ApplicationProcessingJob(
    #     job_id=job_id,
    #     files_source=dir_path,
    #     organization_id=organization_id,
    # )

    # db.add(processing_job)
    # await db.commit()
    # await db.refresh(processing_job)

    # # 6. Attach processing job to Job
    # job.active_application_processing_job_id = processing_job.id
    
    # await db.commit()

    # 7. Trigger background worker (IMPORTANT)

    background_tasks.add_task(
        run_application_processing,
        # processing_job.id
        dir_path
    )

    return {
        # "processing_job_id": processing_job.id,
        "directory_path": dir_path,
        "status": "queued"
    }
