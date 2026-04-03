# IMPORTANT: import all models so Alembic can detect them
from src.models.user_model import User
from src.models.organization_model import Organization
from src.models.job_settings_model import JobSetting
from src.models.job_model import Job
from src.models.job_description_model import JobDescription
from src.models.application_form_config_model import ApplicationFormConfig
from src.models.candidate_model import Candidate
from src.models.application_model import Application
from src.models.resume_model import Resume
from src.models.rubric_model import Rubric
from src.models.score_model import Score
from src.models.ai_processing_log_model import AIProcessingLogs
from src.models.bulk_upload_batches_model import BulkUploadBatches
from src.models.document_model import Document
from src.models.waitlist_model import Waitlist
from src.modules.interviews.models import * 
from src.modules.reminders.model.reminder_model import Reminder
__all__ = [
    "User",
    "Organization",
    "Job",
    "JobDescription",
    "ApplicationFormConfig",
    "JobSetting",
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
    "InterviewAssessment",
    "Panelist",
    "Interview_Slot",
    "CalendarConnection",
    "Waitlist",
    "Reminder"
]