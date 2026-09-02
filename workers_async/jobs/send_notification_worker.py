from logging import Logger
from arq import Retry
from workers_async.context_manager import job_context
from src.modules.notifications.services.notification_worker import NotificationWorker
from src.services.errors.base import DomainError


async def send_notification_worker(ctx, notification_id: str):
    logger: Logger = ctx["logger"]

    job_try = ctx.get("job_try", 1)
    max_tries = 3

    logger.info(f"Processing notification {notification_id} | try={job_try}/{max_tries}")

    async with job_context(ctx) as deps:
        worker: NotificationWorker = deps["notification_worker"]

        try:
            await worker.process_notification(notification_id)
        except DomainError as e:
            logger.warning(f"Domain error for notification {notification_id}: {e}")
            return
        except Exception:
            logger.exception(f"Notification failed {notification_id}")
            if job_try < max_tries:
                raise Retry(defer=job_try * 10)
        finally:
            await deps["db"].commit()
            logger.info(f"Database session committed for notification {notification_id}")
