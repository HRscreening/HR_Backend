from sqlalchemy.ext.asyncio import AsyncSession
from arq.connections import ArqRedis

from configs.postgress_db import async_session_maker
from workers.connection import get_redis_pool
from workers.new_producer import ARQProducer

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

# async def on_startup(ctx: dict):
#     """
#     Initialize resources when worker starts.

#     Stored in ctx and reused by all jobs.
#     """

#     logger = get_logger("WORKER")

#     # 🔹 Redis pool
#     redis: ArqRedis = await get_redis_pool()

#     # 🔹 DB session (one per worker process)
#     db: AsyncSession = async_session_maker

#     # 🔹 Producer (for enqueueing other jobs)
#     producer = ARQProducer(redis)

#     # 🔹 Repositories
#     job_repo = JobRepository(db)
#     resume_repo = ResumeRepository(db)
#     application_repo = ApplicationRepository(db)
#     batch_repo = BatchRepository(db)
#     score_repo = ScoreRepository(db)
#     document_repo = DocumentRepository(db)
#     candidate_repo = CandidateRepository(db) 


#     resume_service = ResumeService_ForWorker(db=db, resume_repository=resume_repo, score_repository=score_repo,
#                                     job_producer=producer,
#                                    application_repository=application_repo,
#                                    batch_repository=batch_repo,
#                                    document_repository=document_repo,
#                                    job_repository=job_repo,      
#                                    )
#     candidate_service = CandidateService(db=db, candidate_repository=candidate_repo, application_repository=application_repo)
    
#     batch_service = BatchService_ForWorker(db=db, batch_repository=batch_repo,resume_repository=resume_repo,job_producer=producer)
    
    
#     ctx.update({
#         "logger": logger,
#         "redis": redis,
#         "db": db,

#         # services
#         "resume_service": resume_service,
#         "candidate_service": candidate_service,
#         "batch_service": batch_service,
#     })
    
    


#     logger.info("Worker dependencies initialized")


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
