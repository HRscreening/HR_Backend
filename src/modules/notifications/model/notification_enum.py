from enum import Enum


class EntityType(str, Enum):
    INTERVIEW = "Interview"
    SLOT = "Slot"
    JOB = "Job"


class NotificationType(str, Enum):
    BOOKING_LINK = "Booking_Link"
    INTERVIEW_UPCOMING = "Interview_Upcoming"
    FEEDBACK_PENDING = "Feedback_Pending"
    RESCHEDULE = "Reschedule"


class NotificationChannel(str, Enum):
    ALL = "ALL"
    SMS = "SMS"
    EMAIL = "EMAIL"
    IN_APP = "IN_APP"

class RecipientType(str, Enum):
    CANDIDATE = "Candidate"
    PANELIST = "Panelist"
    HR = "HR"


class NotificationStatus(str, Enum):
    PENDING = "Pending"
    QUEUED = "Queued"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    FAILED = "Failed"