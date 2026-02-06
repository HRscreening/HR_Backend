from workers.connection import redis_conn
from src.services.resume_services import parse_resume_service,finalize_batch_parsed,mark_fail_job
import os

def parse_resume(payload: dict):
    redis_job_id = str(payload["redis_job_id"])
    batch_id = str(payload["batch_id"])
    file_path = payload["file_path"]

    try:
        # 1️⃣ Mark Redis job as processing
        redis_conn.hset(
            f"job:{redis_job_id}",
            mapping={"status": "processing"}
        )

        # 2️⃣ Business logic (DB + parsing)
        parse_resume_service(
            file_path=file_path,
            batch_id=batch_id,
            redis_job_id=redis_job_id
        )

        # 3️⃣ Mark Redis job completed
        pipe = redis_conn.pipeline()
        pipe.hset(
            f"job:{str(redis_job_id)}",
            mapping={"status": "completed"}
        )
        pipe.hincrby(
            f"batch:{batch_id}",
            "completed",
            1
        )
        pipe.execute()

    except Exception as e:
        # 4️⃣ Failure path
        pipe = redis_conn.pipeline()
        pipe.hset(
            f"job:{redis_job_id}",
            mapping={
                "status": "failed",
                "error": str(e)
            }
        )
        
        mark_fail_job(
            batch_id=batch_id,
            error_msg=str(e),
            file_name=os.path.basename(file_path)
            )
        
        
        pipe.hincrby(
            f"batch:{batch_id}",
            "failed",
            1
        )
        pipe.execute()
        raise

    finally:
        # 5️⃣ Possibly close batch
        finalize_batch_redis(batch_id)





def finalize_batch_redis(batch_id: str):
    batch = redis_conn.hgetall(f"batch:{batch_id}")

    if not batch:
        return

    total = int(batch.get("total", 0))
    completed = int(batch.get("completed", 0))
    failed = int(batch.get("failed", 0))

    if completed + failed != total:
        return  # still processing

    # Batch done
    redis_conn.hset(
        f"batch:{batch_id}",
        mapping={"status": "completed"}
    )

    finalize_batch_parsed(batch_id)