from fastapi import Depends, status,UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from models.organization_model import Organization
from models.user_model import User
from models.job_model import Job
from models.rubric_model import Rubric

from utils.security import hash_password,verify_password
from utils.jwt import create_jwt
from utils.security import hash_password
import random
from utils.send_otp import send_otp_email
from  configs.log_config import get_logger

from schemas.user_schemas import NewOrgSchema,NewJobSchema,ExtractedJDSchema

from services.errors.user_errors import OrganizationAlreadyExists,JDExtractionFailed,JobNotFound
from services.errors.auth_errors import UserNotFound


from models.enums import UserRole
from typing import Optional
from utils.extract_pdf import extract_text_from_pdf
from pipelines.generate_rubric import generate_rubric_from_jd



logger = get_logger(__name__)

from sqlalchemy import select

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



async def extract_jd(
    file: UploadFile,
    db: AsyncSession
) -> dict:
    try:

        # 1. Extract JD text
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
            job_metadata=data.job_data.metadata,
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



