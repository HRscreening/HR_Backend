from rq import Worker
from queue import queue
from configs.redis_config import redis_conn

if __name__ == "__main__":
    worker = Worker(
        [queue],
        connection=redis_conn
    )
    worker.work()
