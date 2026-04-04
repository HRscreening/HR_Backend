from sqlalchemy.ext.asyncio import AsyncSession
from  configs.log_config import get_logger
from configs.env_config import FRONTEND_URL
import asyncio
from src.services.errors.base import DomainError
from src.modules.interviews.repositories.interview_event_repository import InterviewEventRepository
from src.modules.interviews.repositories.panelist_repository import PanelistRepository
from src.modules.interviews.repositories.interview_round_configs_repository import InterviewRoundConfigsRepository
from src.repositories.job_repository import JobRepository

from workers_async.email_tasks_producer import EmailProducer,EnqueueReminderPayload
from workers_async.assessment_task_producer import AssessmentTaskProducer,AnalyzeTranscriptPayload

from src.modules.reminders.reminder_repository import ReminderRepository
from datetime import datetime, timezone
from src.modules.email_services.services import PanelEmailService
from uuid import UUID
from src.modules.reminders.reminder_dtos import CreateReminderDTO
from src.modules.reminders.model.reminder_enum import ReminderType, RecipientType, EntityType, ReminderStatus
from datetime import timedelta
from src.modules.interviews.repositories.interview_assessment_repository import InterviewAssessmentRepository
from src.pipelines.interview_assessments.create_assessment_tag import create_assessment_tags
from src.modules.interviews.services.helpers.token_manager.Interview_token_manger import InterviewTokenManagerFactory
from src.enums.interview_token_facrory_enum import UserType
from src.dtos.token.token_dto import PanelistTokenDto
from src.modules.interviews.repositories.interview_repository import InterviewRepository
from src.modules.interviews.repositories.interview_slots_repository import InterviewSlotsRepository
from src.modules.interviews.repositories.interview_assessment_repository import InterviewAssessmentRepository
from src.dtos.job_settings_dto import FeedbackReminderSettingsDTO
from src.dtos.emails.panel_dto import PanelistFeedbackData
from typing import Optional, Tuple
from src.models.enums import InterviewStatus, InterviewAssessmentStatus
from src.modules.interviews.dtos.interview_assessment_dtos import InterviewAssessmentCreate
from src.pipelines.interview_assessments.analyze_and_feedback import run_transcript_analysis_pipeline,FinalFeedbackOutput
from data.transcript import load_transcript
from src.repositories.application_repository import ApplicationRepository
from src.models.enums import ApplicationStatus, InterviewStatus,InterviewEventActor,InterviewEventType
from src.dtos.job_settings_dto import ReminderSettingsDTO,ReschedulingSettingsDTO
from src.dtos.emails.panel_dto import AvailableSlotsData,PanelistReminderAvailabilityData
from src.dtos.emails.candidate_dto import CandidateBookingLinkReminderData,CandidateBookingLinkData
from src.utils.jwt import JWTService
from src.modules.email_services.services import EmailService, PanelEmailService
from src.modules.interviews.services.helpers.fireflies import FirefliesHelper
from src.utils.supabase_file_handler import SupabaseFileHandler

class BaseInterviewAssessmentService:
    def __init__(self, 
        interview_round_config_repository:InterviewRoundConfigsRepository,
        interview_event_repository:InterviewEventRepository,
        panelist_repository: PanelistRepository, 
        email_service: EmailService,
        interview_assessment_repository: InterviewAssessmentRepository,
        job_repository: JobRepository,
        email_producer: EmailProducer,
        reminder_repository: ReminderRepository,
        interview_repository: InterviewRepository,
        slot_repository : InterviewSlotsRepository,
        interview_token_manager_factory: InterviewTokenManagerFactory,
        db: AsyncSession,
        ):
        
        self.db = db
        self.interview_event_repository = interview_event_repository 
        self.interview_round_config_repository = interview_round_config_repository
        self.panelist_repository = panelist_repository
        self.email_service : EmailService = email_service
        self.job_repository = job_repository
        self.interview_assessment_repository = interview_assessment_repository
        self.email_producer = email_producer
        self.reminder_repository = reminder_repository
        self.interview_repository = interview_repository
        self.slot_repository = slot_repository
        self.interview_token_manager_factory = interview_token_manager_factory
        self.frontend_url = FRONTEND_URL
        
        
           
    async def _resolve_candidate_display(self, interview) -> tuple[Optional[object], str]:
        """Returns (candidate_obj, display_name). Safe — never raises."""
        try:
            await self.db.refresh(interview, ["application"])
            app = interview.application
            if app:
                await self.db.refresh(app, ["candidate"])
                candidate = app.candidate
                if candidate:
                    return candidate, candidate.full_name or candidate.email
        except Exception:
            pass
        return None, "Candidate"
        
    
        

