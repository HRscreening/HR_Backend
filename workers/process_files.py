from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from configs.postgress_db import async_session_maker
from models.enums import ApplicationProcessingStage
from configs.log_config import get_logger
from utils.manage_supabase_buckets import supabase_file_handler
from typing import List
import os
from utils.extract_pdf import extract_text_from_pdf
from models import Resume,Application
# from supabase.types import SupabaseResponse

from sqlalchemy import select,func




log = get_logger("BackgroundWorker:ProcessFiles")

# async def run_application_processing(processing_job_id: UUID) -> None:
from typing import List
import os
import aiofiles
from uuid import UUID
import os
from typing import List
from PyPDF2 import PdfReader

async def run_application_processing(file_paths: List[str]) -> None:
    async with async_session_maker() as db:
        try:
            log.info(
                "Starting application processing for %d files",
                len(file_paths)
            )

            job_id = UUID("62747f6b-3cde-45bc-b855-901d0adf4059")

            for file_path in file_paths:
                # filename = os.path.basename(file_path)

                # Extract PDF data
                reader = PdfReader(file_path)
                pages = len(reader.pages)
                text = extract_text_from_pdf(file_path)

                # Create application
                new_application = Application(
                    job_id=job_id,
                    candidate_id=None
                )
                db.add(new_application)
                await db.flush() 

                # Create resume
                new_resume = Resume(
                    application_id=new_application.id,
                    raw_file_url="temp/path.pdf",  # TODO: replace with actual upload path
                    parsed_text=text,
                    page_count=pages,
                    application=new_application
                )

                db.add(new_resume)

            # ✅ One commit after everything succeeds
            await db.commit()

            log.info("Application processing completed successfully")

        except Exception:
            await db.rollback()
            log.exception("Application processing failed")
            raise
