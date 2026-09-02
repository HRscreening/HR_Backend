from typing import List
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from configs.log_config import get_logger
from src.modules.reminders.reminder_repository import ReminderRepository
from src.modules.reminders.reminder_dtos import CreateReminderDTO
from src.modules.reminders.model.reminder_model import Reminder
from src.modules.reminders.model.reminder_enum import ReminderStatus
from src.modules.notifications.repositories.notification_repository import NotificationRepository
from src.modules.notifications.model.notification_model import Notification
from src.modules.notifications.model.notification_enum import NotificationStatus
from src.dtos.notification_dto import CreateNotificationDTO
from workers_async.producers.email_tasks_producer import EnqueueReminderPayload
from workers_async.base import EnqueueNotificationPayload
from workers_async.factory import AsyncProducerFactory
from src.dtos.async_producers_dtos import Async_Producer_Keys

MAX_RETRIES = 3
BACKOFF_SECONDS = [300, 1800, 7200]


class NotificationDispatcher:
    def __init__(
        self,
        reminder_repository: ReminderRepository,
        notification_repository: NotificationRepository,
        producer_factory: AsyncProducerFactory,
        db: AsyncSession,
    ):
        self.reminder_repository = reminder_repository
        self.notification_repository = notification_repository
        self.producer_factory = producer_factory
        self.email_producer = producer_factory.get_producer(Async_Producer_Keys.EMAIL_PRODUCER)
        self.notification_producer = producer_factory.get_producer(Async_Producer_Keys.NOTIFICATION_PRODUCER)
        self.db = db
        self.logger = get_logger("NotificationDispatcher")

    async def prepare_reminders(self, payloads: List[CreateReminderDTO]) -> List[Reminder]:
        """Phase 1: Insert reminders with status=PENDING. Flush only — caller commits."""
        if not payloads:
            return []
        return await self.reminder_repository.create_reminders(payloads)


    async def prepare_notifications(self, payloads: List[CreateNotificationDTO]) -> List[Notification]:
        """Phase 1: Insert notifications with status=PENDING. Flush only — caller commits."""
        if not payloads:
            return []
        notifications = []
        for dto in payloads:
            notification = await self.notification_repository.create_notification(dto)
            notifications.append(notification)
        return notifications


    async def dispatch_reminders(self, reminders: List[Reminder]) -> None:
        """Phase 2 (after caller commits): Enqueue reminders to ARQ. Update worker_job_id + status=QUEUED in new tx."""
        if not reminders:
            return

        enqueue_payloads = [
            EnqueueReminderPayload(reminder_id=r.id, run_at=r.next_run_at) for r in reminders
        ]
        results = await self.email_producer.enqueue_reminder_email_task(enqueue_payloads)
        result_map = {str(r.reminder_id): r for r in results}

        async with self.db.begin():
            for reminder in reminders:
                res = result_map.get(str(reminder.id))
                if res and res.status == "success":
                    await self.reminder_repository.update_status(
                        reminder.id, ReminderStatus.QUEUED, worker_job_id=res.job_id
                    )

        success_count = sum(1 for r in results if r.status == "success")
        self.logger.info(f"Dispatched {len(reminders)} reminders ({success_count} enqueued successfully)")


    async def dispatch_notifications(self, notifications: List[Notification]) -> None:
        """Phase 2 (after caller commits): Enqueue notifications to ARQ. Update worker_job_id + status=QUEUED in new tx."""
        if not notifications:
            return

        enqueue_payloads = [
            EnqueueNotificationPayload(notification_id=n.id, run_at=datetime.now(timezone.utc))
            for n in notifications
        ]
        results = await self.notification_producer.enqueue_notification_task(enqueue_payloads)
        result_map = {str(r.reminder_id): r for r in results}

        async with self.db.begin():
            for notification in notifications:
                res = result_map.get(str(notification.id))
                if res and res.status == "success":
                    await self.notification_repository.update_status(
                        notification.id, NotificationStatus.QUEUED, worker_job_id=res.job_id
                    )

        success_count = sum(1 for r in results if r.status == "success")
        self.logger.info(f"Dispatched {len(notifications)} notifications ({success_count} enqueued successfully)")

    async def cancel_notifications(self, notification_ids: List[str]) -> None:
        """Mark notifications CANCELLED and abort their ARQ jobs.
        DB update joins caller's transaction — caller is responsible for commit.
        """
        if not notification_ids:
            return
        for notification_id in notification_ids:
            await self.notification_repository.update_status(
                notification_id, NotificationStatus.CANCELLED
            )
        await self.notification_producer.cancel_jobs(notification_ids)
        self.logger.info(f"Cancelled {len(notification_ids)} notifications")


    async def cancel_reminders(self, reminder_ids: List[str]) -> None:
        """Mark reminders CANCELLED and abort their ARQ jobs.
        DB update joins caller's transaction — caller is responsible for commit.
        """
        if not reminder_ids:
            return
        await self.reminder_repository.change_reminder_status_multi(
            reminder_ids, ReminderStatus.CANCELLED
        )
        await self.email_producer.cancel_jobs(reminder_ids)
        self.logger.info(f"Cancelled {len(reminder_ids)} reminders")