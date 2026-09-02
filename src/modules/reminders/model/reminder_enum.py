from enum import Enum


class EntityType(str, Enum):
    INTERVIEW = "Interview"
    CANDIDATE = "Candidate"
    # PANELIST = "Panelist"
    JOB = "Job"


class ReminderType(str, Enum):
    BOOKING_LINK = "Booking_Link"
    INTERVIEW_UPCOMING = "Interview_Upcoming"
    FEEDBACK_PENDING = "Feedback_Pending"
    RESCHEDULE = "Reschedule"


class RecipientType(str, Enum):
    CANDIDATE = "Candidate"
    PANELIST = "Panelist"
    HR = "HR"


class ReminderStatus(str, Enum):
    PENDING = "Pending"
    QUEUED = "Queued"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    FAILED = "Failed"