# app/workers/connection.py

import os

from configs.redis_config import redis_conn
from configs.env_config import DEFAULT_TIMEOUT_REDIS_WORKER
from rq import Queue

# =========================
# Queue Namespace
# =========================
# QUEUE_PREFIX isolates environments sharing the same Redis.
# Local dev: QUEUE_PREFIX=dev:   → queues become "dev:resume_parsing_queue"
# Production: QUEUE_PREFIX=prod: → queues become "prod:resume_parsing_queue"
# Without this, workers on different machines (e.g. Ubuntu server with old code)
# race for the same jobs and silently break the pipeline.
QUEUE_PREFIX = os.environ.get("QUEUE_PREFIX", "")

# =========================
# Queue Configuration
# =========================

DEFAULT_TIMEOUT = DEFAULT_TIMEOUT_REDIS_WORKER  # 10 minutes

resume_parsing_queue = Queue(
    name=f"{QUEUE_PREFIX}resume_parsing_queue",
    connection=redis_conn,
    default_timeout=DEFAULT_TIMEOUT_REDIS_WORKER
)

jd_extraction_queue = Queue(
    name=f"{QUEUE_PREFIX}jd_extraction",
    connection=redis_conn,
    default_timeout=60 * 20,  # JD parsing includes LLM calls
)

resume_scoring_queue = Queue(
    name=f"{QUEUE_PREFIX}resume_scoring_queue",
    connection=redis_conn,
    default_timeout=60 * 20  # LLM calls are slow
)

candidate_extraction_queue = Queue(
    name=f"{QUEUE_PREFIX}candidate_extraction_queue",
    connection=redis_conn,
    default_timeout=60 * 5  # 5 mins
)

# Map for dynamic access. Each queue appears ONCE to avoid round-robin skipping jobs.
QUEUES = {
    "resume_parsing": resume_parsing_queue,
    "jd_extraction": jd_extraction_queue,
    "resume_scoring": resume_scoring_queue,
    "candidate_extraction": candidate_extraction_queue,
}
