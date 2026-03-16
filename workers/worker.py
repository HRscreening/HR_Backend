# app/workers/worker.py

import logging
import os
import sys

# Configure logging BEFORE importing anything else so all module loggers inherit this config
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

import platform as _platform
from rq import Worker, SimpleWorker
from rq.timeouts import TimerDeathPenalty

# _worker_env = os.environ.get("RQ_WORKER_CLASS", "").strip().lower()
# if _worker_env == "fork":
#     WorkerClass = Worker
# elif _worker_env == "simple":
#     WorkerClass = SimpleWorker
# else:
#     # Auto-detect based on OS

WorkerClass = Worker if _platform.system() == "Linux" else SimpleWorker

# On Windows/macOS the default UnixSignalDeathPenalty uses signal.SIGALRM which
# doesn't exist.  TimerDeathPenalty achieves the same timeout via threading.Timer.
if WorkerClass is SimpleWorker:
    WorkerClass.death_penalty_class = TimerDeathPenalty
from workers.connection import redis_conn, QUEUES
from workers.exception_handlers import work_horse_killed_handler, job_exc_handler


def start_worker():
    """
    Start RQ worker listening to configured queues.
    Set QUEUES=resume_parsing to run a dedicated parsing worker (avoids multi-queue round-robin starving).
    """
    queues_filter = os.environ.get("QUEUES", "").strip()
    if queues_filter:
        names = [n.strip() for n in queues_filter.split(",") if n.strip()]
        queue_list = [QUEUES[n] for n in names if n in QUEUES]
        if not queue_list:
            raise ValueError(f"QUEUES={queues_filter} matched no queues. Valid: {list(QUEUES.keys())}")
    else:
        queue_list = list(QUEUES.values())
    logging.info(f"Starting worker on queues: {[q.name for q in queue_list]} (WorkerClass={WorkerClass.__name__})")

    # maintenance_interval=1800 (30 min) — reduces "Job was stuck in intermediate queue" race.
    # Default 600s can mark jobs failed while worker is still preparing them (RQ issue #2061).
    maintenance = int(os.environ.get("RQ_MAINTENANCE_INTERVAL", "1800"))
    worker = WorkerClass(
        queues=queue_list,
        connection=redis_conn,
        exception_handlers=[job_exc_handler],
        work_horse_killed_handler=work_horse_killed_handler if WorkerClass is Worker else None,
        maintenance_interval=maintenance,
    )
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    start_worker()
