"""
RQ exception handlers — run when jobs fail so batches can finalize gracefully.

- work_horse_killed_handler: when RQ kills a job (timeout, OOM) — the child dies
  before our except/finally run. We must update Redis+DB so the batch finalizes.
- job_exc_handler: safety net for ANY job exception. If parse_resume's own try/except
  already handled it, the SETNX dedup prevents double-counting.
"""
import logging
import traceback
from rq.job import Job

from workers.tasks.resume_parser import handle_parse_job_failed

logger = logging.getLogger(__name__)

PARSE_RESUME_FUNC = "workers.tasks.resume_parser.parse_resume"


def _extract_parse_payload(job: Job) -> dict | None:
    """Extract payload from a parse_resume job, or None if not a parse job."""
    if job is None:
        return None
    func_name = getattr(job, "func_name", None) or ""
    args = job.args or []
    payload = args[0] if args else {}
    is_parse_job = (
        isinstance(func_name, str) and PARSE_RESUME_FUNC in func_name
    ) or (isinstance(payload, dict) and payload.get("batch_id") and payload.get("storage_path"))
    if is_parse_job and isinstance(payload, dict) and payload.get("batch_id"):
        return payload
    return None


def work_horse_killed_handler(job: Job, retpid: int, ret_val: int, rusage) -> None:
    """
    Called when the workhorse (child process) is unexpectedly killed — e.g. RQ
    job_timeout, OOM, SIGKILL. The job never ran our except/finally, so we
    must update Redis+DB and trigger batch finalization.
    """
    payload = _extract_parse_payload(job)
    if payload:
        error_msg = f"Workhorse killed (pid={retpid} ret={ret_val})"
        handle_parse_job_failed(payload, error_msg)
        logger.info(f"[WORKHORSE KILLED] Cleaned up parse job for batch {payload.get('batch_id')}")
    else:
        func_name = getattr(job, "func_name", None) if job else "unknown"
        logger.debug(f"[WORKHORSE KILLED] Non-parse job or no batch_id: {func_name}")


def job_exc_handler(job: Job, exc_type, exc_value, tb) -> None:
    """
    RQ exc_handler — called for ANY job exception (normal failures).
    Safety net: if parse_resume's own try/except already ran mark_fail_job,
    the SETNX dedup in handle_parse_job_failed prevents double-counting.
    """
    payload = _extract_parse_payload(job)
    if payload:
        error_msg = f"{exc_type.__name__}: {exc_value}"
        handle_parse_job_failed(payload, error_msg)
        logger.info(f"[EXC HANDLER] Cleaned up parse job for batch {payload.get('batch_id')}")
    else:
        func_name = getattr(job, "func_name", None) if job else "unknown"
        logger.debug(f"[EXC HANDLER] Non-parse job: {func_name}")
