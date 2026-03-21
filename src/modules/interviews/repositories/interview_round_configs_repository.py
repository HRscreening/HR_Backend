from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Interview_Round_Configs,Panelist

from typing import Optional,List
from src.modules.interviews.dtos.interview_round_config_dto import CreateInterviewRoundConfigDTO, UpdateInterviewRoundConfigDTO


class InterviewRoundConfigsRepository:
    def __init__(self,db: AsyncSession):
        self.db = db
    
    async def create_interview_round_config(self, job_id: str, config_data: CreateInterviewRoundConfigDTO) -> Interview_Round_Configs:
        interview_round_config = Interview_Round_Configs(
            job_id=job_id,
            round_number=config_data.round_number,
            title=config_data.title,
            interview_type=config_data.interview_type,
            instructions=config_data.instructions,
            duration_minutes=config_data.duration_minutes,
            panelists=[panel.model_dump() for panel in config_data.panelists],
            meet_link=str(config_data.meet_link) if config_data.meet_link else None,
            start_date=config_data.start_date,
            end_date=config_data.end_date,
            timezone=config_data.timezone,
        )
        self.db.add(interview_round_config)
        await self.db.flush() 
        return interview_round_config

    # async def bulk_create_interview_round_configs(
    #     self,
    #     job_id: str,
    #     configs: List[CreateInterviewRoundConfigDTO],
    # ) -> List[Interview_Round_Configs]:

    #     created = []
        
    #     panelist_ids_mapped_to_round_config = []

    #     for config_data in configs:

    #         row = Interview_Round_Configs(
    #             job_id=job_id,
    #             round_number=config_data.round_number,
    #             title=config_data.title,
    #             interview_type=config_data.interview_type,
    #             instructions=config_data.instructions,
    #             duration_minutes=config_data.duration_minutes,
    #             meet_link=str(config_data.meet_link) if config_data.meet_link else None,
    #             start_date=config_data.start_date,
    #             end_date=config_data.end_date,
    #             timezone=config_data.timezone,
    #         )

    #         # attach panelists
    #         for panel in config_data.panelists:
    #             panelist = Panelist(
    #                 name=panel.name,
    #                 email=panel.email,
    #                 role=panel.role
    #             )

    #             row.panelists.append(panelist)

    #         self.db.add(row)
    #         created.append(row)
            


    #     await self.db.flush(objects=created)
        
    #     for config, created_row in zip(configs, created):
    #         panelist_ids_mapped_to_round_config.append({
    #             "round_config_id": created_row.id,
    #             "round_config_title": created_row.title,
    #             "panelist_ids":[panel.id for panel in created_row.panelists]})
        
    #     return created
    
    async def bulk_create_interview_round_configs(
        self,
        job_id: str,
        configs: List[CreateInterviewRoundConfigDTO],
    ) -> List[Interview_Round_Configs]:

        created = []
        panelist_ids_mapped_to_round_config = []

        for config_data in configs:
            row = Interview_Round_Configs(
                job_id=job_id,
                round_number=config_data.round_number,
                title=config_data.title,
                interview_type=config_data.interview_type,
                instructions=config_data.instructions,
                duration_minutes=config_data.duration_minutes,
                meet_link=config_data.meet_link,
                start_date=config_data.start_date,
                end_date=config_data.end_date,
                timezone=config_data.timezone,
            )

            for panel in config_data.panelists:
                panelist = Panelist(
                    name=panel.name,
                    email=panel.email,
                    role=panel.role
                )
                row.panelists.append(panelist)

            self.db.add(row)
            created.append(row)

        await self.db.flush()

        for config, created_row in zip(configs, created):
            panelist_ids_mapped_to_round_config.append({
                "round_config_id": created_row.id,
                "round_config_title": created_row.title,
                "panelist_ids": [panel.id for panel in created_row.panelists]
            })

        return created  # or return both if needed
    
    
    async def get_interview_round_config_by_id_with_panelist(
            self,
            round_config_id: str
        ) -> Optional[Interview_Round_Configs]:

            result = await self.db.execute(
                select(Interview_Round_Configs)
                .options(
                    selectinload(Interview_Round_Configs.panelists).load_only(
                        Panelist.name,
                        Panelist.email,
                        Panelist.role
                    )
                )
                .where(Interview_Round_Configs.id == round_config_id)
            )

            return result.scalar_one_or_none()

    
    async def get_interview_round_config_by_id(self, round_config_id: str) -> Optional[Interview_Round_Configs]:
        result = await self.db.execute(
            select(Interview_Round_Configs).where(Interview_Round_Configs.id == round_config_id)
        )
        return result.scalar_one_or_none()

    
    async def get_interview_round_configs_by_job(self, job_id: str) -> List[Interview_Round_Configs]:
        result = await self.db.execute(
            select(Interview_Round_Configs).where(Interview_Round_Configs.job_id == job_id).order_by(Interview_Round_Configs.round_number)  
        )
        
        return result.scalars().all()
    
    async def get_interview_round_configs_by_job_with_panelist_count(
        self,
        job_id: str
        ):

        stmt = (
            select(
                Interview_Round_Configs.id,
                Interview_Round_Configs.round_number,
                Interview_Round_Configs.title,
                Interview_Round_Configs.start_date,
                Interview_Round_Configs.end_date,
                Interview_Round_Configs.slots_available,
                Interview_Round_Configs.interview_type,
                func.count(Panelist.id).label("panelists_count")
            )
            .outerjoin(Panelist, Panelist.round_config_id == Interview_Round_Configs.id)
            .where(Interview_Round_Configs.job_id == job_id)
            .group_by(Interview_Round_Configs.id)
            .order_by(Interview_Round_Configs.round_number)
        )

        result = await self.db.execute(stmt)

        return result.all()
    
    async def get_interview_round_config_by_job_and_round(self, job_id: str, round_number: int) -> Optional[Interview_Round_Configs]:
        result = await self.db.execute(
            select(Interview_Round_Configs).where(
                Interview_Round_Configs.job_id == job_id,
                Interview_Round_Configs.round_number == round_number
            )
        )
        return result.scalar_one_or_none()
    
    async def get_available_round_config_by_job(self,job_id: str) -> List[Interview_Round_Configs]:
        result = await self.db.execute(
            select(Interview_Round_Configs).where(
                Interview_Round_Configs.job_id == job_id,
            ).order_by(Interview_Round_Configs.round_number.asc())
        )
        return result.scalars().all()
    
    

    async def delete_interview_round_config(self,round_config_id):
        result = await self.db.execute(
            select(Interview_Round_Configs).where(Interview_Round_Configs.id == round_config_id)
        )
        config = result.scalar_one_or_none()

        if config:
            await self.db.delete(config)
            await self.db.flush()
            return True
        return False