import os
from logging import Logger
from arq import Retry
from workers_async.context_manager import job_context
from src.modules.reminders.reminder_service import ReminderWorkerService

async def send_reminder_email_worker(ctx, reminder_id: str):

    logger: Logger = ctx["logger"]

    job_try = ctx.get("job_try", 1)
    max_tries = 3

    logger.info(f"Processing reminder {reminder_id} | try={job_try}/{max_tries}")

    async with job_context(ctx) as deps:
        service : ReminderWorkerService = deps["reminder_worker_service"]

        try:
            await service.send_reminder_email(reminder_id)

        except Exception as e:
            logger.exception(f"Reminder failed {reminder_id}")

            if job_try < max_tries:
                raise Retry(defer=job_try * 10)  # backoff

            # final failure → mark in DB
            await service.mark_failed(reminder_id, str(e))