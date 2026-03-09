import logging

from workers.connection import redis_conn
from src.services.resume_services import (
    score_resumes_service_sync,
    mark_fail_job
)
import json

logger = logging.getLogger(__name__)


def _update_scoring_progress(
    upload_batch_id: str,
    scored_count: int = 0,
    failed_count: int = 0,
):
    """Update BulkUploadBatches scoring progress in Postgres."""
    from configs.postgress_db import get_sync_db
    from src.models import BulkUploadBatches
    from src.models.enums import BulkUploadStatus
    from sqlalchemy import select

    with get_sync_db() as db:
        batch = db.execute(
            select(BulkUploadBatches)
            .where(BulkUploadBatches.id == upload_batch_id)
            .with_for_update()
        ).scalar_one_or_none()

        if not batch:
            return

        batch.scoring_completed += scored_count
        batch.scoring_failed += failed_count

        if batch.scoring_completed + batch.scoring_failed >= batch.scoring_total:
            batch.scoring_status = BulkUploadStatus.COMPLETED

        db.commit()


def score_resumes_batch(payload: dict):
    # configure_mappers() must run AFTER fork (not at module level) so SQLAlchemy
    # mapper init happens in the child process only, avoiding fork-safety issues
    # with C extensions on macOS / Linux.
    from sqlalchemy.orm import configure_mappers
    configure_mappers()

    redis_job_id = payload["redis_job_id"]
    batch_id = payload["batch_id"]
    upload_batch_id = ""
    resume_ids = []

    try:
        redis_conn.hset(
            f"job:{redis_job_id}",
            mapping={"status": "processing"}
        )

        batch_meta = redis_conn.hgetall(f"batch:{batch_id}")
        if not batch_meta:
            raise RuntimeError(f"Batch {batch_id} not found")

        db_job_id = batch_meta[b"job_id"].decode()
        upload_batch_id = batch_meta.get(b"upload_batch_id", b"").decode() or ""

        resume_ids = [
            rid.decode("utf-8")
            for rid in redis_conn.lrange(f"batch:{batch_id}:resumes", 0, -1)
        ]

        if not resume_ids:
            raise RuntimeError(f"No resumes found for batch {batch_id}")

        result = score_resumes_service_sync(
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

        # Update Postgres batch scoring progress — track both successes AND
        # individual LLM failures (which are skipped silently in scoring service)
        if upload_batch_id:
            scored_count = result.get("scored_count", 0)
            failed_count = result.get("failed_count", 0)
            # If no counts returned, fall back to treating all as scored
            if scored_count == 0 and failed_count == 0:
                scored_count = len(resume_ids)
            _update_scoring_progress(
                upload_batch_id,
                scored_count=scored_count,
                failed_count=failed_count,
            )

    except Exception as e:
        logger.error(
            f"[SCORER FAIL] batch={batch_id} redis_job={redis_job_id} error={e!r}"
        )

        redis_conn.hset(
            f"job:{redis_job_id}",
            mapping={"status": "failed", "error": str(e)[:500]}
        )
        redis_conn.hset(
            f"batch:{batch_id}",
            mapping={"status": "failed"}
        )

        # Track failed scoring in Postgres — use idempotent SETNX to prevent
        # double-counting on RQ retries (same pattern as resume_parser)
        if upload_batch_id and resume_ids:
            fail_counted_key = f"scoring_batch:{batch_id}:fail_counted"
            already_counted = not redis_conn.set(fail_counted_key, "1", ex=86400, nx=True)
            if not already_counted:
                _update_scoring_progress(
                    upload_batch_id,
                    failed_count=len(resume_ids),
                )
            else:
                logger.info(
                    f"[SCORER FAIL] batch={batch_id} already counted as failed — "
                    f"skipping DB increment (this is a retry)"
                )

        raise
