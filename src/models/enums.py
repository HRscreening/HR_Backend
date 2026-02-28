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
    """Values must match PostgreSQL job_status_enum exactly (OPEN/PAUSED/CLOSED/ARCHIVED/draft)."""
    DRAFT = "draft"          # JD uploaded, not yet finalized
    OPEN = "OPEN"
    PAUSED = "PAUSED"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class ApplicationStatus(enum.Enum):
    IN_REVIEW = "in_review"
    APPLIED = "applied"
    SHORTLISTED = "shortlisted"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    OFFER_EXTENDED = "offer_extended"
    REJECTED = "rejected"
    HIRED = "hired"


class ApplicationProcessingStage(enum.Enum):
    QUEUED = "queued"                    # job created, waiting for worker
    UPLOADED = "uploaded"                # files saved to storage
    EXTRACTING = "extracting"            # reading PDFs, extracting raw text
    PARSING = "parsing"                  # LLM parsing resume → structured data
    SCORING = "scoring"                  # LLM scoring / evaluation
    PERSISTING = "persisting"            # writing final results to DB
    COMPLETED = "completed"              # everything succeeded
    FAILED = "failed"                    # unrecoverable failure



class RubricSource(enum.Enum):
    MANUAL = "manual"
    AI = "ai"
    COMBINED = "combined"
    
class ResumeStatus(enum.Enum):
    UPLOADED = "uploaded"
    QUEUED_FOR_PARSING = "queued_for_parsing"
    PARSING_IN_PROGRESS = "parsing_in_progress"
    PARSED = "parsed"
    QUEUED_FOR_SCORING = "queued_for_scoring"
    SCORING_IN_PROGRESS = "scoring_in_progress"
    SCORED = "scored"
    ERROR = "error"
    
class AIProcessingStatus(enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    
class BulkUploadStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    
class DocumentProcessingStatus(enum.Enum):
    PENDING = "pending"      # Queued for parsing
    UPLOADED = "uploaded"
    PARSING_IN_PROGRESS = "parsing_in_progress"
    PARSED = "parsed"
    ERROR = "error"
    
class InterviewType(enum.Enum):
    IN_PERSON = "In Person"
    PHONE = "Phone"
    VIDEO_CALL = "Video Call"
    
class InterviewStatus(enum.Enum):
    COLLECTING_AVAILABILITY = "Collecting Availability"
    READY_TO_BOOK = "Ready to Book"
    SCHEDULED = "Scheduled"
    COMPLETED = "Completed"
    CANCELED = "Canceled"
    IN_PROGRESS = "In Progress"
    AWAITING_FEEDBACK = "Awaiting Feedback"
    FEEDBACK_COLLECTED = "Feedback Collected"
    
    
    
class PanelistResponseStatus(enum.Enum):
    SUBMITTED = "Submitted"
    EXPIRED = "Expired"
    PENDING = "Pending"
    
