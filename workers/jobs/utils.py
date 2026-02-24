from src.services.batch_service import BatchService_ForWorker
from arq.connections import ArqRedis
from configs.log_config import get_logger

logger = get_logger("WORKER_UTILS")


# ─────────────────────────────────────────────────────────────
# Lua script: atomically increment a batch counter, check if
# the batch is complete, and acquire the finalization lock —
# all inside a single Redis call (no race window).
#
# Returns:
#   0 — incremented, but batch is not done yet
#   1 — batch is done AND this caller got the finalization lock
#   2 — batch is done but another caller already holds the lock
# ─────────────────────────────────────────────────────────────
BATCH_INCREMENT_CHECK_LOCK_LUA = """
local batch_key = KEYS[1]
local lock_key  = KEYS[2]
local field     = ARGV[1]

redis.call('HINCRBY', batch_key, field, 1)

local total     = tonumber(redis.call('HGET', batch_key, 'total')     or '0')
local completed = tonumber(redis.call('HGET', batch_key, 'completed') or '0')
local failed    = tonumber(redis.call('HGET', batch_key, 'failed')    or '0')

if total > 0 and (completed + failed) >= total then
    local ok = redis.call('SET', lock_key, '1', 'NX', 'EX', 600)
    if ok then
        redis.call('HSET', batch_key, 'status', 'completed')
        return 1
    end
    return 2
end
return 0
"""


async def increment_and_check_batch(
    redis: ArqRedis,
    batch_id: str,
    field: str,  # "completed" or "failed"
) -> bool:
    """
    Atomically: HINCRBY the counter -> read totals -> acquire lock if done.

    Returns True only for the ONE caller that should trigger finalization.
    """
    batch_key = f"batch:{batch_id}"
    lock_key = f"{batch_key}:finalizing"

    result = await redis.eval(
        BATCH_INCREMENT_CHECK_LOCK_LUA,
        2,
        batch_key,
        lock_key,
        field,
    )

    if result == 1:
        logger.info(
            f"[BATCH DONE] batch={batch_id} — this worker will finalize"
        )
    return result == 1


async def release_finalize_lock(redis: ArqRedis, batch_id: str):
    """Release the finalization lock so another worker can retry."""
    await redis.delete(f"batch:{batch_id}:finalizing")


# async def get_batch_payload(redis: ArqRedis, batch_id: str):

#     batch_meta = await redis.hgetall(f"batch:{batch_id}")

#     if not batch_meta:
#         raise RuntimeError(f"Batch {batch_id} not found")

#     db_job_id = batch_meta.get("job_id")
#     db_batch_id = batch_meta.get("db_batch_id")

#     resume_ids = await redis.lrange(
#         f"batch:{batch_id}:resumes",
#         0,
#         -1,
#     )

#     if not resume_ids:
#         raise RuntimeError(
#             f"No resumes found for batch {batch_id}"
#         )

#     return db_job_id, resume_ids, db_batch_id


async def get_batch_payload(redis: ArqRedis, batch_id: str):
    batch_meta = await redis.hgetall(f"batch:{batch_id}")

    if not batch_meta:
        raise RuntimeError(f"Batch {batch_id} not found")

    # Decode bytes keys/values
    batch_meta = {k.decode(): v.decode() for k, v in batch_meta.items()}

    db_job_id = batch_meta.get("job_id")
    db_batch_id = batch_meta.get("db_batch_id")

    resume_ids = await redis.lrange(f"batch:{batch_id}:resumes", 0, -1)
    resume_ids = [rid.decode() for rid in resume_ids]  # decode these too

    if not resume_ids:
        raise RuntimeError(f"No resumes found for batch {batch_id}")

    return db_job_id, resume_ids, db_batch_id