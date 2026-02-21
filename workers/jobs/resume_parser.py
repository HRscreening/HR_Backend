import os
from logging import Logger
from arq import Retry
from arq.connections import ArqRedis
from workers.context_manager import job_context

from src.services.resume_services import ResumeService_ForWorker
from src.services.batch_service import BatchService_ForWorker

from workers.jobs.utils import increment_and_check_batch, release_finalize_lock


async def parse_resume_worker(ctx, payload: dict, **kwargs):
    redis: ArqRedis = ctx["redis"]
    logger: Logger = ctx["logger"]

    redis_job_id = payload["redis_job_id"]
    batch_id = payload["batch_id"]
    file_path = payload["file_path"]
    job_try = ctx.get("job_try", 1)
    max_tries = 3  # enforced by func() in WorkerSettings

    logger.info(
        f"file={file_path} batch={batch_id} "
        f"try={job_try}/{max_tries} redis_job={redis_job_id}"
    )

    async with job_context(ctx) as deps:
        resume_service: ResumeService_ForWorker = deps["resume_service"]
        batch_service: BatchService_ForWorker = deps["batch_service"]

        await redis.hset(f"job:{redis_job_id}", mapping={"status": "processing"})

        try:
            await resume_service.parse_resume(
                file_path=file_path,
                batch_id=batch_id,
            )

            await redis.hset(f"job:{redis_job_id}", mapping={"status": "completed"})
            should_finalize = await increment_and_check_batch(redis, batch_id, "completed")

        except Exception as e:
            logger.exception(f"Resume parsing failed for job {redis_job_id}")

            # Not the final attempt → Retry with backoff, don't touch counters
            if job_try < max_tries:
                await redis.hset(
                    f"job:{redis_job_id}",
                    mapping={
                        "status": "retrying",
                        "last_error": str(e),
                        "attempt": str(job_try),
                    },
                )
                raise Retry(defer=job_try * 5)  # 5s, 10s backoff

            # Final failure — count it
            await redis.hset(
                f"job:{redis_job_id}",
                mapping={"status": "failed", "error": str(e)},
            )
            await batch_service.mark_fail_job(
                batch_id=batch_id,
                file_name=os.path.basename(file_path),
                reason=str(e),
            )
            should_finalize = await increment_and_check_batch(redis, batch_id, "failed")

        # Only the one winner of the Lua lock finalizes
        if should_finalize:
            try:
                await batch_service.finalize_batch_parsed(batch_id)
            except Exception:
                await release_finalize_lock(redis, batch_id)
                raise