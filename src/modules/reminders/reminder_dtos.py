from pydantic import BaseModel
from src.modules.reminders.model.reminder_enum import ReminderType, RecipientType, EntityType
from uuid import UUID
from datetime import datetime

class CreateReminderDTO(BaseModel):
    entity_id: str | UUID
    entity_type: EntityType
    recipient_id: str | UUID
    recipient_type: RecipientType
    reminder_type: ReminderType
    template_key: str
    next_run_at: datetime
    payload: dict | None = None
    worker_job_id: str | UUID | None = None
    
    
    