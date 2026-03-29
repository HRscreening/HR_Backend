# app/workers/worker.py


from  email_workers_async.jobs.send_email_worker import email_worker
from  email_workers_async.jobs.send_reminder_email_worker import send_reminder_email_worker
from  email_workers_async.dependency import on_startup, on_shutdown
from  email_workers_async.connection import redis_settings
from arq import func


class WorkerSettings:
    redis_settings = redis_settings
    queue_name = "default"
    max_jobs = 10
    job_timeout = 60 * 20
    on_startup = on_startup
    on_shutdown = on_shutdown
    retry_jobs = True

    functions = [
        func(email_worker, timeout=10*5,  max_tries=3),
        func(send_reminder_email_worker, timeout=10*5,  max_tries=3)
    ]
if __name__ == "__main__":
    print("Starting email worker...")
    asyncio.run(run_worker(WorkerSettings))