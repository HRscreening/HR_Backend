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
    UPLOADED = "uploaded"
    PARSING_IN_PROGRESS = "parsing_in_progress"
    PARSED = "parsed"
    ERROR = "error"