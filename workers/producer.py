# app/workers/producer.py

import uuid
from typing import List
from workers.connection import QUEUES, redis_conn
from configs.log_config import get_logger
from rq import Retry
from src.schemas.user_schemas import BatchResumeDataSchema
from src.utils.chunk_generator import  chunk_list
from src.schemas.user_schemas import CandidateInfoSchema


logger = get_logger("producer")


# =========================
# Public Producer API
# =========================
def enqueue_resumes_parsing(
    resume_paths: List[str],
    db_job_id: str,        # Postgres Job.id
    batch_id: str,         # Postgres BulkUploadBatches.id
    queue_name: str = "resume_parsing"
) -> str:

    if queue_name not in QUEUES:
        raise ValueError(f"Invalid queue: {queue_name}")

    queue = QUEUES[queue_name]

    # Redis batch metadata (tracking only)
    redis_conn.hset(
        f"batch:{str(batch_id)}",
        mapping={
            "total": len(resume_paths),
            "completed": 0,
            "failed": 0,
            "status": "queued"
        }
    )

    for path in resume_paths:
        redis_job_id = str(uuid.uuid4())

        # Redis job state
        redis_conn.hset(
            f"job:{redis_job_id}",
            mapping={
                "status": "queued",
                "batch_id": str(batch_id),
                "db_job_id": str(db_job_id),
                "file_path": path,
                "type": "resume_parse"
            }
        )

        try:
            queue.enqueue(
                "workers.tasks.resume_parser.parse_resume",
                {
                    "redis_job_id": str(redis_job_id),
                    "batch_id": str(batch_id),
                    "file_path": path
                },
                retry=Retry(max=3, interval=[10, 30, 60])
            )

        except Exception as e:
            logger.error(f"Failed to enqueue job {redis_job_id}: {e}")
            redis_conn.hset(
                f"job:{str(redis_job_id)}",
                mapping={
                    "status": "failed_to_enqueue",
                    "error": str(e)
                }
            )

    return batch_id





def enqueue_resumes_scoring(
    job_id: str,
    resume_ids: list[str],
    queue_name: str = "resume_scoring",
    batch_size: int = 5
) -> list[str]:

    if queue_name not in QUEUES:
        raise ValueError(f"Invalid queue: {queue_name}")

    queue = QUEUES[queue_name]
    created_batches = []

    for batch in chunk_list(resume_ids, batch_size):
        redis_job_id = str(uuid.uuid4())
        batch_id = str(uuid.uuid4())

        try:
            # Batch metadata
            redis_conn.hset(
                f"batch:{batch_id}",
                mapping={
                    "status": "queued",
                    "job_id": str(job_id),
                    "redis_job_id": redis_job_id,
                    "type": "resume_scoring",
                    "total_resumes": len(batch),
                    "completed": 0,
                    "failed": 0,
                }
            )

            # ✅ Store resume IDs in a LIST (THIS IS THE FIX)
            for resume_id in batch:
                redis_conn.rpush(
                    f"batch:{batch_id}:resumes",
                    str(resume_id)
                )

            queue.enqueue(
                "workers.tasks.resume_scorer.score_resumes_batch",
                {
                    "redis_job_id": redis_job_id,
                    "batch_id": batch_id,
                },
                retry=Retry(max=3, interval=[10, 30, 60])
            )

            created_batches.append(batch_id)

        except Exception as e:
            logger.error(f"Failed to enqueue batch {batch_id}: {e}")
            redis_conn.hset(
                f"batch:{batch_id}",
                mapping={
                    "status": "failed_to_enqueue",
                    "error": str(e)
                }
            )

    return created_batches




def enqueue_candidate_extraction(
    resume_id: str,
    candidate: CandidateInfoSchema | None,
    batch_id: str,
    queue_name: str = "candidate_extraction"
) -> str | None:

    if queue_name not in QUEUES:
        raise ValueError(f"Invalid queue: {queue_name}")

    queue = QUEUES[queue_name]
    redis_job_id = str(uuid.uuid4())

    payload = {
        "redis_job_id": redis_job_id,
        "resume_id": str(resume_id),
        "batch_id": str(batch_id),          # ✅ REQUIRED
        "candidate": (
            candidate.model_dump() if candidate else None
        )
    }

    try:
        queue.enqueue(
            "workers.tasks.candidate_extracter.extract_candidate",
            payload,
            retry=Retry(max=3, interval=[10, 30, 60])
        )

        return redis_job_id

    except Exception as e:
        logger.error(
            f"Failed to enqueue candidate extraction job "
            f"{redis_job_id} for resume_id={resume_id}: {e}"
        )

        redis_conn.hset(
            f"job:{redis_job_id}",
            mapping={
                "status": "failed_to_enqueue",
                "error": str(e),
                "resume_id": str(resume_id),
                "batch_id": str(batch_id),
                "type": "candidate_extraction"
            }
        )

        return None
