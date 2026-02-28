from sqlalchemy.ext.asyncio import AsyncSession
from  configs.log_config import get_logger
from src.services.errors.base import DomainError
from src.repositories.interview_respositories.interview_round_configs_repository import InterviewRoundConfigsRepository
from src.repositories.interview_respositories.interview_event_repository import InterviewEventRepository
# from dtos.interviews_dtos.interviews_dto import 
from src.repositories.interview_respositories.panelist_repository import PanelistRepository
from src.repositories.interview_respositories.interview_repository import InterviewRepository
from src.services.email_services.panel.panel_email_service import PanelEmailService,panel_email_service
from src.utils.jwt import jwt_service,JWTService
from src.models.enums import PanelistResponseStatus
from datetime import datetime, timezone, timedelta
from src.dtos.interviews_dtos.panel_dto import AvailableSlot
from jwt import ExpiredSignatureError, InvalidTokenError


class PanelistService:
    def __init__(self, 
        interview_round_config_repository:InterviewRoundConfigsRepository,
        interview_event_repository:InterviewEventRepository,
        interview_repository:InterviewRepository,
        panelist_repository:PanelistRepository,
        db: AsyncSession):
        
        
        self.db = db
        self.interview_event_repository = interview_event_repository 
        self.interview_round_config_repository = interview_round_config_repository
        self.interview_repository = interview_repository
        self.panelist_repository = panelist_repository
        self.panel_email_service : PanelEmailService = panel_email_service
        self.jwt_service : JWTService = jwt_service
    
        self.logger = get_logger("PanelistService") 
    
    def _validate_and_extract_token_payload(
        self,
        availability_token: str
    ) -> tuple[str, str, str]:

        self.logger.info(f"Validating availability token: {availability_token}")    
        payload = self.jwt_service.decode_token(availability_token)

        interview_id = payload.get("interview_id",None)
        panelist_email = payload.get("panelist_email",None)
        round_config_id = payload.get("round_config_id",None)

        if not interview_id or not panelist_email or not round_config_id:
            raise DomainError(
                "Invalid token payload.",
                status_code=400
            )
        
        return interview_id, panelist_email, round_config_id
    
    def _check_panelist_form_open(self, round_config, panelist):
        now = datetime.now(timezone.utc)

        if panelist.response_status == PanelistResponseStatus.SUBMITTED:
            return {
                "status": "submitted",
                "message": "You have already submitted your availability. Thank you!",
            }
            
                
        if panelist.token_expires_at < now:
            return {
                "status": "expired",
                "message": "Your availability submission link has expired. Please contact HR to resend the link.",
            }


        if now > round_config.end_date:
            return {
                "status": "closed",
                "message": "The availability submission period for this interview round has ended.",
            }

        if now < round_config.start_date:
            return {
                "status": "not_started",
                "message": "The availability submission period has not started yet. Please check back later.",
            }

        return None  # Form is open
        
    # TODO: Mark Panels Token Expired while checking JWT
    async def get_panelist_form_details(self, availability_token: str):
        
        availability_token = availability_token.replace("Bearer ", "")
        interview_id, panelist_email, round_config_id = self._validate_and_extract_token_payload(availability_token)

        interview = await self.interview_repository.get_interview_by_id(interview_id)   
        
        if not interview:
            raise DomainError("Interview not found for the provided token")

        if str(interview.round_config_id) != str(round_config_id):
            raise DomainError("Token does not match interview configuration")
                
        round_config = await self.interview_round_config_repository.get_interview_round_config_by_id(
            interview.round_config_id
        )

        if not round_config:
            raise DomainError(
                "Interview round configuration not found for the provided token"
            )

        panelist = await self.panelist_repository.get_panelist_by_round_config_and_email(
            round_config_id=round_config.id,
            panelist_email=panelist_email,
        )

        if not panelist:
            raise DomainError("Panelist not found for the provided token")
        
        if panelist.availability_token != availability_token:
            raise DomainError(
                "Invalid or outdated availability link.",
                status_code=400
            )
                
        # ⭐ Check if form is open
        status_response = self._check_panelist_form_open(
            round_config,
            panelist,
        )

        if status_response:
            return status_response

        # ⭐ Form is open → return details
        return {
            "status": "open",
            "data": {
                "title": round_config.title,
                "start_date": round_config.start_date,
                "end_date": round_config.end_date,
                "duration_minutes": round_config.duration_minutes,
                "interview_type": round_config.interview_type,
            },
        }
        
        
    async def submit_panelist_availability(self, availability_token: str, available_slots: list[AvailableSlot]):
        try:
            
            if not available_slots:
                raise DomainError(
                    "At least one available slot must be provided.",
                    status_code=400
                )
            
            availability_token = availability_token.replace("Bearer ", "")
            interview_id, panelist_email, round_config_id = self._validate_and_extract_token_payload(availability_token)

            panelist = await self.panelist_repository.get_panelist_by_round_config_and_email(
                round_config_id=round_config_id,
                panelist_email=panelist_email,
            )
            if not panelist:
                raise DomainError("Panelist not found for the provided token")
            
            
            
            round_config = await self.interview_round_config_repository.get_interview_round_config_by_id(
                round_config_id=round_config_id
            )
            if not round_config:
                raise DomainError("Interview round configuration not found for the provided token")
            
            if panelist.availability_token != availability_token:
                raise DomainError(
                    "Invalid or outdated availability link.",
                    status_code=400
                )
            
            status_response = self._check_panelist_form_open(round_config, panelist)
            if status_response:
                return status_response
            
            available_slots_json = [
                    slot.model_dump(mode="json")
                    for slot in available_slots
                ]

            panelist.available_slots = available_slots_json
            panelist.response_status = PanelistResponseStatus.SUBMITTED
            panelist.responded_at = datetime.now(timezone.utc)
            panelist.availability_token = ""  # Invalidate the token after submission
            
            await self.db.flush()
            
            # TODO: Notify HR
            
            
            all_panelists = await self.panelist_repository.get_all_panelists_by_round_config_id(round_config_id)    
            
            
            if all(p.response_status == PanelistResponseStatus.SUBMITTED for p in all_panelists):
                # TODO: Enque background job to find common slots and update round config + send emails to panelists with final slots and update config with final slots and slots available
                pass
            
            await self.db.commit()
            
        except DomainError:
            raise
        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Error submitting panelist availability: {str(e)}")
            raise DomainError("An error occurred while submitting your availability. Please try again later.")
        
        