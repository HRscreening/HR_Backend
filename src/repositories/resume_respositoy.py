
from sqlalchemy.ext.asyncio import AsyncSession

from  configs.log_config import get_logger
from sqlalchemy import select,func
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import Resume,Application
from  configs.log_config import get_logger
from typing import Optional,List
from sqlalchemy.orm import Session
from src.schemas.resume_schema import ResumeCreateSchema
from src.models.enums import ResumeStatus




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
    
    async def add_resume(self,applicaion_id:str,raw_file_url:str,parsed_text:str,page_count:int,status:ResumeStatus) -> Resume:
        resume = Resume(
            application_id=applicaion_id,
            raw_file_url=raw_file_url,
            parsed_text=parsed_text,
            page_count=page_count,
            status=status
        )
        
        self.db.add(resume)
        await self.db.flush()  # to get the ID populated
        return resume
    
    
    # --------------------------  Worker specific methods --------------------------

    # In repository — remove the commit, just flush
    async def lock_and_mark_parsed_resumes_for_scoring(self, job_id: str) -> list[str]:
        stmt = (
            select(Resume)
            .join(Application, Resume.application_id == Application.id)
            .where(
                Application.job_id == job_id,
                Resume.status == ResumeStatus.PARSED,
            )
            .with_for_update(skip_locked=True)
        )
        result = await self.db.execute(stmt)
        resumes = result.scalars().all()

        for resume in resumes:
            resume.status = ResumeStatus.QUEUED_FOR_SCORING

        await self.db.flush()  # ← not commit
        return [resume.id for resume in resumes]
    
    
    
    async def fetch_resumes_for_scoring(
        self,
        job_id: str,
        status: ResumeStatus,
        new_status: ResumeStatus,
        resume_ids: list[str],
    ) -> list[Resume]:

        if not resume_ids:
            return []

        stmt = (
            select(Resume)
            .join(Application, Resume.application_id == Application.id)
            .where(
                Application.job_id == job_id,
                Resume.id.in_(resume_ids),
                Resume.status == status,
            )
            .with_for_update()
        )

        result = await self.db.execute(stmt)
        resumes = result.scalars().all()

        # 🔒 Transition to SCORING immediately
        for r in resumes:
            r.status = new_status

        return resumes


    async def update_resume_status(self,resume_ids:List[str],new_status: ResumeStatus):
        stmt = (
            select(Resume)
            .where(Resume.id.in_(resume_ids))
            .with_for_update()
        )
        
        result = await self.db.execute(stmt)
        resumes = result.scalars().all()
        
        for r in resumes:
            r.status = new_status
            
        await self.db.flush()
        return resumes

    async def get_resumes_by_ids(self, resume_ids: List[str]) -> List[Resume]:
        """Fetch resumes by IDs without any status filter or locking."""
        if not resume_ids:
            return []

        stmt = select(Resume).where(Resume.id.in_(resume_ids))
        result = await self.db.execute(stmt)
        return result.scalars().all()
        
    
    
        




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