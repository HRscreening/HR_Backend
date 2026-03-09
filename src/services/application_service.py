from sqlalchemy.ext.asyncio import AsyncSession
from  configs.log_config import get_logger
from src.services.errors.base import DomainError
from src.repositories.application_repository import ApplicationRepository
from src.models.enums import ApplicationStatus
from datetime import datetime, timezone


class ApplicationService:
    def __init__(self, application_repository:ApplicationRepository, db: AsyncSession):
        self.db = db
        self.application_repository = application_repository
        self.logger = get_logger("APPLICATION_SERVICE")       
    
    async def get_applications_of_job(
        self,
        job_id: str,
        page: int = 1,
        page_size: int = 20,
    ):
        if page < 1:
            page = 1

        offset = (page - 1) * page_size

    
        total = await self.job_repository.get_total_applications_count(job_id=job_id)
        active_rubric = await self.job_repository.get_active_rubric(job_id=job_id)
        
        if not active_rubric:
            raise DomainError( message="Active rubric not found for the job", status_code=404 )
        
        applications = await self.job_repository.get_applications_of_job(job_id=job_id, current_rubric_id=active_rubric.id, page_size=page_size, offset=offset )
        
        response = []

        for app,score in applications:
            # 🔹 active score only
            active_score =  score if score else None
            # 🔹 fetch ONLY current resume
            resume = app.resume if app.resume else None

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
                "raw_file_url": f"{self.PUBLIC_URL}/{resume.raw_file_url}",
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

    async def change_application_status(self,application_id:str,new_status:ApplicationStatus):
        try:
            application = await self.application_repository.get_application_by_id(application_id=application_id)
            if not application:
                raise DomainError(message="Application not found", status_code=404)
            application.status = new_status
            await self.application_repository.db.commit()
            return {
                "application_id": str(application_id),
                "new_status": new_status.value
            }
        except Exception as e:
            self.logger.error(f"Failed to change application status for application_id={application_id} to new_status={new_status}: {str(e)}")
            raise DomainError(message="Failed to change application status", status_code=500)
    
    async def delete_application(self, application_id: str, job_id: str):
        try:
            application = await self.application_repository.get_application_by_id(application_id=application_id)

            if not application:
                raise DomainError(message="Application not found", status_code=404)

            if str(application.job_id) != str(job_id):
                raise DomainError(message="Application does not belong to this job", status_code=403)

            application.deleted_at = datetime.now(timezone.utc)
            application.last_activity_at = datetime.now(timezone.utc)
            
            await self.application_repository.commit()
            return {
                "application_id": str(application_id),
                "deleted_at": application.deleted_at.isoformat()
            }
        except Exception as e:
            self.logger.error(f"Failed to delete application for application_id={application_id}: {str(e)}")
            await self.application_repository.rollback()
            raise DomainError(message="Failed to delete application", status_code=500)
    
    async def flag_application(self,application_id:str,flag_reason:str):
        try:
            application = await self.application_repository.get_application_by_id(application_id=application_id)
            
            if not application:
                raise DomainError(message="Application not found", status_code=404)
            
            application.is_flagged = True
            application.flag_reason = flag_reason
            application.last_activity_at = datetime.now(timezone.utc)
            
            await self.application_repository.commit()
            return True
        except Exception as e:
            self.logger.error(f"Failed to flag application for application_id={application_id}: {str(e)}")
            await self.application_repository.rollback()
            raise DomainError(message="Failed to flag application", status_code=500)