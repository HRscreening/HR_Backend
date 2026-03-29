# app/workers/producer.py

import os
import uuid
from typing import List
from workers.connection import QUEUES, redis_conn
from configs.log_config import get_logger
from rq import Retry
from src.utils.chunk_generator import chunk_list
from src.schemas.user_schemas import CandidateInfoSchema


logger = get_logger("producer")

SCORING_BATCH_SIZE = int(os.environ.get("SCORING_BATCH_SIZE", "5"))
SCORING_MAX_CONCURRENCY = int(os.environ.get("SCORING_MAX_CONCURRENCY", "3"))


# =========================
# Public Producer API
# =========================
def enqueue_resumes_parsing(
    storage_paths: List[str],
    db_job_id: str,        # Postgres Job.id
    batch_id: str,         # Postgres BulkUploadBatches.id
    queue_name: str = "resume_parsing"
) -> str:
    """
    Enqueue one parsing task per resume.
    storage_paths: Supabase storage paths (e.g. "resumes/job_id/filename.pdf").
    Files are already uploaded to Supabase — workers download from there, not local disk.
    """
    if queue_name not in QUEUES:
        raise ValueError(f"Invalid queue: {queue_name}")

    queue = QUEUES[queue_name]
    total = len(storage_paths)
    logger.info(
        f"[ENQUEUE] batch={batch_id} job={db_job_id} total_files={total} "
        f"files={[os.path.basename(p) for p in storage_paths]}"
    )

    for idx, storage_path in enumerate(storage_paths):
        redis_job_id = str(uuid.uuid4())
        try:
            queue.enqueue(
                "workers.tasks.resume_parser.parse_resume",
                {
                    "redis_job_id": redis_job_id,
                    "batch_id": str(batch_id),
                    "storage_path": storage_path,
                },
                job_timeout=300,  # 5 min per PDF hard kill
            )
            logger.info(
                f"[ENQUEUE] {idx + 1}/{total} queued: "
                f"{os.path.basename(storage_path)} redis_job={redis_job_id}"
            )
        except Exception as e:
            logger.error(f"[ENQUEUE] Failed to enqueue {storage_path}: {e}")

    return batch_id





def enqueue_pre_screen_and_score(
    job_id: str,
    resume_ids: list[str],
    upload_batch_id: str = "",
    queue_name: str = "resume_scoring",
) -> str:
    """
    Enqueue a single pre-screening + scoring pipeline task for ALL resumes.

    Pipeline v2 flow:
      Stage 1: Quality Gate (structural checks, <1s, free)
      Stage 2: Cross-Encoder relevance scoring (~6s, free)
      Stage 3: LLM scoring on selected top-N (~20s, ~$0.10)

    Returns the batch_id for progress tracking.
    """
    if queue_name not in QUEUES:
        raise ValueError(f"Invalid queue: {queue_name}")

    queue = QUEUES[queue_name]
    redis_job_id = str(uuid.uuid4())
    batch_id = str(uuid.uuid4())

    try:
        redis_conn.hset(
            f"batch:{batch_id}",
            mapping={
                "status": "queued",
                "job_id": str(job_id),
                "redis_job_id": redis_job_id,
                "type": "pre_screen_and_score",
                "total_resumes": len(resume_ids),
                "completed": 0,
                "failed": 0,
                "upload_batch_id": upload_batch_id,
            }
        )

        for resume_id in resume_ids:
            redis_conn.rpush(f"batch:{batch_id}:resumes", str(resume_id))

        queue.enqueue(
            "workers.tasks.resume_scorer.pre_screen_and_score_batch",
            {
                "redis_job_id": redis_job_id,
                "batch_id": batch_id,
            },
            retry=Retry(max=2, interval=[15, 60]),
            job_timeout=900,  # 15 min — includes cross-encoder + LLM scoring
        )

        logger.info(
            "[ENQUEUE] pre_screen_and_score batch=%s job=%s resumes=%d",
            batch_id, job_id, len(resume_ids),
        )
        return batch_id

    except Exception as e:
        logger.error(f"Failed to enqueue pre_screen_and_score batch {batch_id}: {e}")
        redis_conn.hset(
            f"batch:{batch_id}",
            mapping={"status": "failed_to_enqueue", "error": str(e)}
        )
        raise


def enqueue_resumes_scoring(
    job_id: str,
    resume_ids: list[str],
    upload_batch_id: str = "",
    queue_name: str = "resume_scoring",
    batch_size: int = SCORING_BATCH_SIZE,
) -> list[str]:
    """Enqueue LLM scoring tasks in chunks (called internally after pre-screening)."""
    if queue_name not in QUEUES:
        raise ValueError(f"Invalid queue: {queue_name}")

    queue = QUEUES[queue_name]
    created_batches = []

    for batch in chunk_list(resume_ids, batch_size):
        redis_job_id = str(uuid.uuid4())
        batch_id = str(uuid.uuid4())

        try:
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
                    "upload_batch_id": upload_batch_id,
                }
            )

            for resume_id in batch:
                redis_conn.rpush(f"batch:{batch_id}:resumes", str(resume_id))

            queue.enqueue(
                "workers.tasks.resume_scorer.score_resumes_batch",
                {
                    "redis_job_id": redis_job_id,
                    "batch_id": batch_id,
                },
                retry=Retry(max=3, interval=[10, 30, 60]),
                job_timeout=600,
            )

            created_batches.append(batch_id)

        except Exception as e:
            logger.error(f"Failed to enqueue batch {batch_id}: {e}")
            redis_conn.hset(
                f"batch:{batch_id}",
                mapping={"status": "failed_to_enqueue", "error": str(e)}
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


def enqueue_jd_extraction(
    job_id: str,
    document_id: str,
    file_path: str,
    queue_name: str = "jd_extraction"
) -> str | None:
    """Enqueue JD extraction + parsing job."""
    if queue_name not in QUEUES:
        raise ValueError(f"Invalid queue: {queue_name}")

    queue = QUEUES[queue_name]
    redis_job_id = str(uuid.uuid4())

    redis_conn.hset(
        f"job:{redis_job_id}",
        mapping={
            "status": "queued",
            "job_id": str(job_id),
            "document_id": str(document_id),
            "file_path": file_path,
            "type": "jd_extraction"
        }
    )

    try:
        queue.enqueue(
            "workers.tasks.jd_parser.parse_jd",
            {
                "redis_job_id": redis_job_id,
                "job_id": str(job_id),
                "document_id": str(document_id),
                "file_path": file_path,
            },
            retry=Retry(max=2, interval=[10, 30])
        )

        logger.info(f"Enqueued JD extraction job {redis_job_id} for job {job_id}")
        return redis_job_id

    except Exception as e:
        logger.error(f"Failed to enqueue JD extraction job {redis_job_id}: {e}")
        redis_conn.hset(
            f"job:{redis_job_id}",
            mapping={
                "status": "failed_to_enqueue",
                "error": str(e)
            }
        )
        return None
