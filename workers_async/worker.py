# app/workers/worker.py

import asyncio
from workers_async.jobs.send_reminder_email_worker import send_reminder_email_worker
from workers_async.jobs.assessment_workers import transcript_analyzer_worker, request_panelist_worker, interview_post_processing_worker
from workers_async.dependency import on_startup, on_shutdown
from workers_async.connection import redis_settings
from arq import func, run_worker


class WorkerSettings:
    redis_settings = redis_settings
    queue_name = "default"
    max_jobs = 10
    job_timeout = 60 * 20
    on_startup = on_startup
    on_shutdown = on_shutdown
    retry_jobs = True

    functions = [
        func(transcript_analyzer_worker, timeout=60*5, max_tries=3), # it is making llm calls currrent time = 5 mins
        func(request_panelist_worker, timeout=60*2, max_tries=3),
        func(send_reminder_email_worker, timeout=60*2, max_tries=3),
        func(interview_post_processing_worker, timeout=60*5, max_tries=3)
    ]
if __name__ == "__main__":
    print("Starting Assessment Worker...")
    asyncio.run(run_worker(WorkerSettings))