class InterviewAssessmentService:
    def __init__(self, 
        interview_round_config_repository:InterviewRoundConfigsRepository,
        interview_event_repository:InterviewEventRepository,
        panelist_repository: PanelistRepository, 
        panel_email_service: PanelEmailService,
        interview_assessment_repository: InterviewAssessmentRepository,
        job_repository: JobRepository,
        email_producer: EmailProducer,
        assessment_task_producer: AssessmentTaskProducer,
        reminder_repository: ReminderRepository,
        interview_repository: InterviewRepository,
        slot_repository : InterviewSlotsRepository,
        interview_token_manager_factory: InterviewTokenManagerFactory,
        db: AsyncSession,
        ):
        
        self.db = db
        self.interview_event_repository = interview_event_repository 
        self.interview_round_config_repository = interview_round_config_repository
        self.panelist_repository = panelist_repository
        self.job_repository = job_repository
        self.interview_assessment_repository = interview_assessment_repository
        self.email_producer = email_producer
        self.reminder_repository = reminder_repository
        self.interview_repository = interview_repository
        self.slot_repository = slot_repository
        
        self.interview_token_manager_factory = interview_token_manager_factory
        self.assessment_task_producer = assessment_task_producer
        
        self.panel_email_service : PanelEmailService = panel_email_service
        self.frontend_url = FRONTEND_URL
        
        self.transcript_enqueing_max_retries = 3
        self.request_panelist_enqueing_max_retries = 3
        self.logger = get_logger("Inetrview_Assessment_Service") 
        
    
    async def _resolve_candidate_display(self, interview) -> tuple[Optional[object], str]:
        """Returns (candidate_obj, display_name). Safe — never raises."""
        try:
            await self.db.refresh(interview, ["application"])
            app = interview.application
            if app:
                await self.db.refresh(app, ["candidate"])
                candidate = app.candidate
                if candidate:
                    return candidate, candidate.full_name or candidate.email
        except Exception:
            pass
        return None, "Candidate"
        
    async def interview_completed_trnascript_generated(self,interview_id:str):
        try:
            interview = await self.interview_repository.get_interview_by_id(interview_id)
            
            if not interview:
                raise DomainError(f"Interview with id {interview_id} not found.")
            
            interview.status = InterviewStatus.AWAITING_FEEDBACK
            await self.interview_event_repository.create_interview_event(
                interview_id=UUID(interview_id),
                event_type="interview_completed",
                summary=f"Interview completed and transcript generated.Analyzing transcript and requesting assessment from panelists.",
                actor=f"system"
            )
            
            transcript_equeing_failed_cnt = 0 
            while transcript_equeing_failed_cnt < self.transcript_enqueing_max_retries:
                result_transcipt = await self.assessment_task_producer.enqueue_transcript_analysis_job(AnalyzeTranscriptPayload(interview_id=interview_id))
                if result_transcipt:
                    break
                transcript_equeing_failed_cnt += 1
                self.logger.warning(f"Failed to enqueue transcript analysis job for interview_id {interview_id}. Retying... Attempt {transcript_equeing_failed_cnt}/3")
            

            request_assessment_failed_cnt = 0
            while request_assessment_failed_cnt < self.request_panelist_enqueing_max_retries:
                result_request =  await self.assessment_task_producer.enqueue_request_panelist_job(interview_id=interview_id)
                if result_request:
                    break
                request_assessment_failed_cnt += 1
                self.logger.warning(f"Failed to enqueue request panelist job for interview_id {interview_id}. Retying... Attempt {request_assessment_failed_cnt}/3")
                
            
            
            await self.db.commit()         
        except Exception as e:
            self.logger.error(f"Error in post interview completion process for interview_id {interview_id}: {str(e)}")
            raise DomainError(f"Failed in post interview completion process: {str(e)}")
    
    async def generate_assessment_tags(self, job_id: str, round_title: str):
        try:
            
            job = await self.job_repository.get_job_by_id(UUID(job_id))
            
            if not job:
                raise DomainError(f"Job with id {job_id} not found.")
            
            # ! need some checks here to job is in active state.
            # TODO: Apply those checks when finalized
            
            active_rubric = await self.job_repository.get_active_rubric(job_id)
            
            if not active_rubric:
                raise DomainError(f"No active rubric found for job with id {job_id}.")
            
            tags:list[str] = await create_assessment_tags(active_rubric.criteria, job.title)
            
            return tags
        
        except Exception as e:
            self.logger.error(f"Error generating assessment tags for job_id {job_id} and round_title {round_title}: {str(e)}")
            raise DomainError(f"Failed to generate assessment tags: {str(e)}")

    async def get_interview_assessment_form_parameters(self,token:str):
        try:
            # ! need to check token validity and expiry
            panelist_token_manager = self.interview_token_manager_factory.get_manager(UserType.PANELIST)
            payload = PanelistTokenDto.model_validate(panelist_token_manager.validate_token(token))


            print("Validated token payload:", payload)
            interview_id = payload.interview_id
            round_config_id = payload.round_config_id
            panelist_id = payload.panelist_id
            type = payload.token_type
            
            if type != "assessment":
                raise DomainError("Invalid token")
            
            interview_assessment = await self.interview_assessment_repository.get_interview_assessment_by_interview_id(interview_id)
            
            if not interview_assessment or str(interview_assessment.panelist_id) != panelist_id or interview_assessment.feedback_token != token or interview_assessment.token_expires_at < datetime.now(timezone.utc):
                raise DomainError("Invalid or expired token.")
        
            if interview_assessment.status == InterviewAssessmentStatus.NOT_REQUESTED:
                raise DomainError("Assessment has not been requested for this interview yet.")
            
            if interview_assessment.status == InterviewAssessmentStatus.SUBMITTED:
                raise DomainError("Assessment has already been submitted for this interview.")
          
          
            round_config =  await self.interview_round_config_repository.get_interview_round_config_by_id(round_config_id)
            
            if not round_config:
                raise DomainError(f"Round configuration with id {round_config_id} not found.")
            
            
            return round_config.assessment_criterias       
                
        except Exception as e:
            self.logger.error(f"Error fetching interview assessment form parameters for token {token}: {str(e)}")
            raise DomainError(f"Failed to fetch interview assessment form parameters: {str(e)}")
     
    
    async def submit_interview_assessment(self,token:str,data:InterviewAssessmentCreate):
        try:
            # ! need to check token validity and expiry
            panelist_token_manager = self.interview_token_manager_factory.get_manager(UserType.PANELIST)
            payload = PanelistTokenDto.model_validate(panelist_token_manager.validate_token(token))


            print("Validated token payload:", payload)
            interview_id = payload.interview_id
            round_config_id = payload.round_config_id
            panelist_id = payload.panelist_id
            type = payload.token_type
            
            if type != "assessment":
                raise DomainError("Invalid token")
            
            interview_assessment = await self.interview_assessment_repository.get_interview_assessment_by_interview_id(interview_id)
            
            if not interview_assessment or str(interview_assessment.panelist_id) != panelist_id or interview_assessment.feedback_token != token or interview_assessment.token_expires_at < datetime.now(timezone.utc):
                print("Interview assessment not found or token mismatch or token expired for interview_id:", interview_id)
                
                raise DomainError("Invalid or expired token.")
            
            if interview_assessment.status == InterviewAssessmentStatus.NOT_REQUESTED:
                raise DomainError("Assessment has not been requested for this interview yet.")
            
            if interview_assessment.status == InterviewAssessmentStatus.SUBMITTED:
                raise DomainError("Assessment has already been submitted for this interview.")

            # TODO: change to enum type later
            interview_assessment.final_verdict = data.final_verdict

            interview_assessment.response = {
                "criteria_ratings": [cr.model_dump() for cr in data.criteria_ratings],
            }
            
            # Canceling any pending feedback reminder emails for this interview since assessment is being submitted now
            pending_reminders = await self.reminder_repository.get_all_reminders_by_entity_id_and_type(str(interview_id), EntityType.INTERVIEW,ReminderStatus.PENDING ,ReminderType.FEEDBACK_PENDING)
            
            if pending_reminders:
                pending_ids = [str(r.id) for r in pending_reminders]
                await self.email_producer.cancel_jobs(pending_ids)
            
            interview_assessment.status = InterviewAssessmentStatus.SUBMITTED
            interview_assessment.submitted_at = datetime.now(timezone.utc)
            interview_assessment.feedback_token = None
            interview_assessment.token_expires_at = None
            
            await self.interview_event_repository.create_interview_event(
                interview_id=UUID(interview_id),
                event_type="assessment_submitted",
                summary=f"Assessment submitted by panelist.",
                actor=f"panelist"
            )
            await self.assessment_task_producer.enqueue_interview_post_processing(interview_id=interview_id)
            await self.db.commit()
            
            return {"message": "Assessment submitted successfully."}
   
        except Exception as e:
            self.logger.error(f"Error fetching interview assessment form parameters for token {token}: {str(e)}")
            raise DomainError(f"Failed to fetch interview assessment form parameters: {str(e)}")
    
    # TODO: Optimize and make it cleaner
    async def request_interview_assessment_to_panelist(self,interview_id:str):
        try:
                        
            interview = await self.interview_repository.get_interview_by_id(interview_id)

            if not interview:
                raise DomainError(f"Interview with id {interview_id} not found.")
            
            existing_assessment = await self.interview_assessment_repository.get_interview_assessment_by_interview_id(interview_id)
            
            if existing_assessment and existing_assessment.status !=  InterviewAssessmentStatus.NOT_REQUESTED:
                # ! this means assessment has already been requested or even submitted for this interview, in both cases we should not request again, if needed we can have a separate flow for resending the assessment request email later
                return (f"Assessment has already been requested for interview with id {interview_id}.")
            
            
            # ! for testing purpose
            if interview.status != InterviewStatus.AWAITING_FEEDBACK:
                raise DomainError(f"Interview with id {interview_id} is not in a state to request assessment.")
            
            round_config = await self.interview_round_config_repository.get_interview_round_config_by_id(interview.round_config_id)
            
            if not round_config:
                raise DomainError(f"Round configurations not found.")

            job_settings = await self.job_repository.get_job_settings(round_config.job_id)
            
            feedback_reminder_settings = FeedbackReminderSettingsDTO.model_validate(job_settings.feedback_reminders) if job_settings and job_settings.feedback_reminders else None

            booked_slot = await self.slot_repository.get_slot_by_interview_id_with_panelist(interview_id)

            if not booked_slot:
                raise DomainError(f"No booked slot found for interview with id {interview_id}.")
            
            panelist = booked_slot.panelist

            if not panelist:
                raise DomainError(f"No panelist found for interview with id {interview_id}.")
            
            panelist_token_manager = self.interview_token_manager_factory.get_manager(UserType.PANELIST)
            
                        
            expiry = round_config.end_date - datetime.now(timezone.utc)
            expiry_minutes = int(expiry.total_seconds() // 60)
            
            token = panelist_token_manager.create_token(
                token_type="assessment",
                expiration_minutes= expiry_minutes if expiry_minutes > 0 else 1, # If the interview round has already ended, set token to expire in 1 minute
                panelist_id=str(panelist.id),
                round_config_id=str(interview.round_config_id),
                interview_id=str(interview.id)
            )
            
            await self.interview_assessment_repository.create_interview_assessment(
                interview_id=interview.id,
                panelist_id=panelist.id,
                token=token,
                token_expiry=round_config.end_date
            )

            await self.interview_event_repository.create_interview_event(
                interview_id=UUID(interview_id),
                event_type="assessment_requested",
                summary=f"Assessment requested from panelist {panelist.name}",
                actor=f"system"
            )
            candidate, candidate_display = await self._resolve_candidate_display(interview)
           
            
            form_link = f"{self.frontend_url}/interview/assessment?token={token}"
            
            if feedback_reminder_settings and feedback_reminder_settings.enabled:
                reminders_payload = []
                for reminder_sec in feedback_reminder_settings.form_reminder_sec:
                    reminders_payload.append(CreateReminderDTO(
                    entity_id=str(interview.id),
                    entity_type=EntityType.INTERVIEW,
                    payload=PanelistFeedbackData(
                        candidate_name=candidate.full_name if candidate else "Candidate",
                        panelist_email=panelist.email,
                        panelist_name=panelist.name,
                        interview_round_title=round_config.title,
                        form_link=form_link,
                        form_valid_till=round_config.end_date
                    ).model_dump(mode="json"),
                    recipient_id=str(panelist.id or candidate.email),
                    recipient_type=RecipientType.PANELIST,
                    reminder_type=ReminderType.FEEDBACK_PENDING,
                    # ! set it before the slot start time minus the reminder hours, currently in minutes for testing, change to hours later
                    next_run_at= datetime.now(timezone.utc) + timedelta(seconds=reminder_sec)  #! for now doing in minutes, change to hours later       
                ))
                    
                    
                if reminders_payload:
                    reminders = await self.reminder_repository.create_reminders(reminders_payload)
                    
                    reminder_map = {str(r.id): r for r in reminders}
                    enqueue_payloads = [EnqueueReminderPayload(reminder_id=r.id,run_at=r.next_run_at)for r in reminders]
                    enqueue_results = await self.email_producer.enqueue_reminder_email_task(enqueue_payloads)

                    for res in enqueue_results:
                        if res.status == "success":
                            reminder_map[str(res.reminder_id)].worker_job_id = res.job_id 
                    
                    self.logger.info(f"Enqueued {len(enqueue_payloads)} reminders for interview assessment feedback for interview_id {interview_id} and panelist_id {panelist.id}")
            

            task = [self.panel_email_service.send_panelist_feedback_request_email(
                        PanelistFeedbackData(
                        panelist_email=panelist.email,
                        panelist_name=panelist.name,
                        candidate_name=candidate_display,
                        interview_round_title=round_config.title,
                        form_link=form_link,
                        form_valid_till=round_config.end_date
                        )
                    )]
            
            await asyncio.gather(*task,return_exceptions=True)
            
            self.logger.info(f"Requested interview assessment for interview_id {interview_id} from panelist_id {panelist.id}")
            await self.db.commit()
           
            return {"message": "Assessment requested successfully."}    

        except Exception as e:
            self.logger.error(f"Error requesting interview assessment for interview_id {interview_id}: {str(e)}")
            raise DomainError(f"Failed to request interview assessment: {str(e)}")
        
    async def analyze_interview_transcript(self,interview_id:str):
        """This method will be called after the interview is completed and transcript is available, it will run the analysis pipeline and store the AI generated summary and assessment in the interview record, and then request assessment from panelists."""
        try:
            interview = await self.interview_repository.get_interview_by_id(interview_id)
            if not interview:
                raise DomainError(f"Interview with id {interview_id} not found.")   
            
            round_config = await self.interview_round_config_repository.get_interview_round_config_by_id(interview.round_config_id)
            if not round_config:
                raise DomainError(f"Round configuration with id {interview.round_config_id} not found.")
            
            job_criterias = await self.job_repository.get_active_rubric(round_config.job_id)
            
            if not job_criterias:
                raise DomainError(f"No active rubric found for job with id {round_config.job_id}.")
            
            # ! currently hardcoded transcript loading for testing, need to integrate with actual transcript storage later you either need to either save the transcript in db or fetch it real time for now just loading from a json file for testing the pipeline
            transcript = load_transcript()
            actual_transcript = transcript["data"]["transcript"]
            
            result = await run_transcript_analysis_pipeline(actual_transcript, round_config.assessment_criterias, job_criterias.criteria)
            result = FinalFeedbackOutput(**result)
            print("RESULT",result,"\n\n\n")
            interview.ai_summary = result.interview_summary if result.interview_summary else None
            interview_ai_assessment = result.model_dump(exclude_none=True,exclude={"interview_summary"}) if result else None
            interview.ai_assessment = interview_ai_assessment 
            interview.status = InterviewStatus.AWAITING_FEEDBACK
            
            
            await self.interview_event_repository.create_interview_event(
                interview_id=UUID(interview_id),
                event_type="interview_analyzed",
                summary=f"Interview transcript analyzed and AI assessment generated.",
                actor=f"system"
            )
            await self.db.commit()
            

            return {"message": "Interview transcript analyzed and assessment requested successfully."}
            

        except Exception as e:
            self.logger.error(f"Error analyzing interview transcript for interview_id {interview_id}: {str(e)}")
            raise DomainError(f"Failed to analyze interview transcript: {str(e)}")

    async def get_interview_assessment(self,interview_id:str):
        """method to fetch the interview assessment for a given interview id, mainly for testing and verification of the analysis pipeline output, will be used in the future to show the AI generated assessment and feedback in the frontend."""
        try:
            interview = await self.interview_repository.get_interview_by_id(interview_id)
            
            if not interview:
                raise DomainError(f"Interview with id {interview_id} not found.")
            
            panelist_assessment = await self.interview_assessment_repository.get_interview_assessment_by_interview_id(interview_id) 
            
            return {
                "ai_assessment": interview.ai_assessment,
                "panelist_assessment": {
                    "final_verdict": panelist_assessment.final_verdict,
                    "response": panelist_assessment.response,
                    "submitted_at": panelist_assessment.submitted_at
                } if panelist_assessment else None
            }
        
        except Exception as e:
            self.logger.error(f"Error fetching interview assessment for interview_id {interview_id}: {str(e)}")
            raise 
    
    async def interview_post_processing(self,interview_id:str):
        try:
            await self.assessment_task_producer.enqueue_request_panelist_job(interview_id=interview_id)
            await self.assessment_task_producer.enqueue_interview_post_processing(interview_id=interview_id)
            
            return {"message": "Interview post processing tasks enqueued successfully."}
        except Exception as e:
            self.logger.error(f"Error in interview post processing for interview_id {interview_id}: {str(e)}")
            raise DomainError(f"Failed in interview post processing: {str(e)}")
            
    async def process_received_transcript(self,payload:dict):
        try:
            meeting_id = payload.get("meeting_id")
            event = payload.get("event")
            
            
            if event != "meeting.transcribed":
                self.logger.warning(f"Received unsupported event type in transcript webhook: {event}")
                return {"message": f"Ignored unsupported event type: {event}"}
                
            if not meeting_id:
                self.logger.error(f"Invalid payload received in transcript webhook: {payload}")
                raise DomainError("Invalid payload: interview_id and transcript are required.")
            
            await self.assessment_task_producer.enqueue_interview_extraction_and_post_processsing(meeting_id)
            
            return {"message": "Transcript received successfully"}
        
        
        except Exception as e:
                self.logger.error(f"Error processing received transcript webhook: {str(e)}")
                raise DomainError(f"Failed to process received transcript: {str(e)}")
                
        
        
# TODO: TO be implemented
class InterviewAssessmentWorkerService(BaseInterviewAssessmentService):
    def __init__(self,
        interview_round_config_repository:InterviewRoundConfigsRepository,
        interview_event_repository:InterviewEventRepository,
        panelist_repository: PanelistRepository, 
        email_service: EmailService,
        interview_assessment_repository: InterviewAssessmentRepository,
        job_repository: JobRepository,
        email_producer: EmailProducer,
        reminder_repository: ReminderRepository,
        interview_repository: InterviewRepository,
        slot_repository : InterviewSlotsRepository,
        application_repository : ApplicationRepository,
        jwt_service: JWTService,
        interview_token_manager_factory: InterviewTokenManagerFactory,
        fireflies_helper: FirefliesHelper,
        assessment_task_producer: AssessmentTaskProducer,
        supabase_file_handler: SupabaseFileHandler,
        db: AsyncSession):
        
        super().__init__(
            interview_round_config_repository,
            interview_event_repository,
            panelist_repository,
            email_service,
            interview_assessment_repository,
            job_repository,
            email_producer,
            reminder_repository,
            interview_repository,
            slot_repository,
            interview_token_manager_factory,
            db
        )
        self.application_repository = application_repository
        self.fireflies_helper = fireflies_helper
        self.jwt_service = jwt_service
        self.assessment_task_producer = assessment_task_producer
        self.supabase_file_handler = supabase_file_handler
        self.logger = get_logger("Interview_Assessment_Worker_Service")
        
        # TODO: Optimize and make it cleaner
    
    
            
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
                    next_run_at= datetime.now(timezone.utc) + timedelta(seconds=reminder_sec)  #! for now doing in minutes, change to hours later       
                ))
            return reminders_payload
    
    
   
    async def request_interview_assessment_to_panelist(self,interview_id:str):
        try:
            self.logger.info(f"Starting process to request interview assessment for interview_id {interview_id}")      
            interview = await self.interview_repository.get_interview_by_id(interview_id)

            if not interview:
                raise DomainError(f"Interview with id {interview_id} not found.")
            
            existing_assessment = await self.interview_assessment_repository.get_interview_assessment_by_interview_id(interview_id)
            
            if existing_assessment and existing_assessment.status !=  InterviewAssessmentStatus.NOT_REQUESTED:
                raise DomainError(f"Assessment has already been requested for interview with id {interview_id}.")
            
            
            # ! for testing purpose
            if interview.status != InterviewStatus.AWAITING_FEEDBACK:
                raise DomainError(f"Interview with id {interview_id} is not in a state to request assessment.")
            
            round_config = await self.interview_round_config_repository.get_interview_round_config_by_id(interview.round_config_id)
            
            if not round_config:
                raise DomainError(f"Round configurations not found.")

            job_settings = await self.job_repository.get_job_settings(round_config.job_id)
            
            feedback_reminder_settings = FeedbackReminderSettingsDTO.model_validate(job_settings.feedback_reminders) if job_settings and job_settings.feedback_reminders else None

            booked_slot = await self.slot_repository.get_slot_by_interview_id_with_panelist(interview_id)

            if not booked_slot:
                raise DomainError(f"No booked slot found for interview with id {interview_id}.")
            
            panelist = booked_slot.panelist

            if not panelist:
                raise DomainError(f"No panelist found for interview with id {interview_id}.")
            
            panelist_token_manager = self.interview_token_manager_factory.get_manager(UserType.PANELIST)
            
                        
            expiry = round_config.end_date - datetime.now(timezone.utc)
            expiry_minutes = int(expiry.total_seconds() // 60)
            
            token = panelist_token_manager.create_token(
                token_type="assessment",
                expiration_minutes= expiry_minutes if expiry_minutes > 0 else 1, # If the interview round has already ended, set token to expire in 1 minute
                panelist_id=str(panelist.id),
                round_config_id=str(interview.round_config_id),
                interview_id=str(interview.id)
            )
            
            await self.interview_assessment_repository.create_interview_assessment(
                interview_id=interview.id,
                panelist_id=panelist.id,
                token=token,
                token_expiry=round_config.end_date
            )

            await self.interview_event_repository.create_interview_event(
                interview_id=UUID(interview_id),
                event_type="assessment_requested",
                summary=f"Assessment requested from panelist {panelist.name}",
                actor=f"system"
            )
            candidate, candidate_display = await self._resolve_candidate_display(interview)
           
            
            form_link = f"{self.frontend_url}/interview/assessment?token={token}"
            
            if feedback_reminder_settings and feedback_reminder_settings.enabled:
                reminders_payload = []
                for reminder_sec in feedback_reminder_settings.form_reminder_sec:
                    reminders_payload.append(CreateReminderDTO(
                    entity_id=str(interview.id),
                    entity_type=EntityType.INTERVIEW,
                    payload=PanelistFeedbackData(
                        candidate_name=candidate.full_name if candidate else "Candidate",
                        panelist_email=panelist.email,
                        panelist_name=panelist.name,
                        interview_round_title=round_config.title,
                        form_link=form_link,
                        form_valid_till=round_config.end_date
                    ).model_dump(mode="json"),
                    recipient_id=str(panelist.id or candidate.email),
                    recipient_type=RecipientType.PANELIST,
                    reminder_type=ReminderType.FEEDBACK_PENDING,
                    # ! set it before the slot start time minus the reminder hours, currently in minutes for testing, change to hours later
                    next_run_at= datetime.now(timezone.utc) + timedelta(seconds=reminder_sec)  #! for now doing in minutes, change to hours later       
                ))
                    
                    
                if reminders_payload:
                    reminders = await self.reminder_repository.create_reminders(reminders_payload)
                    
                    reminder_map = {str(r.id): r for r in reminders}
                    enqueue_payloads = [EnqueueReminderPayload(reminder_id=r.id,run_at=r.next_run_at)for r in reminders]
                    enqueue_results = await self.email_producer.enqueue_reminder_email_task(enqueue_payloads)

                    for res in enqueue_results:
                        if res.status == "success":
                            reminder_map[str(res.reminder_id)].worker_job_id = res.job_id 
                    
                    self.logger.info(f"Enqueued {len(enqueue_payloads)} reminders for interview assessment feedback for interview_id {interview_id} and panelist_id {panelist.id}")
            

            task = [self.email_service.panel.send_panelist_feedback_request_email(
                        PanelistFeedbackData(
                        panelist_email=panelist.email,
                        panelist_name=panelist.name,
                        candidate_name=candidate_display,
                        interview_round_title=round_config.title,
                        form_link=form_link,
                        form_valid_till=round_config.end_date
                        )
                    )]
            
            await asyncio.gather(*task,return_exceptions=True)
            
            self.logger.info(f"Requested interview assessment for interview_id {interview_id} from panelist_id {panelist.id}")
            await self.db.commit()
           
            return {"message": "Assessment requested successfully."}    

        except Exception as e:
            self.logger.error(f"Error requesting interview assessment for interview_id {interview_id}: {str(e)}")
            raise 

        
    async def analyze_interview_transcript(self,interview_id:str):
        """This method will be called after the interview is completed and transcript is available, it will run the analysis pipeline and store the AI generated summary and assessment in the interview record, and then request assessment from panelists."""
        try:
            interview = await self.interview_repository.get_interview_by_id(interview_id)
            
            if not interview:
                raise DomainError(f"Interview with id {interview_id} not found.")   
            
            round_config = await self.interview_round_config_repository.get_interview_round_config_by_id(interview.round_config_id)
            
            if not round_config:
                raise DomainError(f"Round configuration with id {interview.round_config_id} not found.")
            
            job_criterias = await self.job_repository.get_active_rubric(round_config.job_id)
            
            if not job_criterias:
                raise DomainError(f"No active rubric found for job with id {round_config.job_id}.")
            
            
            if not interview.transcript_url:
                raise DomainError(f"No transcript URL found for interview with id {interview_id}.")
            
            # ! currently hardcoded transcript loading for testing, need to integrate with actual transcript storage later
            transcript = await self.supabase_file_handler.get_json_data_from_file_on_supabase(interview.transcript_url)
            
            result = await run_transcript_analysis_pipeline(transcript, round_config.assessment_criterias, job_criterias.criteria)
            result = FinalFeedbackOutput(**result)
            print("RESULT",result,"\n\n\n")
            interview.ai_summary = result.interview_summary if result.interview_summary else None
            interview_ai_assessment = result.model_dump(exclude_none=True,exclude={"interview_summary"}) if result else None
            interview.ai_assessment = interview_ai_assessment 
            
            
            
            await self.interview_event_repository.create_interview_event(
                interview_id=UUID(interview_id),
                event_type="interview_analyzed",
                summary=f"Interview transcript analyzed and AI assessment generated.",
                actor=f"system"
            )
            await self.db.commit()
            

            return {"message": "Interview transcript analyzed and assessment requested successfully."}
            

        except Exception as e:
            self.logger.error(f"Error analyzing interview transcript for interview_id {interview_id}: {str(e)}")
            raise 

    
    async def _move_to_round(self,application_id:str,job_id:str,round_number:int,job_settings,round_config):
        try:
            
            application = await self.application_repository.get_application_by_id(application_id)
          
            panelist_reminder_settings = ReminderSettingsDTO.model_validate(job_settings.panel_reminders) if job_settings and job_settings.panel_reminders else None
            candidate_reminder_settings = ReminderSettingsDTO.model_validate(job_settings.candidate_reminders) if job_settings and job_settings.candidate_reminders else None
                

            
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
                    if panelist_reminder_settings and panelist_reminder_settings.enabled and panelist_reminder_settings.form_reminder_hours:
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
                            self.email_service.panel.send_slot_availability_email(
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
                    await self.email_service.candidate.send_booking_link_email(
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
    
    async def _move_to_offer(self,interview, round_config, job_settings):
        pass

    async def move_interview_ahead(self,interview_id:str):
        try:
            interview = await self.interview_repository.get_interview_by_id(interview_id)
            if not interview:
                raise DomainError(f"Interview with id {interview_id} not found.")
            
            round_config = await self.interview_round_config_repository.get_interview_round_config_by_id(interview.round_config_id)
            if not round_config:
                raise DomainError(f"Round configuration with id {interview.round_config_id} not found.")
            
            max_round_number = await self.interview_round_config_repository.get_total_rounds_from_round_config(round_config.job_id)
            
            print("Max Round Number", max_round_number)
            job_settings = await self.job_repository.get_job_settings(round_config.job_id) 
            
            if not job_settings:
                raise DomainError(message="Job settings not found for the job, please set job settings first", status_code=400)
            
            if job_settings.auto_move_to_next_round == False:
                raise DomainError(message="Auto move to next round is disabled for this job, cannot move application to next round", status_code=400)        
            

            # ! edge case is what if hr has only configured only 1 round and he may want to add more rounds further
            if interview.round_number == max_round_number and job_settings.auto_offer_enabled:
                self.logger.info(f"Interview {interview_id} is already in the final round, moving to offer since auto_offer is enabled for the job")
                return await self._move_to_offer(interview, round_config, job_settings)

            
            elif interview.round_number < max_round_number:
                next_round_number = interview.round_number + 1
                next_round_config = await self.interview_round_config_repository.get_interview_round_config_by_job_and_round(round_config.job_id, next_round_number)
                
                if not next_round_config:
                    self.logger.error(f"Round configuration for round {next_round_number} not found for job {round_config.job_id}")
                    raise DomainError(f"Configuration for the next round (Round {next_round_number}) is missing.")

                self.logger.info(f"Moving interview {interview_id} to next round {next_round_number} using config {next_round_config.id}")
                return await self._move_to_round(interview.application_id, round_config.job_id, next_round_number, job_settings, next_round_config)

            else:
                raise DomainError(f"Interview {interview_id} has invalid round number {interview.round_number} which is greater than max round number {max_round_number} for the job.")
            
        
        except Exception as e:
            self.logger.error(f"Failed to move interview ahead: {str(e)}")
            raise
    
    async def processs_interview_extraction_and_post_processsing(self, meeting_id:str):
        """This method will be called after receiving the transcript from fireflies, it will run the analysis pipeline and store the AI generated summary and assessment in the interview record, and then request assessment from panelists."""
        try:
            
            cal_id,transcript = await self.fireflies_helper.fetch_transcript(meeting_id)
            
            if not cal_id or not transcript:
                raise DomainError(f"Failed to fetch transcript for meeting_id {meeting_id}")
            
            interview = await self.interview_repository.get_interview_by_calendar_id(cal_id)
            
            if not interview:
                raise DomainError(f"Interview with calendar id {cal_id} not found.")
            
            if interview.status != InterviewStatus.SCHEDULED:
                raise DomainError(f"Only interviews in SCHEDULED status can be processed for transcript analysis and assessment request, interview with calendar id {cal_id} is in {interview.status} status.")
            
            
            transcrip_url = await  self.supabase_file_handler.save_json_file_from_data(
                data=transcript,
                destination_path=f"{interview.round_config_id}",
                filename=f"{interview.id}_transcript"
                ) 
            
            interview.transcript_url = transcrip_url
            interview.status = InterviewStatus.AWAITING_FEEDBACK
            
            await self.assessment_task_producer.enqueue_transcript_analysis_job(AnalyzeTranscriptPayload(
                interview_id=str(interview.id)))
            await self.assessment_task_producer.enqueue_request_panelist_job(interview_id=str(interview.id))
            
            
            self.logger.info(f"Enqueued transcript analysis and panelist assessment request for interview_id {interview.id} with calendar_id {cal_id}")
            await self.db.commit()
            
        except Exception as e:
            self.logger.error(f"Error in interview extraction and post processing for meeting_id {meeting_id}: {str(e)}")
            raise 
    