from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,func
from sqlalchemy.orm import selectinload,joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Interview,Application
from datetime import datetime, timezone, timedelta
from typing import Optional,List
from src.dtos.interviews_dtos.interview_event_dto import CreateInterviewEventDTO
from src.models.enums import InterviewStatus
from configs.log_config import get_logger
from src.utils.jwt import jwt_service,JWTService





class InterviewRepository:
    def __init__(self,db: AsyncSession):
        self.db = db
        self.jwt_service : JWTService = jwt_service
        self.logger = get_logger("InterviewRepository")
    
    async def create_interview(self, round_config_id: str,application_id: str,round_number:int ) -> Interview:
        """Creates a new interview ."""
        interview = Interview(
               round_config_id=round_config_id,
                application_id=application_id,
                round_number=round_number   
        )
        self.db.add(interview)
        await self.db.flush() 
        return interview
    
    
    async def get_interview_by_id(self, interview_id: str) -> Optional[Interview]:
        result = await self.db.execute(
            select(Interview).where(Interview.id == interview_id)
        )
        return result.scalar_one_or_none()


    async def get_interview_by_application_id(self, application_id: str) -> Optional[Interview]:
        result = await self.db.execute(
            select(Interview).where(Interview.application_id == application_id)
        )
        return result.scalar_one_or_none()
    
    async def get_interview_by_application_id_and_round_number(self, application_id: str,round_number:int) -> Optional[Interview]:
        result = await self.db.execute(
            select(Interview).where(Interview.application_id == application_id,Interview.round_number == round_number)
        )
        return result.scalar_one_or_none()
    

    async def get_interviews_with_details_and_le_round_number(self, application_id: str, round_number: int):

        result = await self.db.execute(
            select(Interview)
            .options(
                selectinload(Interview.round_config),
                selectinload(Interview.events)
            )
            .where(
                Interview.application_id == application_id,
                Interview.round_number <= round_number
            )
            .order_by(Interview.round_number)
        )

        return result.scalars().all()
    
    
    async def send_booking_link_to_waiting_candidates(
        self,
        round_config_id: str,
        token_expiry_in_min: int
    ) :
        """Sends booking link to candidates who are in waiting state for a particular round config. We identify these candidates by looking at interviews which are in COLLECTING_AVAILABILITY state for that round config. We also generate a booking token for these interviews which will be used by candidates to access the booking page and book their slots."""

        result = await self.db.execute(
            select(Interview)
            .options(
                joinedload(Interview.application).joinedload(Application.candidate)
            )
            .where(
                Interview.round_config_id == round_config_id,
                Interview.status == InterviewStatus.COLLECTING_AVAILABILITY
            )
        )

        interviews = result.scalars().all()

        if not interviews:
            self.logger.info(
                f"No interviews in COLLECTING_AVAILABILITY state for round config ID {round_config_id}"
            )
            return []

        res_data = []

        for interview in interviews:
            candidate = interview.application.candidate

            booking_token = self.jwt_service.create_candidate_booking_token(
                interview_id=str(interview.id),
                candidate_email=candidate.email,
                expiration_minutes=token_expiry_in_min,
            )

            interview.booking_token = booking_token
            interview.booking_token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=token_expiry_in_min)
            interview.status = InterviewStatus.READY_TO_BOOK

            res_data.append({
                "candidate_full_name": candidate.full_name,
                "candidate_email": candidate.email,
                "booking_token": booking_token
            })

        await self.db.flush()
        return res_data