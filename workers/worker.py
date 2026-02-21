# app/workers/worker.py

from arq.connections import RedisSettings

from workers.jobs.candidate_extracter import extract_candidate_worker
from workers.jobs.resume_parser import parse_resume_worker 
from workers.jobs.resume_scorer import score_resumes_text_batch, score_resumes_url_batch
from workers.dependency import on_startup,on_shutdown
from configs.env_config import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD
from workers.connection import redis_settings
from arq import func


# class WorkerSettings:
#     """
#     ARQ Worker configuration
#     """

#     # Redis connection
#     redis_settings = redis_settings

#     # Functions this worker can execute
#     functions = [
#         func(extract_candidate_worker,max_tries=3, timeout=20*5),
#         func(parse_resume_worker,max_tries=3, timeout=20*5) ,
#         func(score_resumes_text_batch,max_tries=3, timeout=20*5),
#         func(score_resumes_url_batch,max_tries=3, timeout=20*5),
#     ]

#     # Concurrency (number of async jobs at once)
#     max_jobs = 10

#     # Default timeout per job (seconds)
#     job_timeout = 60 * 20  # 20 minutes

#     on_startup = on_startup
#     on_shutdown = on_shutdown

    
#     # Retry behavior
#     retry_jobs = True

#     # Optional: custom queue name (default = "arq:queue")
#     queue_name = "default"


class WorkerSettings:
    redis_settings = redis_settings
    queue_name = "default"
    max_jobs = 10
    job_timeout = 60 * 20
    on_startup = on_startup
    on_shutdown = on_shutdown
    retry_jobs = True

    functions = [
        func(extract_candidate_worker, timeout=60*5,  max_tries=3),
        func(parse_resume_worker,      timeout=60*10, max_tries=3),
        func(score_resumes_text_batch, timeout=60*20, max_tries=3),
        func(score_resumes_url_batch,  timeout=60*20, max_tries=3),
    ]