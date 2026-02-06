from configs.postgress_db import get_sync_db,AsyncSession
from src.models import Resume, Application,BulkUploadBatches,Document,Rubric,Candidate,Score,Job
from src.utils.extract_pdf import extract_text_from_pdf_sync
from src.utils.manage_supabase_buckets import supabase_file_handler,save_file_from_path
import aiofiles
import os
from src.schemas.worker_task_schemas import ResumeParsingJobSchema
from src.schemas.user_schemas import ResumeDataSchema,BatchResumeDataSchema,ScoreOutputSchema,CandidateInfoSchema
from src.models.enums import ResumeStatus, DocumentProcessingStatus,BulkUploadStatus
from configs.env_config import SUPABASE_PUBLIC_URL
import os
from sqlalchemy import select,func,update,and_

from src.services.errors.base import DomainError 


from sqlalchemy import select, func
from sqlalchemy.orm import selectinload





async def get_applications(
    *,
    job_id: str,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession
):
    if page < 1:
        page = 1

    offset = (page - 1) * page_size

    # 1️⃣ total count
    total_result = await db.execute(
        select(func.count(Application.id))
        .where(Application.job_id == job_id)
    )
    total = total_result.scalar_one()

    # 2️⃣ fetch applications (NO resume join here)
    result = await db.execute(
        select(Application)
        .where(Application.job_id == job_id)
        .options(
            selectinload(Application.candidate),
            selectinload(Application.scores)  # we'll filter later
        )
        .order_by(Application.created_at.desc())
        .limit(page_size)
        .offset(offset)
    )

    applications = result.scalars().all()
    response = []

    for app in applications:


        # 🔹 active score only
        active_score = next(
            (s for s in app.scores if s.is_active),
            None
        )

        # 🔹 fetch ONLY current resume
        resume = None
        if app.current_resume_id:
            resume_result = await db.execute(
                select(Resume)
                .where(Resume.id == app.current_resume_id)
            )
            resume = resume_result.scalar_one_or_none()

        app_data = {
            "id": str(app.id),
            "current_round": app.current_round,
            "is_starred": app.is_starred,
            "denormalized_rank": app.denormalized_rank,
            "is_flagged": app.is_flagged,
            "offer_letter_url": app.offer_letter_url,
            "flag_reason": app.flag_reason,
            "tags": app.tags,
            "last_activity_at": (
                app.last_activity_at.isoformat()
                if app.last_activity_at else None
            ),
            "deleted_at": (
                app.deleted_at.isoformat()
                if app.deleted_at else None
            ),
            "status": app.status.value,
            "created_at": app.created_at.isoformat(),
            "updated_at": app.updated_at.isoformat(),
            "ai_analysis": app.ai_analysis,
        }

        # ✅ candidate (minimal)
        app_data["candidate"] = {
            "id": str(app.candidate.id),
            "full_name": app.candidate.full_name,
            "email": app.candidate.email,
            "phone": app.candidate.phone,
        } if app.candidate else None

        # ✅ resume (current only)
        app_data["resume"] = {
            "id": str(resume.id),
            "raw_file_url": f"{SUPABASE_PUBLIC_URL}/{resume.raw_file_url}",
            "status": resume.status.value,
            "page_count": resume.page_count,
            "uploaded_at": resume.uploaded_at.isoformat(),
        } if resume else None

        # ✅ active score only
        app_data["scores"] = [
            {
                "is_active": active_score.is_active,
                "overall_score": active_score.overall_score,
                "ai_confidence": active_score.ai_confidence,
                "created_at": active_score.created_at.isoformat(),
                "grounding_data": active_score.grounding_data,
                "is_overridden": active_score.is_overridden,
                "version": active_score.version,
                "is_latest": active_score.is_latest,
            }
        ] if active_score else []

        response.append(app_data)

    return {
        "applications": response,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size
        }
    }
