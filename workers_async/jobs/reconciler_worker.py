""""
This File contains the NotificationReconciler class which is responsible for reconciling the state of notifications and reminders in the system. It checks for any PENDING or FAILED notifications/reminders and attempts to re-enqueue them for processing. This ensures that any notifications or reminders that may have failed due to transient issues (like temporary worker downtime or external service failures) get retried and eventually processed successfully.
"""
from datetime import datetime, timedelta, timezone
from configs.log_config import get_logger
from src.modules.reminders.reminder_repository import ReminderRepository
from src.modules.reminders.model.reminder_enum import ReminderStatus
from src.modules.notifications.repositories.notification_repository import NotificationRepository
from src.modules.notifications.model.notification_enum import NotificationStatus
from workers_async.producers.email_tasks_producer import EmailProducer, EnqueueReminderPayload
from workers_async.producers.notification_producer import NotificationProducer
from workers_async.base import EnqueueNotificationPayload

MAX_RETRIES = 3
BACKOFF_SECONDS = [300, 1800, 7200]


class NotificationReconciler:
    def __init__(
        self,
        reminder_repository: ReminderRepository,
        notification_repository: NotificationRepository,
        email_producer: EmailProducer,
        notification_producer: NotificationProducer,
    ):
        self.reminder_repository = reminder_repository
        self.notification_repository = notification_repository
        self.email_producer = email_producer
        self.notification_producer = notification_producer
        self.logger = get_logger("NotificationReconciler")

    async def reconcile(self) -> None:
        """Re-enqueue PENDING records and retry FAILED records ready for retry."""
        await self._reconcile_pending_reminders()
        await self._reconcile_failed_reminders()
        await self._reconcile_pending_notifications()
        await self._reconcile_failed_notifications()

    async def _reconcile_pending_reminders(self) -> None:
        reminders = await self.reminder_repository.get_pending_for_dispatch(limit=100)
        if not reminders:
            return

        enqueue_payloads = [
            EnqueueReminderPayload(reminder_id=r.id, run_at=r.next_run_at) for r in reminders
        ]
        results = await self.email_producer.enqueue_reminder_email_task(enqueue_payloads)
        result_map = {str(r.reminder_id): r for r in results}

        for reminder in reminders:
            res = result_map.get(str(reminder.id))
            if res and res.status == "success":
                await self.reminder_repository.update_status(
                    reminder.id, ReminderStatus.QUEUED, worker_job_id=res.job_id
                )
                self.logger.info(f"Reconciled PENDING reminder {reminder.id} to QUEUED")

    async def _reconcile_failed_reminders(self) -> None:
        reminders = await self.reminder_repository.get_failed_for_retry(limit=100)
        if not reminders:
            return

        enqueue_payloads = [
            EnqueueReminderPayload(reminder_id=r.id, run_at=r.next_run_at) for r in reminders
        ]
        results = await self.email_producer.enqueue_reminder_email_task(enqueue_payloads)
        result_map = {str(r.reminder_id): r for r in results}

        for reminder in reminders:
            res = result_map.get(str(reminder.id))
            if res and res.status == "success":
                await self.reminder_repository.update_status(
                    reminder.id,
                    ReminderStatus.QUEUED,
                    worker_job_id=res.job_id,
                    attempt_count=reminder.attempt_count,
                    next_retry_at=None
                )
                self.logger.info(f"Reconciled FAILED reminder {reminder.id} to QUEUED (attempt {reminder.attempt_count + 1})")

    async def _reconcile_pending_notifications(self) -> None:
        notifications = await self.notification_repository.get_pending_for_dispatch(limit=100)
        if not notifications:
            return

        enqueue_payloads = [
            EnqueueNotificationPayload(notification_id=n.id, run_at=datetime.now(timezone.utc))
            for n in notifications
        ]
        results = await self.notification_producer.enqueue_notification_task(enqueue_payloads)
        result_map = {str(r.reminder_id): r for r in results}

        for notification in notifications:
            res = result_map.get(str(notification.id))
            if res and res.status == "success":
                await self.notification_repository.update_status(
                    notification.id, NotificationStatus.QUEUED, worker_job_id=res.job_id
                )
                self.logger.info(f"Reconciled PENDING notification {notification.id} to QUEUED")

    async def _reconcile_failed_notifications(self) -> None:
        notifications = await self.notification_repository.get_failed_for_retry(limit=100)
        if not notifications:
            return

        enqueue_payloads = [
            EnqueueNotificationPayload(notification_id=n.id, run_at=datetime.now(timezone.utc))
            for n in notifications
        ]
        results = await self.notification_producer.enqueue_notification_task(enqueue_payloads)
        result_map = {str(r.reminder_id): r for r in results}

        for notification in notifications:
            res = result_map.get(str(notification.id))
            if res and res.status == "success":
                await self.notification_repository.update_status(
                    notification.id,
                    NotificationStatus.QUEUED,
                    worker_job_id=res.job_id,
                    attempt_count=notification.attempt_count,
                    next_retry_at=None
                )
                self.logger.info(f"Reconciled FAILED notification {notification.id} to QUEUED (attempt {notification.attempt_count + 1})")


async def reconcile_notifications(ctx) -> dict:
    """ARQ background job: reconcile pending and failed notifications/reminders."""
    from workers_async.context_manager import job_context

    async with job_context(ctx) as deps:
        reconciler = NotificationReconciler(
            reminder_repository=deps["reminder_repository"],
            notification_repository=deps["notification_repository"],
            email_producer=deps["email_producer"],
            notification_producer=deps["notification_producer"],
        )
        try:
            await reconciler.reconcile()
            await deps["db"].commit()
        except Exception:
            await deps["db"].rollback()
            raise

    return {"status": "completed"}
