from workers.connection import redis_conn
from src.services.resume_services import extract_candidate_service
import os
from src.schemas.user_schemas import CandidateInfoSchema
from configs.log_config import get_logger

logger = get_logger("candidate_extracter")

def extract_candidate(payload: dict):
    redis_job_id = payload.get("redis_job_id")
    batch_id = payload.get("batch_id")
    resume_id = payload.get("resume_id")
    candidate_payload = payload.get("candidate")  # ✅ correct key

    # 🔐 Hard guard – NEVER crash on bad payloads
    if not redis_job_id or not resume_id:
        logger.error(f"Invalid payload received in extract_candidate: {payload}")
        return  # ❌ do NOT raise → avoids retry storm

    candidate = (
        CandidateInfoSchema(**candidate_payload)
        if candidate_payload
        else None
    )

    try:
        # 1️⃣ Mark Redis job as processing
        redis_conn.hset(
            f"job:{redis_job_id}",
            mapping={"status": "processing"}
        )

        # 2️⃣ Business logic
        extract_candidate_service(
            resume_id=resume_id,
            candidate_info=candidate,
        )

        # 3️⃣ Mark Redis job completed
        redis_conn.hset(
            f"job:{redis_job_id}",
            mapping={"status": "completed"}
        )

    except Exception as e:
        # 4️⃣ Failure path (no retry storm)
        redis_conn.hset(
            f"job:{redis_job_id}",
            mapping={
                "status": "failed",
                "error": str(e)
            }
        )

        logger.exception(
            f"Candidate extraction failed for resume_id={resume_id}, "
            f"redis_job_id={redis_job_id}"
        )

        raise  # retry ONLY for real processing failures
