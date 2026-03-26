from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,func,not_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Panelist
from pydantic import EmailStr
from typing import Optional,List
from src.modules.interviews.dtos.panel_dto import CreatePanelDTO,updatePanelistLists,PanelistDTO,PanelistEditDTO
from src.models.enums import PanelistResponseStatus
from src.models import Interview_Round_Configs
from datetime import datetime, timedelta, timezone
from src.services.errors.base import DomainError
from typing import List

from src.utils.jwt import JWTService


class PanelistRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.jwt_service : JWTService = JWTService()

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

    async def bulk_add_panelist_to_round_config(self, round_config_id: str, panelist_data: List[PanelistDTO]) -> Panelist:
        """Add a single panelist to a round config."""
        panelists = [
            Panelist(
                round_config_id=round_config_id,
                name=p.name,
                email=p.email,
                role=p.role
            )
            for p in panelist_data
        ]

        self.db.add_all(panelists)
        await self.db.flush()

        return panelists
    
    async def bulk_update_panelists(self, round_config_id: str, panelist_data: List[PanelistEditDTO]) -> List[Panelist]:
        """Bulk update panelists of a round config based on the provided data."""
        updated_panelists = []

        for panel_data in panelist_data:
            panelist = await self.get_panelist_by_round_config_and_panelist_id(
                round_config_id,
                panel_data.id
            )

            if not panelist:
                raise DomainError(f"Panelist with ID {panel_data.id} not found in round config {round_config_id}", status_code=404)

            panelist.name = panel_data.name
            panelist.email = panel_data.email
            panelist.role = panel_data.role

            updated_panelists.append(panelist)

        await self.db.flush()
        return updated_panelists
    
    
    # TODO: Need to handle interview and etc while deleting it
    async def delete_panelists_by_ids(self, round_config_id: str, panelist_ids: List[str]) -> None:
        """Bulk delete panelists of a round config based on the provided IDs."""
        for panelist_id in panelist_ids:
            panelist = await self.get_panelist_by_round_config_and_panelist_id(
                round_config_id,
                panelist_id
            )

            if not panelist:
                raise DomainError(f"Panelist with ID {panelist_id} not found in round config {round_config_id}", status_code=404)
            
            panelist.is_deleted = True
            # await self.db.delete(panelist)

        await self.db.flush()
        
    async def get_panelist_by_id(
        self,
        panelist_id: str,
        exclude_deleted: bool = True
    ) -> Optional[Panelist]:

        stmt = select(Panelist).where(Panelist.id == panelist_id)

        if exclude_deleted:
            stmt = stmt.where(Panelist.is_deleted.is_(False))

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_panelist_by_job_id(
        self,
        job_id: str,
        exclude_deleted: bool = True
    ) -> list[Panelist]:
        
        stmt = (select(Panelist)
            .join(Interview_Round_Configs)
            .where(Interview_Round_Configs.job_id == job_id))
        
        if exclude_deleted:
            stmt = stmt.where(Panelist.is_deleted.is_(False))

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_panelist_by_round_config_and_email(
        self,
        round_config_id: str,
        panelist_email: EmailStr,
        exclude_deleted: bool = True
    ) -> Optional[Panelist]:

        stmt = (select(Panelist)
            .where(
                Panelist.round_config_id == round_config_id,
                Panelist.email == panelist_email,
            ))
        
        if exclude_deleted:
            stmt = stmt.where(Panelist.is_deleted.is_(False))
        
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_panelist_by_round_config_and_panelist_id(
        self,
        round_config_id: str,
        panelist_id: str,
        exclude_deleted: bool = True
    ) -> Optional[Panelist]:

        stmt = (select(Panelist)
            .where(
                Panelist.round_config_id == round_config_id,
                Panelist.id == panelist_id,
            ))
        if exclude_deleted:
            stmt = stmt.where(Panelist.is_deleted.is_(False))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()



    async def get_panelists_by_round_config_and_panelist_ids(
        self,
        round_config_id: str,
        panelist_ids: list[str],
        exclude_deleted: bool = True
    ) -> list[Panelist]:

        stmt = (select(Panelist)
            .where(
                Panelist.round_config_id == round_config_id,
                Panelist.id.in_(panelist_ids),
            ))
        
        if exclude_deleted:
            stmt = stmt.where(Panelist.is_deleted.is_(False))
        result = await self.db.execute(stmt)
        return result.scalars().all()


    async def get_all_panelists_by_round_config_id(
        self,
        round_config_id: str,
        exclude_deleted: bool = True
    ) -> List[Panelist]:
        """Get all panelists for a round config."""
        stmt = ( select(Panelist).where(Panelist.round_config_id == round_config_id))
        
        if exclude_deleted:
            stmt = stmt.where(Panelist.is_deleted.is_(False))
        
        result = await self.db.execute(stmt)
        return result.scalars().all()


    async def get_all_panelists_by_round_config_id_and_status(
        self,
        round_config_id: str,
        status:PanelistResponseStatus,
        exclude_deleted: bool = True
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
        status:PanelistResponseStatus,
        exclude_deleted: bool = True
        
    ) -> List[Panelist]:
        
        """Get all panelists for a round config who are not with the given status."""

        stmt = select(Panelist).where(Panelist.round_config_id == round_config_id,Panelist.response_status != status)
       
        if exclude_deleted:
            stmt = stmt.where(Panelist.is_deleted.is_(False))
       
        result = await self.db.execute(stmt)
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
    
    
    async def update_panelists_for_round_config(
        self,
        round_config_id: str,
        panelist_data_list: List[updatePanelistLists]
    ) -> List[Panelist]:
        
        # print("\n\nIncoming panelist data:", panelist_data_list,"\n\n")
        # 1. Fetch existing panelists
        existing_panelists = await self.get_all_panelists_by_round_config_id(round_config_id)
        existing_map = {p.email: p for p in existing_panelists}

        incoming_emails = set()
        updated_panelists = []

        # 2. Upsert logic
        for panel_data in panelist_data_list:
            email = panel_data.email
            incoming_emails.add(email)

            if email in existing_map:
                # ✅ UPDATE
                panelist = existing_map[email]
                panelist.name = panel_data.name
                panelist.role = panel_data.role
            else:
                # ✅ INSERT
                panelist = Panelist(
                    round_config_id=round_config_id,
                    name=panel_data.name,
                    email=email,
                    role=panel_data.role
                )
                self.db.add(panelist)

            updated_panelists.append(panelist)

        # 3. DELETE removed panelists (important 🔥)
        for email, panelist in existing_map.items():
            if email not in incoming_emails:
                await self.db.delete(panelist)

        # 4. Flush once
        await self.db.flush()

        return updated_panelists
    
  