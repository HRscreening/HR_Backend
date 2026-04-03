from sqlalchemy.ext.asyncio import AsyncSession
from arq.connections import ArqRedis

from configs.postgress_db import async_session_maker
from async_workers.connection import get_redis_pool
from async_workers.producer import ARQProducer

# Repositories
from src.repositories.job_repository import JobRepository
from src.repositories.resume_respositoy import ResumeRepository
from src.repositories.application_repository import ApplicationRepository
from src.repositories.batch_repositoy import BatchRepository
from src.repositories.score_repository import ScoreRepository
from src.repositories.document_repository import DocumentRepository
from src.repositories.candidiate_repository import CandidateRepository

from src.services.resume_services import ResumeService_ForWorker
from src.services.candidate_service import CandidateService
from src.services.batch_service import BatchService_ForWorker

from configs.log_config import get_logger


# =========================================================
# ARQ STARTUP
# =========================================================

async def on_startup(ctx: dict):

    logger = get_logger("WORKER")
    redis: ArqRedis = await get_redis_pool()

    ctx.update({
        "logger": logger,
        "redis": redis,
        "db_sessionmaker": async_session_maker,  # ✅ factory only
    })

    logger.info("Worker dependencies initialized")


# =========================================================
# ARQ SHUTDOWN
# =========================================================

async def on_shutdown(ctx: dict):
    """
    Cleanup resources when worker stops.
    """

    logger = ctx.get("logger")
    redis: ArqRedis = ctx.get("redis")

    if redis:
        await redis.aclose()

    if logger:
        logger.info("Worker shutdown complete")
