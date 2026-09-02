from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Literal
from uuid import UUID

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
class EnqueueNotificationPayload:
    notification_id: str | UUID
    run_at: datetime
