"""
JD Parser Worker — Extracts and parses JD documents.

Reads JD file, runs generate_rubric_from_jd (single-call rubric pipeline),
writes results to documents.ai_parsed_data and jobs.parsed_jd + jobs.job_metadata.
"""

import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from uuid import UUID

from configs.env_config import DATABASE_URL
from configs.log_config import get_logger
from src.models import Document, Job
from src.models.enums import DocumentProcessingStatus
from src.repositories.document_repository import DocumentRepository
from src.utils.extract_pdf import extract_text_from_pdf
from src.pipelines.generate_rubric import generate_rubric_from_jd
from workers.connection import redis_conn

logger = get_logger("jd_parser_worker")

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _parse_jd_async(job_id: str, document_id: str, file_path: str):
    """Async JD parsing logic."""
    async with AsyncSessionLocal() as db:
        doc_repo = DocumentRepository(db)

        try:
            # 1. Get document
            doc = await doc_repo.get_document(UUID(document_id))
            if not doc:
                logger.error(f"Document {document_id} not found")
                return

            # 2. Update status to parsing_in_progress
            await doc_repo.update_parsing_status(
                UUID(document_id), DocumentProcessingStatus.PARSING_IN_PROGRESS
            )
            await db.commit()

            # 3. Extract text from file
            logger.info(f"Extracting text from JD file: {file_path}")
            # If file_path is a URL, download it first; else read from local storage
            # For now assume file_path is accessible (or use doc.file_url)
            # You may need to fetch from storage first
            jd_text = doc.extracted_text
            if not jd_text:
                # Extract from file (simplified - you may need to download from storage first)
                try:
                    # Placeholder: implement file fetching from storage if needed
                    # For now assume extracted_text is already set during upload
                    raise ValueError("extracted_text not set; implement file fetch from storage")
                except Exception as e:
                    logger.error(f"Failed to extract text: {e}")
                    await doc_repo.update_parsing_status(
                        UUID(document_id),
                        DocumentProcessingStatus.ERROR,
                        error=f"Text extraction failed: {e}",
                    )
                    await db.commit()
                    return

            # 4. Run JD → rubric pipeline
            logger.info(f"Running JD rubric generation for document {document_id}")
            rubric_payload = await generate_rubric_from_jd(jd_text, use_cache=False)

            # 5. Write results to document and job
            await doc_repo.update_parsing_status(
                UUID(document_id),
                DocumentProcessingStatus.PARSED,
                ai_parsed_data=rubric_payload,
            )

            # Update job: parsed_jd and job_metadata
            from sqlalchemy import update
            await db.execute(
                update(Job)
                .where(Job.id == UUID(job_id))
                .values(
                    parsed_jd=rubric_payload,
                    job_metadata={
                        "domain": rubric_payload.get("domain"),
                        "domain_confidence": rubric_payload.get("domain_confidence"),
                    },
                    raw_jd_text=jd_text,
                )
            )

            await db.commit()
            logger.info(f"JD parsing completed for job {job_id}, document {document_id}")

        except Exception as e:
            logger.exception(f"JD parsing failed for document {document_id}: {e}")
            await doc_repo.update_parsing_status(
                UUID(document_id),
                DocumentProcessingStatus.ERROR,
                error=str(e),
            )
            await db.commit()


def parse_jd(payload: dict):
    """RQ worker entry point for JD parsing."""
    redis_job_id = payload.get("redis_job_id")
    job_id = payload.get("job_id")
    document_id = payload.get("document_id")
    file_path = payload.get("file_path")

    logger.info(f"Starting JD parse job {redis_job_id} for job {job_id}")

    try:
        redis_conn.hset(f"job:{redis_job_id}", "status", "processing")

        asyncio.run(_parse_jd_async(job_id, document_id, file_path))

        redis_conn.hset(f"job:{redis_job_id}", mapping={"status": "completed"})
        logger.info(f"JD parse job {redis_job_id} completed")

    except Exception as e:
        logger.exception(f"JD parse job {redis_job_id} failed: {e}")
        redis_conn.hset(
            f"job:{redis_job_id}",
            mapping={"status": "failed", "error": str(e)}
        )
        raise
