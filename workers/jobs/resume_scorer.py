import os
from logging import Logger
from arq import Retry
from arq.connections import ArqRedis
from workers.jobs.utils import get_batch_payload
from workers.context_manager import job_context
from src.services.resume_services import ResumeService_ForWorker


async def score_resumes_text_batch(ctx, payload: dict, **kwargs):
    redis: ArqRedis = ctx["redis"]
    logger: Logger = ctx["logger"]

    redis_job_id = payload["redis_job_id"]
    redis_batch_id = payload["batch_id"]
    job_try = ctx.get("job_try", 1)
    max_tries = 3  # enforced by func() in WorkerSettings

    await redis.hset(f"job:{redis_job_id}", mapping={"status": "processing"})

    try:
        db_job_id, resume_ids, db_batch_id = await get_batch_payload(
            redis, redis_batch_id
        )

        async with job_context(ctx) as deps:
            resume_service: ResumeService_ForWorker = deps["resume_service"]

            await resume_service.score_parsed_text_resumes(
                db_job_id=db_job_id,
                resume_ids=resume_ids,
                batch_id=db_batch_id,
            )

        await redis.hset(f"job:{redis_job_id}", mapping={"status": "completed"})

    except Exception as e:
        logger.exception(f"Text scoring failed for batch {redis_batch_id}")

        if job_try < max_tries:
            await redis.hset(
                f"job:{redis_job_id}",
                mapping={
                    "status": "retrying",
                    "last_error": str(e),
                    "attempt": str(job_try),
                },
            )
            raise Retry(defer=job_try * 5)

        await redis.hset(
            f"job:{redis_job_id}",
            mapping={"status": "failed", "error": str(e)},
        )
        raise






async def score_resumes_url_batch(ctx, payload: dict, **kwargs):
    redis: ArqRedis = ctx["redis"]
    logger: Logger = ctx["logger"]

    redis_job_id = payload["redis_job_id"]
    redis_batch_id = payload["batch_id"]
    job_try = ctx.get("job_try", 1)
    max_tries = 3  # enforced by func() in WorkerSettings

    await redis.hset(f"job:{redis_job_id}", mapping={"status": "processing"})

    try:
        db_job_id, resume_ids, db_batch_id = await get_batch_payload(
            redis, redis_batch_id
        )

        async with job_context(ctx) as deps:
            resume_service: ResumeService_ForWorker = deps["resume_service"]

            await resume_service.score_url_resumes(
                db_job_id=db_job_id,
                resume_ids=resume_ids,
                batch_id=db_batch_id,
            )

        await redis.hset(f"job:{redis_job_id}", mapping={"status": "completed"})

    except Exception as e:
        logger.exception(f"URL scoring failed for batch {redis_batch_id}")

        if job_try < max_tries:
            await redis.hset(
                f"job:{redis_job_id}",
                mapping={
                    "status": "retrying",
                    "last_error": str(e),
                    "attempt": str(job_try),
                },
            )
            raise Retry(defer=job_try * 5)

        await redis.hset(
            f"job:{redis_job_id}",
            mapping={"status": "failed", "error": str(e)},
        )
        raise