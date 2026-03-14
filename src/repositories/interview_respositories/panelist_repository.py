from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,func,not_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Panelist
from pydantic import EmailStr
from typing import Optional,List
from src.dtos.interviews_dtos.panel_dto import CreatePanelDTO
from src.models.enums import PanelistResponseStatus
from src.models import Interview_Round_Configs
from src.utils.jwt import jwt_service,JWTService
from datetime import datetime, timedelta, timezone
from src.services.errors.base import DomainError
from typing import List


class PanelistRepository:
    def __init__(self, db: AsyncSession,jwt_service: JWTService):
        self.db = db
        self.jwt_service = jwt_service

    async def add_panelists(
        self,
        round_config_id: str,
        interview_id: str,
        panel_data_list: list[CreatePanelDTO],
    ) -> list[Panelist]:
        """Create panelist availability records."""

        panelists = [
            Panelist(
                round_config_id=round_config_id,
                interview_id=interview_id,
                name=p.panelist_name,
                email=p.panelist_email,
                availability_token=p.availability_token,
                token_expires_at=p.token_expires_at,
            )
            for p in panel_data_list
        ]

        self.db.add_all(panelists)
        await self.db.flush()

        return panelists

    async def get_Panelist_by_id(
        self,
        panelist_id: str,
    ) -> Optional[Panelist]:

        result = await self.db.execute(
            select(Panelist)
            .where(Panelist.id == panelist_id)
        )

        return result.scalar_one_or_none()

    async def get_panelist_by_job_id(
        self,
        job_id: str,
    ) -> list[Panelist]:

        result = await self.db.execute(
            select(Panelist)
            .join(Interview_Round_Configs)
            .where(Interview_Round_Configs.job_id == job_id)
        )

        return result.scalars().all()

    async def get_panelist_by_round_config_and_email(
        self,
        round_config_id: str,
        panelist_email: EmailStr,
    ) -> Optional[Panelist]:

        result = await self.db.execute(
            select(Panelist)
            .where(
                Panelist.round_config_id == round_config_id,
                Panelist.email == panelist_email,
            )
        )

        return result.scalar_one_or_none()

    async def get_panelist_by_round_config_and_panelist_id(
        self,
        round_config_id: str,
        panelist_id: str,
    ) -> Optional[Panelist]:

        result = await self.db.execute(
            select(Panelist)
            .where(
                Panelist.round_config_id == round_config_id,
                Panelist.id == panelist_id,
            )
        )

        return result.scalar_one_or_none()



    async def get_panelists_by_round_config_and_panelist_ids(
        self,
        round_config_id: str,
        panelist_ids: list[str],
    ) -> list[Panelist]:

        result = await self.db.execute(
            select(Panelist)
            .where(
                Panelist.round_config_id == round_config_id,
                Panelist.id.in_(panelist_ids),
            )
        )

        return result.scalars().all()


    async def get_all_panelists_by_round_config_id(
        self,
        round_config_id: str,
    ) -> List[Panelist]:

        result = await self.db.execute(
            select(Panelist)
            .where(Panelist.round_config_id == round_config_id)
        )

        return result.scalars().all()


    async def get_all_panelists_by_round_config_id_and_status(
        self,
        round_config_id: str,
        status:PanelistResponseStatus
    ) -> List[Panelist]:
        
        """Get all panelists for a round config who are with the given status."""

        result = await self.db.execute(
            select(Panelist)
            .where(Panelist.round_config_id == round_config_id,Panelist.response_status==status)
        )

        return result.scalars().all()


    async def get_all_panelists_by_round_config_id_and_not_status(
        self,
        round_config_id: str,
        status:PanelistResponseStatus
    ) -> List[Panelist]:
        
        """Get all panelists for a round config who are not with the given status."""

        result = await self.db.execute(
            select(Panelist)
            .where(Panelist.round_config_id == round_config_id,Panelist.response_status != status)
        )

        return result.scalars().all()

    async def get_all_panelists_by_round_config_id_and_statuses(
        self,
        round_config_id: str,
        statuses: List[PanelistResponseStatus]
    ) -> List[Panelist]:
        
        """Get all panelists for a round config who match any of the given statuses."""

        result = await self.db.execute(
            select(Panelist)
            .where(
                Panelist.round_config_id == round_config_id,
                Panelist.response_status.in_(statuses)
            )
        )

        return result.scalars().all()
    
    async def get_panelists_not_pending(self, round_config_id: str):
        stmt = select(Panelist).where(
            Panelist.round_config_id == round_config_id,
            Panelist.response_status != PanelistResponseStatus.PENDING
        )

        result = await self.db.execute(stmt)
        return result.scalars().all()
    
        
    async def request_panelist_for_availability(
        self,
        round_config_id: str,
        token_expiry_in_min: int
    ) -> List[Panelist]:
        """Sends availability request to all panelists which are not already requested of a round config."""

        # requesting only those panelists who are not in pending state, as pending ones would have already received the request and might have responded to it. This also avoids sending multiple emails to panelists in case the interviewer clicks "Request Availability" multiple times.
        panelists = await self.get_all_panelists_by_round_config_id_and_not_status(round_config_id, PanelistResponseStatus.PENDING)

        if not panelists or len(panelists) == 0:
            raise DomainError("Panelist not found", status_code=404)
        
        now = datetime.now(timezone.utc)

        for panelist in panelists:

            panelist.availability_token = self.jwt_service.create_panelist_availability_token(
                panelist_id=str(panelist.id),
                round_config_id=str(round_config_id),
                expiration_minutes=token_expiry_in_min
            )
            panelist.response_status = PanelistResponseStatus.PENDING
            panelist.token_expires_at = now + timedelta(minutes=token_expiry_in_min)
            panelist.last_requested_at = now
            panelist.availability_request_count = panelist.availability_request_count + 1 if panelist.availability_request_count else 1
            

        await self.db.flush()

        return panelists
    
    
    async def request_panelist_ids_for_availability(
        self,
        round_config_id: str,
        panelist_ids: list[str],
        token_expiry_in_min: int
    ) -> dict:

        panelists = await self.get_panelists_by_round_config_and_panelist_ids(
            round_config_id,
            panelist_ids
        )

        found_ids = {str(p.id) for p in panelists}
        invalid_ids = [pid for pid in panelist_ids if pid not in found_ids]

        now = datetime.now(timezone.utc)

        requested_panelists = []
        already_pending_ids = []

        for panelist in panelists:

            if panelist.response_status == PanelistResponseStatus.PENDING:
                already_pending_ids.append(str(panelist.id))
                continue

            panelist.availability_token = self.jwt_service.create_panelist_availability_token(
                panelist_id=str(panelist.id),
                round_config_id=str(round_config_id),
                expiration_minutes=token_expiry_in_min
            )

            panelist.response_status = PanelistResponseStatus.PENDING
            panelist.token_expires_at = now + timedelta(minutes=token_expiry_in_min)
            panelist.last_requested_at = now
            panelist.availability_request_count = (
                panelist.availability_request_count + 1
                if panelist.availability_request_count
                else 1
            )

            requested_panelists.append(panelist)

        await self.db.flush()

        return {
            "requested_panelists": requested_panelists,
            "already_pending_ids": already_pending_ids,
            "invalid_ids": invalid_ids
        }
        
    async def get_panelists_by_round_config_id_with_slots(self,round_config_id:str)->List[Panelist]:
        """Get all panelists for a round config along with their slot information."""

        result = await self.db.execute(
            select(Panelist)
            .options(selectinload(Panelist.slots))
            .where(Panelist.round_config_id == round_config_id)
            .order_by(Panelist.created_at.desc())
        )

        return result.scalars().all()