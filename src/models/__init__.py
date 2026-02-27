# IMPORTANT: import all models so Alembic can detect them
from src.models.user_model import User
from src.models.organization_model import Organization
from src.models.job_model import Job
from src.models.candidate_model import Candidate
from src.models.application_model import Application
from src.models.resume_model import Resume
from src.models.rubric_model import Rubric
from src.models.score_model import Score
from src.models.ai_processing_log_model import AIProcessingLogs
from src.models.bulk_upload_batches_model import BulkUploadBatches
from src.models.document_model import Document
from src.models.waitlist_model import Waitlist

from src.models.interview_models.interviews import Interview
from src.models.interview_models.interview_rouns_configs import Interview_Round_Configs
from src.models.interview_models.interview_timeline_events import Interview_TimeLine_Events
from src.models.interview_models.panelist_availability import Panelist_Availability
from src.models.interview_models.calendly_connections import CalendlyCollection


__all__ = [
    "User",
    "Organization",
    "Job",
    "Candidate",
    "Application",
    "Resume",
    "Rubric",
    "Score",
    "AIProcessingLogs",
    "BulkUploadBatches",
    "Document",
    "Interview",
    "Interview_Round_Configs",
    "Interview_TimeLine_Events",
    "Panelist_Availability",
    "CalendlyCollection",
    "Waitlist",
]