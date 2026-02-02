from typing import Dict, Optional, Any
from uuid import UUID
from pydantic import BaseModel
from enum import Enum


class JobStatus(str, Enum):
    OPEN = "open"
    PAUSED = "paused"
    CLOSED = "closed"
    ARCHIVED = "archived"


class ApplicationStatus(str, Enum):
    APPLIED = "applied"
    SHORTLISTED = "shortlisted"
    REJECTED = "rejected"
    HIRED = "hired"
    WITHDRAWN = "withdrawn"


# -------- Job --------
class JobOverviewJob(BaseModel):
    id: UUID
    title: str
    status: JobStatus
    target_headcount: int


# -------- Dashboard --------
class JobDashboardAnalytics(BaseModel):
    total_applications: int
    by_status: Dict[ApplicationStatus, int]


# -------- Criteria --------
class JobCriteria(BaseModel):
    rubric_id: UUID
    version: int
    threshold_score: Optional[int]
    criteria: Dict[str, Any]


# -------- Settings --------
class JobSettings(BaseModel):
    voice_ai_enabled: bool
    manual_rounds_count: int
    is_confidential: bool
    job_metadata: Optional[Dict[str, Any]]
    closing_reason: Optional[str]


# -------- Final Response --------
class JobOverviewResponse(BaseModel):
    job: JobOverviewJob
    dashboard: JobDashboardAnalytics
    criteria: JobCriteria
    settings: JobSettings
