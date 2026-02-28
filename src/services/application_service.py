import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from  configs.log_config import get_logger
from  configs.env_config import FRONTEND_URL
from src.services.errors.base import DomainError
from src.repositories.application_repository import ApplicationRepository
from src.models.enums import ApplicationStatus
from src.models.interview_models.interview_rounds_configs import Interview_Round_Configs
from datetime import datetime, timezone, timedelta
from src.schemas.candidate_schemas import CandidateCreateSchema
from src.repositories.candidiate_repository import CandidateRepository
from src.repositories.interview_respositories.panelist_repository import PanelistRepository
from src.repositories.interview_respositories.interview_repository import InterviewRepository
from src.services.email_services.panel.panel_email_service import PanelEmailService,panel_email_service
from src.repositories.interview_respositories.interview_round_configs_repository import InterviewRoundConfigsRepository
from src.repositories.interview_respositories.interview_event_repository import InterviewEventRepository
from src.utils.jwt import JWTService,jwt_service
from src.dtos.interviews_dtos.panel_dto import CreatePanelDTO


class ApplicationService:
    def __init__(self,
        application_repository:ApplicationRepository,
        candidate_repository:CandidateRepository,
        interview_repository:InterviewRepository,
        panelist_repository:PanelistRepository,
        interview_round_config_repository:InterviewRoundConfigsRepository,
        interview_event_repository:InterviewEventRepository,
        db: AsyncSession):
        
        
        self.db = db
        self.application_repository = application_repository
        self.candidate_repository = candidate_repository
        self.interview_repository = interview_repository
        self.panelist_repository = panelist_repository
        self.interview_round_config_repository = interview_round_config_repository
        self.interview_event_repository = interview_event_repository
        self.panel_email_service : PanelEmailService = panel_email_service
        self.jwt_service : JWTService = jwt_service
        
        self.frontend_url = FRONTEND_URL
        

        self.logger = get_logger("APPLICATION_SERVICE")
        
    
    def _check_application_movable_to_new_round(self,application,round_config,round_number):
        if not round_config.panelists:
            raise DomainError(message="No panelists assigned for this round config,Please assign panelists first", status_code=404) 
        
        if not round_config.start_date or not round_config.end_date:
            raise DomainError(message="Start date and end date must be defined for the round config", status_code=400)
        
        if round_config.start_date < datetime.now(timezone.utc):
            raise DomainError(message="Round config start date must be in the future to move application to this round", status_code=400)
        
        if round_config.end_date < datetime.now(timezone.utc):
            raise DomainError(message="Round config end date must be in the future to move application to this round", status_code=400)
            
        if application.current_round and round_number != application.current_round + 1:
            raise DomainError(message="Application can only be moved to the next round sequentially", status_code=400)
        
        if application.current_round and round_number == application.current_round:
            raise DomainError(message="Application is already in this round", status_code=400)
        
        if application.current_round and round_number < application.current_round:
            raise DomainError(message="Cannot move application back to a previous round", status_code=400)
        
         
      

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




    async def attach_candidate_to_application(self,application_id: str,candidate_data: CandidateCreateSchema,org_id: str | None = None):
        """ This method is used to attach a new candidate to application when candidate info is filled for the first time in application flow."""
        try:
            application = await self.application_repository.get_application_by_id(
                application_id
            )

            if not application or application.deleted_at is not None:
                raise DomainError("Application not found", 404)
            
            if application.candidate_id is not None:
                raise DomainError("Candidate already attached to this application,Edit using candidateId", 400)
            
            
            # TODO: Personal mode (org_id=None) currently shares candidate namespace globally.
            # TODO: Add owner_user_id to isolate candidates per user and update uniqueness constraints.
            if candidate_data.email and org_id is not None:
                existing_candidate = await self.candidate_repository.get_candidate_by_email(candidate_data.email,org_id )
                if existing_candidate:
                    raise DomainError("Candidate with this email already exists", 400)
                
            if candidate_data.phone and org_id is not None:
                existing_candidate = await self.candidate_repository.get_candidate_by_phone(candidate_data.phone,org_id)
                if existing_candidate:
                    raise DomainError("Candidate with this phone number already exists", 400)
            
            
            # 1️⃣ Create candidate
            candidate = await self.candidate_repository.create_candidate(
                candidate_data,
                org_id
            )
            
            
            application.candidate_id = candidate.id
            candidate.total_applications += 1
            await self.application_repository.commit()
            return application

        except:
            await self.application_repository.rollback()
            raise

 
    async def change_application_status(self,application_id:str,new_status:ApplicationStatus):
        try:
            application = await self.application_repository.get_application_by_id(application_id=application_id)
            if not application:
                raise DomainError(message="Application not found", status_code=404)
            application.status = new_status
            await self.db.commit()
            return {
                "application_id": str(application_id),
                "new_status": new_status.value
            }
        except DomainError:
            raise
        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Failed to change application status for application_id={application_id} to new_status={new_status}: {str(e)}")
            raise DomainError(message="Failed to change application status", status_code=500)
    
    async def delete_application(self,application_id:str):
        try:
            application = await self.application_repository.get_application_by_id(application_id=application_id)
            
            if not application:
                raise DomainError(message="Application not found", status_code=404)
            
            application.deleted_at = datetime.now(timezone.utc)
            application.last_activity_at = datetime.now(timezone.utc)
            
            await self.db.commit()
            return {
                "application_id": str(application_id),
                "deleted_at": application.deleted_at.isoformat()
            }
        except DomainError:
            raise
        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Failed to delete application for application_id={application_id}: {str(e)}")
            raise DomainError(message="Failed to delete application", status_code=500)
    
    async def flag_application(self,application_id:str,flag_reason:str):
        try:
            application = await self.application_repository.get_application_by_id(application_id=application_id)
            
            if not application:
                raise DomainError(message="Application not found", status_code=404)
            
            application.is_flagged = True
            application.flag_reason = flag_reason
            application.last_activity_at = datetime.now(timezone.utc)
            
            await self.db.commit()
            return True
        except DomainError:
            raise
        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Failed to flag application for application_id={application_id}: {str(e)}")
            raise DomainError(message="Failed to flag application", status_code=500)
        

                
    async def unflag_application(self,application_id:str,org_id:str=None):
        try:
            application = await self.application_repository.get_application_by_id(application_id=application_id)
            
            if not application or application.deleted_at is not None:
                raise DomainError(message="Application not found", status_code=404)
            
            if application.is_flagged == False:
                raise DomainError(message="Application is not flagged", status_code=400)
            
            
            application.is_flagged = False
            application.flag_reason = None
            application.last_activity_at = datetime.now(timezone.utc)
            
            await self.db.commit()
            return True
        except DomainError:
            raise
        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Failed to unflag application for application_id={application_id}: {str(e)}")
            raise DomainError(message="Failed to unflag application", status_code=500)


    
    async def star_application(self,application_id:str,org_id:str=None):
        try:
            application = await self.application_repository.get_application_by_id(application_id=application_id)
            
            if not application or application.deleted_at is not None:
                raise DomainError(message="Application not found", status_code=404)
            
            if application.is_starred == True:
                raise DomainError(message="Application is already starred", status_code=400)
            
            application.is_starred = True
            application.last_activity_at = datetime.now(timezone.utc)
            
            await self.db.commit()
            return True
        except DomainError:
            raise
        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Failed to star application for application_id={application_id}: {str(e)}")
            raise DomainError(message="Failed to star application", status_code=500)


                
    async def unstar_application(self,application_id:str,org_id:str=None):
        try:
            application = await self.application_repository.get_application_by_id(application_id=application_id)
            
            if not application  or application.deleted_at is not None:
                raise DomainError(message="Application not found", status_code=404)

            if application.is_starred == False:
                raise DomainError(message="Application is not starred", status_code=400)
            
            application.is_starred = False
            application.last_activity_at = datetime.now(timezone.utc)
            
            await self.db.commit()
            return True
        except DomainError:
            raise
        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Failed to unstar application for application_id={application_id}: {str(e)}")
            raise DomainError(message="Failed to unstar application", status_code=500)
        
        
        
        
    async def move_to_round(self,application_id:str,job_id:str,round_number:int):
        try:
            application = await self.application_repository.get_application_by_id(application_id=application_id)
            
            if not application:
                raise DomainError(message="Application not found", status_code=404)
            
            
            round_config = await self.interview_round_config_repository.get_interview_round_config_by_job_and_round(job_id=job_id, round_number=round_number)
            
            if not round_config:
                raise DomainError(message="There is no round config for this round,Add config first", status_code=404)
            
            
            self._check_application_movable_to_new_round(application,round_config,round_number)
                  
            new_interview = await self.interview_repository.create_interview(
                round_config_id=round_config.id,
                application_id=application_id,
                round_number=round_number
            ) 
            
            
            
            if round_config.slots_available and round_config.candidate_slot_booking_link:
                # send current availability email to candidate with booking link
                await self.interview_event_repository.create_interview_event(
                    interview_id=new_interview.id,
                    event_type="SLOT_BOOKING_LINK_SENT",
                    
                )
                self.logger.info("Round Available slots: Sending slot booking link to candidate for interview_id={new_interview.id}")
                pass
            
            
            else:   
                # Ask Panelist for new slots 
                pannelist_data = []
                remaining_seconds = (round_config.end_date - datetime.now(timezone.utc)).total_seconds()

                if remaining_seconds <= 0:
                    raise DomainError("Round already expired")

                token_expiry_in_min = max(1, int(remaining_seconds // 60))
                
                for panel in round_config.panelists:
                    if panel.get("email") is None:
                        self.logger.warning(f"Panelist {panel.get('name')} does not have an email, skipping slot availability email")
                        continue  # Skip panelists with missing email 
                    
                    pannelist_data.append(
                        CreatePanelDTO(
                            panelist_name=panel.get("name"),
                            panelist_email=panel.get("email"),
                            token_expires_at=datetime.now(timezone.utc) + timedelta(minutes=token_expiry_in_min),
                            availability_token=self.jwt_service.create_panelist_availability_token(
                                interview_id=str(new_interview.id),
                                panelist_email=panel.get("email"),
                                round_config_id=str(round_config.id),
                                expiration_minutes=token_expiry_in_min
                            ),
                            
                        )
                    )

                    
                panelists = await self.panelist_repository.add_panelists(
                    round_config_id=str(round_config.id),
                    interview_id=str(new_interview.id),
                    panel_data_list=pannelist_data
                )
                
                if not panelists:
                    raise DomainError(message="Failed to add panelists for this interview round,Please check panelist data and try again", status_code=500)

                await self.db.commit()
                
                 
                # TODO: Enque email sending task if many panelists to avoid delays in response
                await asyncio.gather(*[
                    self.panel_email_service.send_slot_availability_email(
                        panelist_email=panelist.panelist_email,
                        panelist_name=panelist.panelist_name,
                        interview_round_title=round_config.title,
                        form_link=f"{self.frontend_url}/panelist/availability?token={panelist.availability_token}",
                    )
                    for panelist in panelists
                ])
                
                    
                
            return "Application moved to round successfully"
        except Exception as e:
            self.logger.error(f"Failed to move application to round for application_id={application_id} to round_number={round_number}: {str(e)}")
            await self.db.rollback()
            raise 