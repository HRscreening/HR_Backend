from sqlalchemy import Column, String, DateTime, Integer, Enum as SQLEnum,Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from configs.postgress_db import Base
from src.modules.notifications.model.notification_enum import RecipientType, NotificationStatus, NotificationType,NotificationChannel, EntityType

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    entity_type = Column(SQLEnum(EntityType, name="entity_type_enum",values_callable=lambda obj: [e.value for e in obj],), nullable=False)
    entity_id = Column(String, nullable=False, index=True)

    template_key = Column(String, nullable=False)   # template key to identify which email/sms template to use for the notification. This should correspond to the keys defined in the template keys enum in the notification_dto.py file.
    channel = Column(SQLEnum(NotificationChannel, name="notification_channel_enum",values_callable=lambda obj: [e.value for e in obj],), nullable=False)
    
    recipient_type = Column(SQLEnum(RecipientType, name="recipient_notification_type_enum",values_callable=lambda obj: [e.value for e in obj],), nullable=False)
    recipient_id = Column(String, nullable=False, index=True)

    payload = Column(JSONB, nullable=True)  # payload for the template make sure to include all necessary information in the payload for the template to render correctly. For example, if the template requires candidate_name and interview_time, make sure to include those keys in the payload when creating a notification.
    
    error_log = Column(JSONB,nullable=True)

    status = Column(SQLEnum(NotificationStatus, name="notification_status_enum",values_callable=lambda obj: [e.value for e in obj]), default=NotificationStatus.PENDING, nullable=False)

    #TODO: worker_job_id = notification_id for now for easy tracking and management of jobs. In the future, if we want to allow multiple notifications for the same reminder or have more complex scheduling needs, we can decouple these and allow multiple jobs per notification or track them separately as needed.
    worker_job_id = Column(String, nullable=True)

    attempt_count = Column(Integer, default=0, nullable=False)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())