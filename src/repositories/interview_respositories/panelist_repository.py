from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Panelist_Availability
from pydantic import EmailStr
from typing import Optional,List
from src.dtos.interviews_dtos.panel_dto import CreatePanelDTO



class PanelistRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_panelists(
        self,
        round_config_id: str,
        interview_id: str,
        panel_data_list: list[CreatePanelDTO],
    ) -> list[Panelist_Availability]:
        """Create panelist availability records."""

        panelists = [
            Panelist_Availability(
                round_config_id=round_config_id,
                interview_id=interview_id,
                panelist_name=p.panelist_name,
                panelist_email=p.panelist_email,
                availability_token=p.availability_token,
                token_expires_at=p.token_expires_at,
            )
            for p in panel_data_list
        ]

        self.db.add_all(panelists)
        await self.db.flush()

        return panelists

    async def get_panelist_availability_by_id(
        self,
        panelist_id: str,
    ) -> Optional[Panelist_Availability]:

        result = await self.db.execute(
            select(Panelist_Availability)
            .where(Panelist_Availability.id == panelist_id)
        )

        return result.scalar_one_or_none()



    async def get_panelist_by_round_config_and_email(
        self,
        round_config_id: str,
        panelist_email: EmailStr,
    ) -> Optional[Panelist_Availability]:

        result = await self.db.execute(
            select(Panelist_Availability)
            .where(
                Panelist_Availability.round_config_id == round_config_id,
                Panelist_Availability.panelist_email == panelist_email,
            )
        )

        return result.scalar_one_or_none()



    async def get_all_panelists_by_round_config_id(
        self,
        round_config_id: str,
    ) -> List[Panelist_Availability]:

        result = await self.db.execute(
            select(Panelist_Availability)
            .where(Panelist_Availability.round_config_id == round_config_id)
        )

        return result.scalars().all()