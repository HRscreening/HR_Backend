import enum
from sqlalchemy import Enum

class UserRole(enum.Enum):
    ADMIN = "admin"
    CEO = "ceo"
    HR_MANAGER = "hr_manager"
    HR_COLLABORATOR = "hr_collaborator"
    INTERVIEWER = "interviewer"
    INDIVIDUAL = "individual"


class JobStatus(enum.Enum):
    OPEN = "open"
    PAUSED = "paused"
    CLOSED = "closed"
    ARCHIVED = "archived"


class ApplicationStatus(enum.Enum):
    APPLIED = "applied"
    IN_REVIEW = "in_review"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    OFFER_EXTENDED = "offer_extended"
    REJECTED = "rejected"
    HIRED = "hired"
