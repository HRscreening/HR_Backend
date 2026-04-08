#!/usr/bin/env python3
"""
Inspect RQ queues, registries, and intermediate queue for resume parsing.
Run from HR_Backend: python scripts/check_queues.py

Useful when jobs seem to vanish (e.g. 3/6 parsed, queues empty, 3 jobs never processed).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from rq import Queue
from rq.registry import FailedJobRegistry, StartedJobRegistry, FinishedJobRegistry, DeferredJobRegistry
from configs.redis_config import redis_conn
from workers.connection import QUEUES


def main():
    print("Connecting to Redis...")
    try:
        redis_conn.ping()
    except Exception as e:
        print(f"Redis connection failed: {e}")
        sys.exit(1)

    queue = QUEUES["resume_scoring"]
    qname = queue.name

    print(f"\n=== Queue: {qname} ===")
    count = len(queue)
    print(f"  Jobs in queue: {count}")

    # Intermediate queue (jobs dequeued but not yet in StartedJobRegistry - race window)
    try:
        iq = queue.intermediate_queue
        iq_jobs = iq.get_job_ids()
        if iq_jobs:
            print(f"  Intermediate queue: {len(iq_jobs)} jobs")
            for jid in iq_jobs[:10]:
                print(f"    - {jid}")
            if len(iq_jobs) > 10:
                print(f"    ... and {len(iq_jobs) - 10} more")
        else:
            print(f"  Intermediate queue: empty")
    except Exception as e:
        print(f"  Intermediate queue: (error: {e})")

    for reg_name, reg_class in [
        ("StartedJobRegistry", StartedJobRegistry),
        ("FailedJobRegistry", FailedJobRegistry),
        ("DeferredJobRegistry", DeferredJobRegistry),
        ("FinishedJobRegistry", FinishedJobRegistry),
    ]:
        reg = reg_class(queue=queue)
        job_ids = list(reg.get_job_ids())
        print(f"\n=== {reg_name} ===")
        print(f"  Count: {len(job_ids)}")
        for jid in job_ids[:5]:
            try:
                jid_str = jid.decode() if isinstance(jid, bytes) else str(jid)
                job = queue.fetch_job(jid_str)
                if job:
                    fp = (job.kwargs or {}).get("file_path", "?") if job.kwargs else "?"
                    status = getattr(job, "_status", None) or "?"
                    print(f"    {jid_str}: {os.path.basename(fp) if isinstance(fp, str) else fp} status={status}")
                else:
                    print(f"    {jid_str}: (job fetch failed)")
            except Exception as e:
                print(f"    {jid_str}: error {e}")
        if len(job_ids) > 5:
            print(f"    ... and {len(job_ids) - 5} more")

    print("\nDone.")


if __name__ == "__main__":
    main()
