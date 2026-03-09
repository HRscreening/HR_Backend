"""
Resume Parser Worker — parses PDF/DOCX resumes and enqueues scoring when batch completes.

Production-grade timeout: uses thread-based timeout (not SIGALRM) so blocking I/O
(Gemini HTTP, pdfplumber, file ops) can be interrupted. SIGALRM doesn't reliably
interrupt syscalls, causing one stuck PDF to block the entire batch.
"""
import logging
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

from workers.connection import redis_conn
from src.services.resume_services import parse_resume_service, finalize_batch_parsed, mark_fail_job

logger = logging.getLogger(__name__)

PARSE_TIMEOUT_SEC = int(os.environ.get("RESUME_PARSE_TIMEOUT", "240"))  # 4 min per PDF


def _run_parse(storage_path: str, batch_id: str, redis_job_id: str | None):
    """Run parse in a thread — allows timeout to interrupt blocking I/O (Gemini HTTP, download)."""
    parse_resume_service(
        storage_path=storage_path,
        batch_id=batch_id,
        redis_job_id=redis_job_id,
    )


def parse_resume(payload: dict):
    # Extract payload INSIDE try so KeyError/bad-payload still updates failed_count.
    # Previously this was outside try, so crashes here left the batch stuck forever.
    batch_id = None
    file_name = "unknown"
    redis_job_id = None

    try:
        redis_job_id = str(payload["redis_job_id"])
        batch_id = str(payload["batch_id"])
        storage_path = payload["storage_path"]
        file_name = os.path.basename(storage_path)

        logger.info(f"[PARSE START] file={file_name} redis_job={redis_job_id} batch={batch_id} (timeout={PARSE_TIMEOUT_SEC}s)")
        redis_conn.hset(f"job:{redis_job_id}", mapping={"status": "processing"})

        # Thread-based timeout — interrupts blocking I/O (Gemini HTTP, Supabase download).
        # SIGALRM doesn't interrupt syscalls; ThreadPoolExecutor.result(timeout=) does.
        # CRITICAL: do NOT use `with ThreadPoolExecutor` — its __exit__ calls shutdown(wait=True)
        # which blocks until the hung thread finishes, completely defeating the timeout.
        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(_run_parse, storage_path, batch_id, redis_job_id)
        try:
            future.result(timeout=PARSE_TIMEOUT_SEC)
            pool.shutdown(wait=False)
        except FuturesTimeout:
            pool.shutdown(wait=False)
            raise TimeoutError(f"PDF parsing timed out after {PARSE_TIMEOUT_SEC}s: {file_name}")

        redis_conn.hset(f"job:{redis_job_id}", mapping={"status": "completed"})
        logger.info(f"[PARSE OK] file={file_name} redis_job={redis_job_id}")

    except Exception as e:
        logger.error(f"[PARSE FAIL] file={file_name} redis_job={redis_job_id} error={e!r}")
        if redis_job_id:
            redis_conn.hset(
                f"job:{redis_job_id}",
                mapping={"status": "failed", "error": str(e)[:500]}
            )

        # SETNX guard: only increment DB failed_count ONCE per file across all retries.
        if batch_id:
            fail_counted_key = f"batch:{batch_id}:fail_counted:{file_name}"
            if redis_conn.set(fail_counted_key, "1", ex=86400, nx=True):
                try:
                    mark_fail_job(batch_id=batch_id, error_msg=str(e), file_name=file_name)
                except Exception as db_err:
                    logger.error(f"[PARSE FAIL] mark_fail_job failed for batch {batch_id}: {db_err}")
            else:
                logger.info(f"[PARSE FAIL] file={file_name} already counted — skipping (retry)")

        raise

    finally:
        if batch_id:
            logger.info(f"[FINALIZE CHECK] Checking if batch {batch_id} is fully done...")
            finalize_batch_redis(batch_id)


def finalize_batch_redis(batch_id: str):
    """
    Check if batch is complete using the DB (authoritative source), not Redis counters.
    Redis counters can be polluted by stale retry jobs from previous runs.
    finalize_batch_parsed uses a DB-level FOR UPDATE lock, so it's safe to call after every job.
    """
    logger.info(f"[FINALIZE] Checking batch {batch_id} via DB...")
    try:
        finalize_batch_parsed(batch_id)
    except Exception as e:
        logger.error(f"[FINALIZE] finalize_batch_parsed failed for batch {batch_id}: {e!r}")


def handle_parse_job_failed(job_payload: dict, error_msg: str = "Job failed (timeout or crash)"):
    """
    Called when a parse_resume job is killed externally (RQ job_timeout, OOM, SIGKILL).
    The child process never ran our except/finally, so we update Redis + DB here
    so the batch can finalize and other resumes continue.
    """
    try:
        batch_id = str(job_payload.get("batch_id", ""))
        redis_job_id = str(job_payload.get("redis_job_id", ""))
        storage_path = job_payload.get("storage_path", "")
        file_name = os.path.basename(storage_path) if storage_path else "unknown"

        if not batch_id:
            logger.warning("[FAILED JOB] No batch_id in payload, skipping cleanup")
            return

        logger.info(f"[FAILED JOB] Cleaning up: file={file_name} batch={batch_id} error={error_msg[:200]}")

        redis_conn.hset(
            f"job:{redis_job_id}",
            mapping={"status": "failed", "error": error_msg[:500]},
        )

        fail_counted_key = f"batch:{batch_id}:fail_counted:{file_name}"
        if redis_conn.set(fail_counted_key, "1", ex=86400, nx=True):
            try:
                mark_fail_job(batch_id=batch_id, error_msg=error_msg, file_name=file_name)
            except Exception as db_err:
                logger.error(f"[FAILED JOB] mark_fail_job failed: {db_err}")

        finalize_batch_redis(batch_id)
    except Exception as e:
        logger.error(f"[FAILED JOB] handle_parse_job_failed error: {e!r}")
