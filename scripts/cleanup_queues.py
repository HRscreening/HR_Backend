#!/usr/bin/env python3
"""
Purge RQ worker queues, batch/job tracking keys, and batch progress (bulk_upload_batches).
Run from HR_Backend: python scripts/cleanup_queues.py
"""
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from rq import Queue
from rq.registry import FailedJobRegistry, StartedJobRegistry, DeferredJobRegistry, FinishedJobRegistry
from configs.redis_config import redis_conn
from configs.postgress_db import sync_engine
from sqlalchemy import text
from workers.connection import QUEUES


def main():
    print("Connecting to Redis...")
    try:
        redis_conn.ping()
    except Exception as e:
        print(f"Redis connection failed: {e}")
        sys.exit(1)

    # Empty all RQ queues
    for name, queue in QUEUES.items():
        count = len(queue)
        queue.empty()
        print(f"  Emptied {queue.name}: {count} jobs removed")

        # Clear registries (failed/started/deferred/finished) so old job ids don't linger.
        # This does not affect application DB state; it's just RQ bookkeeping.
        for reg_cls in (FailedJobRegistry, StartedJobRegistry, DeferredJobRegistry, FinishedJobRegistry):
            try:
                reg = reg_cls(queue=queue)
                job_ids = list(reg.get_job_ids())
                if job_ids:
                    for jid in job_ids:
                        # RQ 2.6.1 registries don't implement .empty(); remove entries one by one.
                        # Use delete_job=True to also remove the stored Job payload.
                        reg.remove(jid, delete_job=True)
                    print(f"  Cleared {reg_cls.__name__} for {queue.name}: {len(job_ids)} jobs removed")
            except Exception as e:
                print(f"  Warning: could not clear {reg_cls.__name__} for {queue.name}: {e}")

    # Delete batch/job tracking keys (batch:*, job:*)
    cursor = 0
    deleted = 0
    while True:
        cursor, keys = redis_conn.scan(cursor=cursor, match="batch:*", count=100)
        if keys:
            redis_conn.delete(*keys)
            deleted += len(keys)
        cursor, keys = redis_conn.scan(cursor=cursor, match="job:*", count=100)
        if keys:
            redis_conn.delete(*keys)
            deleted += len(keys)
        if cursor == 0:
            break

    if deleted:
        print(f"  Deleted {deleted} batch/job tracking keys")

    # Truncate bulk_upload_batches so "Processing Resumes" modal shows no batch
    print("Clearing batch progress (bulk_upload_batches)...")
    try:
        with sync_engine.connect() as conn:
            conn.execute(text("TRUNCATE TABLE bulk_upload_batches CASCADE"))
            conn.commit()
        print("  Truncated bulk_upload_batches")
    except Exception as e:
        print(f"  Warning: Could not truncate bulk_upload_batches: {e}")

    print("Done.")


if __name__ == "__main__":
    main()
