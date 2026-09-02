import traceback
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from configs.log_config import get_logger
from src.modules.notifications.services.notification_service import NotificationService
from src.modules.notifications.repositories.notification_repository import NotificationRepository
from src.modules.reminders.reminder_repository import ReminderRepository
from src.modules.notifications.model.notification_enum import NotificationChannel, NotificationStatus
from src.modules.reminders.model.reminder_enum import ReminderStatus
from src.services.errors.base import DomainError

MAX_RETRIES = 3
BACKOFF_SECONDS = [300, 1800, 7200]


class NotificationWorker:
    """
    NotificationWorker processes reminders and instant notifications picked up
    by ARQ jobs. It owns its own commits on the session so status/attempt state
    is durable even if the job handler's finally path is skipped.
    """

    def __init__(
        self,
        notification_service: NotificationService,
        notification_repository: NotificationRepository,
        reminder_repository: ReminderRepository,
        db: AsyncSession,
    ):
        self.notification_service = notification_service
        self.notification_repository = notification_repository
        self.reminder_repository = reminder_repository
        self.db = db
        self.logger = get_logger("Notification_Worker_Service")

    def _compute_next_retry(self, attempt_count: int) -> datetime:
        idx = min(max(attempt_count - 1, 0), len(BACKOFF_SECONDS) - 1)
        return datetime.now(timezone.utc) + timedelta(seconds=BACKOFF_SECONDS[idx])

    def _check_reminder_validity(self, reminder):
        if not reminder:
            raise DomainError(message="Reminder not found for the given worker job ID", status_code=404)
        if reminder.status not in [ReminderStatus.PENDING, ReminderStatus.QUEUED]:
            raise DomainError(message="Reminder is not in a valid state to send email", status_code=400)

    async def process_notification(self, notification_id: str):
        """Worker function to process instant notifications and track status/retries."""
        notification = await self.notification_repository.get_notification_by_id(notification_id)

        if not notification:
            self.logger.error(f"Notification with ID {notification_id} not found.")
            return

        if notification.status not in [NotificationStatus.PENDING, NotificationStatus.QUEUED]:
            self.logger.info(
                f"Notification {notification_id} already processed or in invalid state: {notification.status}"
            )
            return

        try:
            await self.notification_service.send_notification(
                notification.recipient_type,
                notification.channel,
                notification.payload,
                notification.template_key,
            )
        except Exception as e:
            self.logger.exception(f"Error sending notification {notification_id}")
            new_attempt = (notification.attempt_count or 0) + 1
            await self.notification_repository.update_status(
                notification_id,
                NotificationStatus.FAILED,
                error_log={"error": str(e), "traceback": traceback.format_exc()},
                attempt_count=new_attempt,
            )
            await self.db.commit()
            self.logger.info(f"Notification {notification_id} marked FAILED (attempt {new_attempt})")
            raise

        await self.notification_repository.update_status(notification_id, NotificationStatus.COMPLETED)
        await self.db.commit()
        self.logger.info(f"Notification {notification_id} completed successfully")

    async def send_reminder_notification(self, reminder_id: str):
        """Worker function to send reminder notifications and track status/retries."""
        reminder = await self.reminder_repository.get_reminder_by_id(reminder_id)
        self._check_reminder_validity(reminder)

        try:
            await self.notification_service.send_notification(
                reminder.recipient_type,
                NotificationChannel.EMAIL,
                reminder.payload,
                reminder.template_key,
            )
        except ValueError as e:
            self.logger.error(f"Value error sending reminder {reminder_id}: {e}")
            new_attempt = (reminder.attempt_count or 0) + 1
            await self.reminder_repository.update_status(
                reminder_id,
                ReminderStatus.FAILED,
                error_log={"error": str(e), "traceback": traceback.format_exc()},
                attempt_count=new_attempt,
                next_retry_at=self._compute_next_retry(new_attempt),
            )
            await self.db.commit()
            raise DomainError(message=str(e), status_code=400)
        except Exception as e:
            self.logger.exception(f"Error sending reminder {reminder_id}")
            new_attempt = (reminder.attempt_count or 0) + 1
            await self.reminder_repository.update_status(
                reminder_id,
                ReminderStatus.FAILED,
                error_log={"error": str(e), "traceback": traceback.format_exc()},
                attempt_count=new_attempt,
                next_retry_at=self._compute_next_retry(new_attempt),
            )
            await self.db.commit()
            self.logger.info(f"Reminder {reminder_id} marked FAILED (attempt {new_attempt})")
            raise

        await self.reminder_repository.update_status(reminder_id, ReminderStatus.COMPLETED)
        await self.db.commit()
        self.logger.info(f"Reminder {reminder_id} completed successfully")
