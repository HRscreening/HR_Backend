from sqlalchemy import Column, String, DateTime, Integer, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from configs.postgress_db import Base
from src.modules.reminders.model.reminder_enum import RecipientType, ReminderStatus, ReminderType, EntityType

class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    entity_type = Column(SQLEnum(EntityType, name="entity_type_enum",values_callable=lambda obj: [e.value for e in obj],), nullable=False)
    entity_id = Column(String, nullable=False)

    reminder_type = Column(SQLEnum(ReminderType, name="reminder_type_enum",values_callable=lambda obj: [e.value for e in obj],), nullable=False)

    recipient_type = Column(SQLEnum(RecipientType, name="recipient_type_enum",values_callable=lambda obj: [e.value for e in obj],), nullable=False)
    recipient_id = Column(String, nullable=False)

    next_run_at = Column(DateTime(timezone=True), nullable=False)

    payload = Column(JSONB, nullable=True)
    reminder_count = Column(Integer, default=0, nullable=False)

    status = Column(SQLEnum(ReminderStatus, name="reminder_status_enum",values_callable=lambda obj: [e.value for e in obj]), default=ReminderStatus.PENDING, nullable=False)

    #TODO: can be removed as keeping the worker_job_id = reminder_id for now for easy tracking and management of reminders. Can be used in future for grouping of reminders if needed.
    worker_job_id = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())