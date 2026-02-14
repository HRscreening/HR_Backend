
from sqlalchemy.ext.asyncio import AsyncSession

from  configs.log_config import get_logger
from sqlalchemy import select,func
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import Resume
from  configs.log_config import get_logger
from typing import Optional,List
from sqlalchemy.orm import Session

class ResumeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = get_logger("RESUME_REPOSITORY")
        
    async def get_resume_by_id(self,resume_id:int)-> Optional[Resume]:
            resume_result = await self.db.execute(
                select(Resume)
                .where(Resume.id == resume_id)
            )
            
            return resume_result.scalar_one_or_none()
        
        
    
    async def commit(self):
        await self.db.commit()

    async def rollback(self):
        await self.db.rollback()


        



# class ResumeRepositoy_Sync:
#     def __init__(self, db: Session):
#         self.db = db
#         self.logger = get_logger("RESUME_REPOSITORY_SYNC")
        
#     async def get_resume_by_id(self,resume_id:int)-> Optional[Resume]:
#             resume_result = await self.db.execute(
#                 select(Resume)
#                 .where(Resume.id == resume_id)
#             )
            
#             return resume_result.scalar_one_or_none()