from logging import Logger
from arq import Retry
from arq.connections import ArqRedis
from src.schemas.user_schemas import CandidateInfoSchema
from src.services.candidate_service import CandidateService_ForWorker
from async_workers.context_manager import job_context


async def extract_candidate_worker(ctx, payload: dict, **kwargs):
    """
    ARQ worker: Extract candidate information from resume.
    Uses per-job DB session via job_context for proper isolation.
    """
    redis: ArqRedis = ctx["redis"]
    logger: Logger = ctx["logger"]

    redis_job_id = payload.get("redis_job_id")
    resume_id = payload.get("resume_id")
    candidate = payload.get("candidate")
    job_try = ctx.get("job_try", 1)
    max_tries = 3  # enforced by func() in WorkerSettings

    # Hard guard — avoid retry storms on invalid payloads
    if not redis_job_id or not resume_id:
        logger.error(
            f"Invalid payload in extract_candidate: "
            f"redis_job_id={redis_job_id}, resume_id={resume_id}"
        )
        return  # intentional early return, don't retry invalid payloads

    candidate_obj = CandidateInfoSchema(**candidate) if candidate else None

    await redis.hset(f"job:{redis_job_id}", mapping={"status": "processing"})

    try:
        async with job_context(ctx) as deps:
            candidate_service: CandidateService_ForWorker = deps["candidate_service"]

            await candidate_service.extract_candidate(
                resume_id=resume_id,
                candidate_info=candidate_obj,
            )

        await redis.hset(f"job:{redis_job_id}", mapping={"status": "completed"})

    except Exception as e:
        logger.exception(
            f"Candidate extraction failed for "
            f"resume_id={resume_id}, redis_job_id={redis_job_id}"
        )

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