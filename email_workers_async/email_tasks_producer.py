import uuid
from typing import List
from arq.connections import ArqRedis
from configs.log_config import get_logger
from dataclasses import dataclass
from uuid import UUID
from datetime import timedelta
from typing import Optional,Literal
from datetime import datetime,timezone
from arq.jobs import Job, JobStatus


@dataclass
class JobConfig:
    queue_name: str
    worker_func: str
    
@dataclass
class EnqueueResult:
    reminder_id: str | UUID
    job_id: Optional[str]
    status: Literal["success", "failed"]
    error: Optional[str] = None

@dataclass
class EnqueueReminderPayload:
    reminder_id: str | UUID
    run_at: datetime

class EmailProducer:
    """
    Async producer for Email jobs
    """

    def __init__(self,redis:ArqRedis):
        self.redis  = redis
        self.default_queue = "default"
        
        # --------------- config ---------------
        # TODO: In arq each queue needs its own worker function. We can optimize this by having a single worker function that can handle both text and url scoring based on the batch metadata. This way we can use a single queue and reduce complexity. For now, we will keep them separate for clarity and ease of scaling different types of scoring independently in the future if needed.
        self.send_reminder_email_config = JobConfig(
            queue_name=self.default_queue,
            worker_func="send_reminder_email_worker",
        )

        self.logger = get_logger("Reminder_Email_Producer")

    
    def get_now(self):
        return datetime.now(timezone.utc)

    async def enqueue_reminder_email_task(
        self,
        payloads: List[EnqueueReminderPayload],
    ) -> List[EnqueueResult]:

        results: List[EnqueueResult] = []

        for reminder in payloads:
            try:
                now = self.get_now()

                # 🔥 Always enqueue
                if reminder.run_at > now:
                    job = await self.redis.enqueue_job(
                        self.send_reminder_email_config.worker_func,
                        str(reminder.reminder_id),
                        _job_id=str(reminder.reminder_id),  # ✅ set job_id to reminder_id for easy tracking    
                        _queue_name=self.default_queue,
                        _defer_until=reminder.run_at,  # ✅ better
                    )
                else:
                    # run immediately
                    job = await self.redis.enqueue_job(
                        self.send_reminder_email_config.worker_func,
                        str(reminder.reminder_id),
                        _job_id=str(reminder.reminder_id),  # ✅ set job_id to reminder_id for easy tracking
                        _queue_name=self.default_queue,
                    )

                if job:
                    results.append(
                        EnqueueResult(
                            reminder_id=reminder.reminder_id,
                            job_id=job.job_id,
                            status="success",
                        )
                    )
                else:
                    results.append(
                        EnqueueResult(
                            reminder_id=reminder.reminder_id,
                            job_id=None,
                            status="failed",
                            error="Job enqueue returned None",
                        )
                    )

            except Exception as e:
                self.logger.error(
                    f"Failed to enqueue reminder {reminder.reminder_id}: {e}"
                )

                results.append(
                    EnqueueResult(
                        reminder_id=reminder.reminder_id,
                        job_id=None,
                        status="failed",
                        error=str(e),
                    )
                )

        return results
   
   
   
    async def cancel_jobs(
        self,
        job_ids: List[str],
    ) -> List[EnqueueResult]:

        results: List[EnqueueResult] = []

        for job_id in job_ids:
            try:
                job = Job(job_id=job_id, redis=self.redis)
                status = await job.status()

                if status in (JobStatus.deferred, JobStatus.queued):
                    aborted = await job.abort()
                    results.append(EnqueueResult(
                        reminder_id=job_id,
                        job_id=job_id,
                        status="success" if aborted else "failed",
                        error=None if aborted else "abort() returned False",
                    ))
                else:
                    results.append(EnqueueResult(
                        reminder_id=job_id,
                        job_id=job_id,
                        status="failed",
                        error=f"Cannot cancel job with status: {status}",
                    ))

            except Exception as e:
                self.logger.error(f"Failed to cancel job {job_id}: {e}")
                results.append(EnqueueResult(
                    reminder_id=job_id,
                    job_id=job_id,
                    status="failed",
                    error=str(e),
                ))

        return results