from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete
from sqlalchemy.orm import selectinload,  aliased


from typing import Optional, List

from src.modules.reminders.model.reminder_model import Reminder 
from src.modules.reminders.model.reminder_enum import ReminderType, ReminderStatus,RecipientType,EntityType 
from configs.log_config import get_logger
from src.modules.reminders.reminder_dtos import CreateReminderDTO
from src.dtos.notification_dto import CreateNotificationDTO
from src.modules.notifications.model.notification_model import Notification, NotificationChannel, NotificationStatus, RecipientType as NotificationRecipientType, EntityType as NotificationEntityType

class NotificationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = get_logger("Notification_Repository")
        
        
    async def create_notification(self, data:CreateNotificationDTO) -> Notification | None:

        notification = Notification(
            entity_type = data.entity_type,
            entity_id = data.entity_id,
            recipient_type = NotificationRecipientType(data.recipient_type),
            recipient_id = data.recipient_id,
            channel = NotificationChannel(data.channel),
            payload = data.payload,
            template_key = data.template_key,
            worker_job_id = data.worker_job_id,
            status = NotificationStatus.PENDING
        )

        self.db.add(notification)
        await self.db.flush()

        return notification
    
    
    async def get_notification_by_id(self, notification_id: UUID) -> Notification | None:
        result = await self.db.execute(select(Notification).where(Notification.id == notification_id))
        return result.scalar_one_or_none()

    async def update_status(
        self,
        notification_id: UUID,
        status: NotificationStatus,
        worker_job_id: str | None = None,
        error_log: dict | None = None,
        attempt_count: int | None = None
    ) -> Notification | None:
        values = {"status": status}
        if worker_job_id is not None:
            values["worker_job_id"] = worker_job_id
        if error_log is not None:
            values["error_log"] = error_log
        if attempt_count is not None:
            values["attempt_count"] = attempt_count

        result = await self.db.execute(
            update(Notification)
            .where(Notification.id == notification_id)
            .values(**values)
            .returning(Notification)
        )
        updated = result.fetchone()
        return updated[0] if updated else None

    async def get_pending_for_dispatch(self, limit: int = 100) -> list[Notification]:
        result = await self.db.execute(
            select(Notification)
            .where(Notification.status == NotificationStatus.PENDING)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_failed_for_retry(self, limit: int = 100) -> list[Notification]:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(Notification)
            .where(
                Notification.status == NotificationStatus.FAILED,
                Notification.attempt_count < 3,
                (Notification.next_retry_at.is_(None)) | (Notification.next_retry_at <= now)
            )
            .limit(limit)
        )
        return result.scalars().all()
