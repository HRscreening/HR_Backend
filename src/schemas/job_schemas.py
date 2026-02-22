from typing import Dict, Optional, Any, List
from datetime import datetime
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


# -------- Rubric Versions (for audit + switching) --------
class RubricVersionInfo(BaseModel):
    rubric_id: UUID
    version: int
    is_active: bool
    source: Optional[str] = None
    created_at: Optional[datetime] = None
    created_by_id: Optional[UUID] = None
    created_via: Optional[str] = None
    change_reason: Optional[str] = None
    change_type: Optional[str] = None
    parent_rubric_id: Optional[UUID] = None


class RubricVersionsResponse(BaseModel):
    job_id: UUID
    active_rubric_id: Optional[UUID] = None
    versions: List[RubricVersionInfo]


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
