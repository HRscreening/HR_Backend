from workers.connection import redis_conn
from src.services.resume_services import (
    score_resumes_service_sync,
    mark_fail_job
)
import json
from sqlalchemy.orm import configure_mappers
configure_mappers()


def score_resumes_batch(payload: dict):
    redis_job_id = payload["redis_job_id"]
    batch_id = payload["batch_id"]

    try:
        redis_conn.hset(
            f"job:{redis_job_id}",
            mapping={"status": "processing"}
        )

        batch_meta = redis_conn.hgetall(f"batch:{batch_id}")
        if not batch_meta:
            raise RuntimeError(f"Batch {batch_id} not found")

        db_job_id = batch_meta[b"job_id"].decode()

        resume_ids = [
            rid.decode("utf-8")
            for rid in redis_conn.lrange(f"batch:{batch_id}:resumes", 0, -1)
        ]

        if not resume_ids:
            raise RuntimeError(f"No resumes found for batch {batch_id}")

        score_resumes_service_sync(
            db_job_id=db_job_id,
            resume_ids=resume_ids,
            batch_id=batch_id,
            redis_job_id=redis_job_id
        )

        redis_conn.hset(
            f"job:{redis_job_id}",
            mapping={"status": "completed"}
        )

        redis_conn.hset(
            f"batch:{batch_id}",
            mapping={"status": "completed"}
        )

    except Exception as e:
        redis_conn.hset(
            f"job:{redis_job_id}",
            mapping={"status": "failed", "error": str(e)}
        )
        redis_conn.hset(
            f"batch:{batch_id}",
            mapping={"status": "failed"}
        )
        raise
