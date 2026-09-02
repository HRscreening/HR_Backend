from sqlalchemy.ext.asyncio import AsyncSession
from  configs.log_config import get_logger
from src.services.errors.base import DomainError
from src.repositories.application_repository import ApplicationRepository
from src.models.enums import ApplicationStatus
from datetime import datetime, timezone
from src.models.enums import InterviewStatus
from datetime import timedelta
from src.repositories.application_repository import ApplicationRepository
from src.models.enums import ApplicationStatus, InterviewStatus,InterviewEventActor,InterviewEventType
from datetime import datetime, timezone, timedelta
from src.schemas.candidate_schemas import CandidateCreateSchema
from src.repositories.candidiate_repository import CandidateRepository

from src.modules.interviews.repositories.panelist_repository import PanelistRepository
from src.modules.interviews.repositories.interview_repository import InterviewRepository
from src.modules.interviews.repositories.interview_round_configs_repository import InterviewRoundConfigsRepository
from src.modules.interviews.repositories.interview_event_repository import InterviewEventRepository
from src.repositories.job_repository import JobRepository

from src.modules.notifications.channels.email.services import CandidateEmailService, PanelEmailService
from configs.env_config import FRONTEND_URL
from src.dtos.notification_dto import Email_Template_Keys
from src.modules.reminders.reminder_dtos import CreateReminderDTO
from src.dtos.emails.panel_dto import PanelistReminderAvailabilityData,PanelistInterviewReminderData,PanelistBookingData,AvailableSlotsData,ThankYouPanelistData,PanelistSlotReleasedData,PanelistMeetingRescheduledData
from src.dtos.emails.candidate_dto import CandidateBookingLinkReminderData,CandidateInterviewReminderData,CandidateBookingLinkData,CandidateBookingConfirmationData,CandidateRescheduleNewSlotsData,CandidateShortlistedData
from src.modules.reminders.model.reminder_enum import ReminderType, RecipientType, EntityType
from datetime import timedelta
from src.dtos.job_settings_dto import ReminderSettingsDTO,ReschedulingSettingsDTO
from src.modules.reminders.reminder_repository import ReminderRepository
from workers_async.producers.email_tasks_producer import EmailProducer,EnqueueReminderPayload
from src.utils.jwt import JWTService
import asyncio



        
class ApplicationService:
    def __init__(self, 
        application_repository:ApplicationRepository,
        candidate_repository:CandidateRepository,
        interview_repository:InterviewRepository,
        panelist_repository:PanelistRepository,
        interview_round_config_repository:InterviewRoundConfigsRepository,
        interview_event_repository:InterviewEventRepository,
        job_repository:JobRepository,
        panel_email_service:PanelEmailService,
        candidate_email_service:CandidateEmailService,
        reminder_repository: ReminderRepository,
        email_producer: EmailProducer,
        db: AsyncSession):
        
        
        self.db = db
        self.application_repository = application_repository
        self.candidate_repository = candidate_repository
        self.interview_repository = interview_repository
        self.panelist_repository = panelist_repository
        self.interview_round_config_repository = interview_round_config_repository
        self.interview_event_repository = interview_event_repository
        self.job_repository : JobRepository = job_repository
        self.panel_email_service : PanelEmailService = panel_email_service
        self.candidate_email_service : CandidateEmailService = candidate_email_service
        self.jwt_service : JWTService = JWTService()
        self.reminder_repository = reminder_repository
        self.email_producer = email_producer
        
        self.frontend_url = FRONTEND_URL
        
        self.logger = get_logger("APPLICATION_SERVICE")  
        
        
            
    
    def _check_application_movable_to_new_round(self,application,round_config,round_number):

        if not round_config.start_date or not round_config.end_date:
            raise DomainError(message="Start date and end date must be defined for the round config", status_code=400)
        
        # TODO: Decide if we want to allow moving application to a round whose start date is in the past but end date is in the future,
        # as sometimes interview rounds can be created with start date in the past by mistake but still want to use them if end date is in the future.
        # For now, we will allow it but log a warning.

        # if round_config.start_date < datetime.now(timezone.utc):
        #     raise DomainError(message="Round config start date must be in the future to move application to this round", status_code=400)
        
        if round_config.end_date < datetime.now(timezone.utc):
            raise DomainError(message="Round config end date must be in the future to move application to this round", status_code=400)
            
        if application.current_round and round_number != application.current_round + 1:
            raise DomainError(message="Application can only be moved to the next round sequentially", status_code=400)
        
        if application.current_round and round_number == application.current_round:
            raise DomainError(message="Application is already in this round", status_code=400)
        
        if application.current_round and round_number < application.current_round:
            raise DomainError(message="Cannot move application back to a previous round", status_code=400)
        
    def _create_form_reminder_payload_for_panelist(self,requested_panelist,config, panelist_reminder_settings: ReminderSettingsDTO) -> list[CreateReminderDTO]:
        reminders_payload = []
        for panelist in requested_panelist:
            for reminder_sec in set(panelist_reminder_settings.form_reminder_sec):
                reminders_payload.append(CreateReminderDTO(
                    entity_id=str(config.id),
                    entity_type=EntityType.INTERVIEW,
                    payload=PanelistReminderAvailabilityData(
                        panelist_email=panelist.email,
                        panelist_name=panelist.name,
                        interview_round_title=config.title,
                        form_link=f"{self.frontend_url}/panelist/availability?token={panelist.availability_token}"
                    ).model_dump(),
                    recipient_id=str(panelist.id),
                    recipient_type=RecipientType.PANELIST,
                    reminder_type=ReminderType.BOOKING_LINK,
                    template_key=Email_Template_Keys.FORM_REMINDER,
                    next_run_at= datetime.now(timezone.utc) + timedelta(seconds=reminder_sec)  #! for now doing in minutes, change to hours later       
                ))
                
        return reminders_payload
    
    def _create_booking_reminder_payload_candidate(self, candidate, round_config, candidate_reminder_settings:ReminderSettingsDTO,booking_link,application_id) -> list[CreateReminderDTO]:
        reminders_payload = []
        if candidate_reminder_settings and candidate_reminder_settings.enabled and candidate_reminder_settings.form_reminder_sec:
            for reminder_sec in candidate_reminder_settings.form_reminder_sec:
                reminders_payload.append(CreateReminderDTO(
                    entity_id=str(round_config.id),
                    entity_type=EntityType.INTERVIEW,
                    payload=CandidateBookingLinkReminderData(
                        candidate_email=candidate.email,
                        candidate_name=candidate.full_name or candidate.email,
                        interview_round_title=round_config.title,
                        booking_link=booking_link
                    ).model_dump(),
                    recipient_id=str(application_id),
                    recipient_type=RecipientType.CANDIDATE,
                    reminder_type=ReminderType.BOOKING_LINK,
                    template_key=Email_Template_Keys.Candidate_BOOKING_LINK_REMINDER,
                    next_run_at= datetime.now(timezone.utc) + timedelta(seconds=reminder_sec)  #! for now doing in minutes, change to hours later       
                ))
            return reminders_payload
    
    async def attach_new_candidate_to_application(self,application_id:str,candidate_info: CandidateCreateSchema,org_id: str | None = None):
        """ This method is used when we want to attach a new candidate to an existing application, it will create a new candidate and attach it to the application, this is used in the flow when user want to edit candidate info through application flow and candidate with given email or phone number is not found, so we create a new candidate and attach it to the application, this is different from create_candidate method in candidate service which is used to create candidate without attaching it to any application and is called from candidate routes directly."""
        try:
            application = await self.application_repository.get_application_by_id(application_id) 
            
            if not application:
                raise DomainError(message="Application not found", status_code=404)
            
            candidate = await self.candidate_repository.create_candidate(
                candidate_info, org_id
            )   
            
            application.candidate_id = candidate.id

            await self.db.commit()

            return candidate.id

        except DomainError:
            await self.candidate_repository.rollback()
            raise

        except Exception as e:
            await self.candidate_repository.rollback()
            self.logger.error(f"Failed to create candidate: {str(e)}")
            raise DomainError(message="Failed to create candidate", status_code=500)
    
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
                "current_title": app.candidate.current_title,
                "current_company": app.candidate.current_company,
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
            
            job = await self.job_repository.get_job_by_id(str(application.job_id))
            if not job:
                raise DomainError(message="Job not found for this application", status_code=404)
            
            if application.current_round != 0:
                raise DomainError(message="Cannot change status of application which is already in interview rounds, status can only be changed when application is in initial round", status_code=400)
            
            candidate = await self.candidate_repository.get_candidate_by_id(str(application.candidate_id)) if application.candidate_id else None
            if not candidate:
                raise DomainError(message="Candidate not found for this application, cannot change status without candidate information, please first add candidate information to the application", status_code=404)
            
            application.status = new_status
            application.last_activity_at = datetime.now(timezone.utc)
            
            await self.application_repository.db.commit()
            
            if new_status == ApplicationStatus.SHORTLISTED:
                # Timeline: Application Shortlisted
                await self.candidate_email_service.send_shortlisted_email(
                    CandidateShortlistedData(
                        candidate_email=candidate.email,
                        candidate_name=candidate.full_name or candidate.email,
                        job_title= job.title if application.job else "the job"
                ))
            return {
                "application_id": str(application_id),
                "new_status": new_status.value
            }
        except Exception as e:
            self.logger.error(f"Failed to change application status for application_id={application_id} to new_status={new_status}: {str(e)}")
            raise DomainError(message="Failed to change application status", status_code=500)
    
    async def delete_application(self, application_id: str, org_id: str):
        try:
            application = await self.application_repository.get_application_by_id(application_id=application_id)

            if not application:
                raise DomainError(message="Application not found", status_code=404)

            # if str(application.job_id) != str(job_id):
            #     raise DomainError(message="Application does not belong to this job", status_code=403)

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
        
        
        
    # TODO: Need Optimization
    async def move_to_round(self,application_id:str,job_id:str,round_number:int):
        try:
            application = await self.application_repository.get_application_by_id(application_id=application_id)
            
            if not application:
                raise DomainError(message="Application not found", status_code=404)
            

            await self.db.refresh(application, ["candidate"])
            candidate = application.candidate 

            # can also check phone number later if required
            if not candidate:
                raise DomainError(message="Candidate not exist,Please Contact Support Team", status_code=400)
            
            if not candidate.email:
                raise DomainError(message="Candidate email not found for this application,Please First Add it", status_code=424)   # status code 424 Failed Dependency can be used when prerequisite information is missing and needs to be provided before the request can be processed.
            
            round_config = await self.interview_round_config_repository.get_interview_round_config_by_job_and_round(job_id=job_id, round_number=round_number)
            
            if not round_config:
                raise DomainError(message="There is no round config for this round,Add config first", status_code=425)  # status code 425 Too Early can be used when prerequisite information is missing and needs to be provided before the request can be processed.
            
                        
            panelists = await self.panelist_repository.get_all_panelists_by_round_config_id(round_config.id)
            
            if not panelists:
                raise DomainError(message="No panelists assigned for this round, please assign panelists to the round first", status_code=400)
            
            # ! not using  applicaion current_round field directly to validate if the move is valid or not, as sometimes application current_round can be out of sync with actual interview rounds created for the application, so validating based on actual interview rounds created and application current round both to make it more robust.
            
            # total_possible_round = await self.job_repository.get_total_rounds_for_job(job_id=job_id)
            
            
            # if round_number > total_possible_round:
            #     raise DomainError(message=f"Invalid round number, total possible rounds for this job is {total_possible_round}", status_code=400)
            
            current_round = await self.application_repository.get_current_interview_round_for_application(application_id=application_id)
            
            if current_round and round_number <= current_round:
                raise DomainError(message="Application is already in this round or higher round, cannot move back to same or previous round", status_code=400)
            
            if current_round and round_number > current_round + 1:
                    raise DomainError(message="Application can only be moved to the next round sequentially, cannot skip rounds", status_code=400)
                
            if application.status == ApplicationStatus.REJECTED:
                raise DomainError(message="Cannot move application to next round as it is already rejected", status_code=400)
            
            if round_number == 1 and application.status != ApplicationStatus.SHORTLISTED:
                raise DomainError(message="Application must be in shortlisted status to move to round 1", status_code=400)
            
            self._check_application_movable_to_new_round(application,round_config,round_number)

            
            new_interview = await self.interview_repository.create_interview(
                round_config_id=round_config.id,
                application_id=application_id,
                round_number=round_number
            ) 
            
            # Timeline: interview created
            await self.interview_event_repository.create_interview_event(
                interview_id=str(new_interview.id),
                event_type=InterviewEventType.Interview_Created.value,
                actor=InterviewEventActor.HR.value,
                summary=(f"Candidate moved to round {round_number} - {round_config.title}"
                         f"\nBooking Link will be sent to candidate."
                         ),
                details={"round_number": round_number, "round_title": round_config.title},
            )
            
                            
            job_settings = await self.job_repository.get_job_settings(round_config.job_id) 
        
        
            panelist_reminder_settings = ReminderSettingsDTO.model_validate(job_settings.panel_reminders) if job_settings and job_settings.panel_reminders else None
            candidate_reminder_settings = ReminderSettingsDTO.model_validate(job_settings.candidate_reminders) if job_settings and job_settings.candidate_reminders else None
                
            
            # ! should we also check slot repository for available slot or rely on slot_available flag | when candidate choose slot we maintain this flag that time if error occurs then we will implement this
            application.current_round = round_number
            if not round_config.slots_available:
 
                if round_config.end_date < datetime.now(timezone.utc):
                    raise DomainError("This Round has already ended", status_code=400)

                # Ask Panelist for new slots 
                remaining_seconds = (round_config.end_date - datetime.now(timezone.utc)).total_seconds()

                if remaining_seconds <= 0:
                    raise DomainError("Round already expired")

                token_expiry_in_min = max(1, int(remaining_seconds // 60))
                
                requested_panelist = await self.panelist_repository.request_panelist_for_availability(round_config.id, token_expiry_in_min)
                
                new_interview.status = InterviewStatus.COLLECTING_AVAILABILITY
  
                                    
                    
                    
                if requested_panelist:
                    if panelist_reminder_settings and panelist_reminder_settings.enabled and panelist_reminder_settings.form_reminder_sec:
                        reminders_payload =  self._create_form_reminder_payload_for_panelist(requested_panelist, round_config, panelist_reminder_settings) if panelist_reminder_settings and panelist_reminder_settings.enabled else []
                        
                        if reminders_payload:
                            reminders = await self.reminder_repository.create_reminders(reminders_payload)
                            
                            reminder_map = {str(r.id): r for r in reminders}
                            enqueue_payloads = [EnqueueReminderPayload(reminder_id=r.id,run_at=r.next_run_at)for r in reminders]
                            enqueue_results = await self.email_producer.enqueue_reminder_email_task(enqueue_payloads)

                            for res in enqueue_results:
                                if res.status == "success":
                                    reminder_map[str(res.reminder_id)].worker_job_id = res.job_id 
                    

                    await asyncio.gather(*[
                            self.panel_email_service.send_slot_availability_email(
                                AvailableSlotsData(
                                panelist_email=panelist.email,
                                panelist_name=panelist.name,
                                interview_round_title=round_config.title,
                                form_link=f"{self.frontend_url}/panelist/availability?token={panelist.availability_token}",
                                ))
                            for panelist in requested_panelist
                        ])
                    self.logger.info(f"Sent slot availability email to panelists for round_config_id={round_config.id} and application_id={application_id}")
                await self.db.commit()
                
                return {
                    "new_round": round_number,
                    "message":"Application moved to round successfully.Panelists have been requested for availability and booking link will be sent to candidate once slot will be available."
                    }
                
            else:             
                await self.db.refresh(application, ["candidate"])
                candidate = application.candidate
                if not candidate or not candidate.email:
                    raise DomainError("Candidate email not found for this application", status_code=400)

                remaining_seconds = (round_config.end_date - datetime.now(timezone.utc)).total_seconds()
                token_expiry_min = max(60, int(remaining_seconds // 60))

                booking_token = self.jwt_service.create_candidate_booking_token(
                    interview_id=str(new_interview.id),
                    candidate_email=candidate.email,
                    expiration_minutes=token_expiry_min,
                )
                new_interview.booking_token = booking_token
                new_interview.booking_token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_expiry_min)
                new_interview.status = InterviewStatus.READY_TO_BOOK


                # Send email (best-effort, after commit)
                booking_link = f"{self.frontend_url}/interview/book?token={booking_token}"
                
                reminders_payload = self._create_booking_reminder_payload_candidate(candidate,round_config,candidate_reminder_settings,booking_link,application.id) if candidate_reminder_settings and candidate_reminder_settings.enabled else []
            
                if reminders_payload:
                    reminders = await self.reminder_repository.create_reminders(reminders_payload)
                    
                    reminder_map = {str(r.id): r for r in reminders}
                    enqueue_payloads = [EnqueueReminderPayload(reminder_id=r.id,run_at=r.next_run_at)for r in reminders]
                    enqueue_results = await self.email_producer.enqueue_reminder_email_task(enqueue_payloads)

                    for res in enqueue_results:
                        if res.status == "success":
                            reminder_map[str(res.reminder_id)].worker_job_id = res.job_id 
                            
                    self.logger.info(f"Enqueued {len(enqueue_payloads)} reminder emails for candidates {candidate.full_name or candidate.email} for round_config {round_config.id}")
                    
                
                
                await self.db.commit()
                
                try:
                    await self.candidate_email_service.send_booking_link_email(
                            CandidateBookingLinkData(
                            candidate_email=candidate.email,
                            candidate_name=candidate.full_name or candidate.email,
                            interview_round_title=round_config.title,
                            booking_link=booking_link,
                            ))
                except Exception as e:
                    self.logger.error(f"Failed to send booking link email: {e}")

                self.logger.info(f"Slots available: Sent booking link to candidate for interview_id={new_interview.id}")
                
                
                    
                return {
                    "new_round": round_number,
                    "message":"Application moved to round successfully"
                    }
        except Exception as e:
            self.logger.error(f"Failed to move application to round for application_id={application_id} to round_number={round_number}: {str(e)}")
            await self.db.rollback()
            raise 
        
        
