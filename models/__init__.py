# IMPORTANT: import all models so Alembic can detect them
from models.user_model import User
from models.organization_model import Organization
from models.job_model import Job
from models.candidate_model import Candidate
from models.application_model import Application
from models.resume_model import Resume
from models.rubric_model import Rubric
from models.score_model import Score
from models.ai_processing_log_model import AIProcessingLogs
from models.bulk_upload_batches_model import BulkUploadBatches
from models.document_model import Document

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
]