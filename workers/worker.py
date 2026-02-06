# app/workers/worker.py

import os
# from rq import Worker  # For Linux/Mac
from rq import SimpleWorker as Worker # For Windows compatibility
from workers.connection import redis_conn, QUEUES

def start_worker():
    """
    Start RQ worker listening to configured queues.
    """
    queue_list = list(QUEUES.values())

    worker = Worker(
        queues=queue_list,
        connection=redis_conn
    )
    worker.work(with_scheduler=False)

if __name__ == "__main__":
    start_worker()
