# app/workers/connection.py


from configs.redis_config import redis_conn
from configs.env_config import DEFAULT_TIMEOUT_REDIS_WORKER
from rq import Queue

# =========================
# Redis Configuration
# =========================


# =========================
# Queue Configuration
# =========================

DEFAULT_TIMEOUT = DEFAULT_TIMEOUT_REDIS_WORKER  # 10 minutes

resume_parsing_queue = Queue(
    name="resume_parsing_queue",
    connection=redis_conn,
    default_timeout=DEFAULT_TIMEOUT_REDIS_WORKER
)

jd_extraction_queue = Queue(
    name="jd_extraction",
    connection=redis_conn,
    default_timeout=60 * 20,  # JD parsing includes LLM calls
)

resume_scoring_queue = Queue(
    name="resume_scoring_queue",
    connection=redis_conn,
    default_timeout=60 * 20  # LLM calls are slow  #TODO: make it dynamic based on env variable later
)

llm_queue = Queue(
    name="resume_parsing_queue",
    connection=redis_conn,
    default_timeout=60 * 20  # LLM calls are slow  #TODO: make it dynamic based on env variable later
)

candidate_extraction_queue = Queue(
    name="candidate_extraction_queue",
    connection=redis_conn,
    default_timeout= 60*5  # 5 mins
)

# Optional: Map for dynamic access
QUEUES = {
    "resume_parsing": resume_parsing_queue,
    "jd_extraction": jd_extraction_queue,
    "resume_scoring": resume_scoring_queue,
    "candidate_extraction":candidate_extraction_queue,
    "llm": llm_queue
}
