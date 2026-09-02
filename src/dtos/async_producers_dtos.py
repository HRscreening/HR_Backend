from pydantic import BaseModel
from enum import Enum
from typing import Union



class Async_Producer_Keys(str, Enum):
    EMAIL_PRODUCER = "email_producer"
    NOTIFICATION_PRODUCER = "notification_producer"
    ASSESSMENT_TASK_PRODUCER = "assessment_task_producer"
    