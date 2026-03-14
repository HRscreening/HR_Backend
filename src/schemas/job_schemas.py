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










# ------------ From Keshav's Versoin -------------


from pydantic import BaseModel, field_validator
from typing import Dict, Optional,Any


class SubCriterionSchema(BaseModel):
    weight: int
    value: Optional[str] = None

class CriterionSchema(BaseModel):
    weight: int
    value: Optional[str] = None
    sub_criteria: Optional[Dict[str, SubCriterionSchema]] = None

    @field_validator("weight")
    @classmethod
    def validate_weight(cls, v):
        if v < 0:
            raise ValueError("weight must be non-negative")
        return v


    @field_validator("sub_criteria")
    @classmethod
    def validate_sub_criteria(cls, sub, info):
        if not sub:
            return sub

        total = sum(c.weight for c in sub.values())

        if total != 100:
            raise ValueError(
                f"sub_criteria weights must sum to 100 (got {total})"
            )

        return sub


class JobDataSchema(BaseModel):
    title: str
    description: str
    location: str | None = None
    salary: str | None = None
    target_headcount: int
    metadata: Dict[str, Any] | None = None
    


class ExtractedJDSchema(BaseModel):
    job_data: JobDataSchema
    threshold_score: int
    mandatory_criteria: Dict[str, CriterionSchema]
    screening_criteria: Dict[str, CriterionSchema]

    @field_validator("threshold_score")
    @classmethod
    def validate_threshold_score(cls, v):
        if v < 0:
            raise ValueError("threshold_score must be non-negative")
        return v

class Criterion(BaseModel):
    mandatory_criteria: Dict[str, CriterionSchema]
    screening_criteria: Dict[str, CriterionSchema]
    

class ExtendedJobDataSchema(JobDataSchema):
    metadata: Dict[str, Any] | None = None
    voice_ai_enabled: bool = False
    manual_rounds_count: int = 0
    is_confidential: bool = False

class NewJobSchema(BaseModel):  
    job_data:ExtendedJobDataSchema
    threshold_score:int
    criteria:Criterion
    
class JobOverviewInfo(BaseModel):
    id: UUID
    title: str
    status: str  # or JobStatus if Enum
    description: str
    created_at: datetime
    salary: Optional[str]
    location: Optional[str]
    target_headcount: Optional[int]
    current_batch_id: Optional[UUID]

class DashboardInfo(BaseModel):
    total_applications: int
    by_status: Dict[str, int]
    avg_score: float

class CriteriaOverview(BaseModel):
    current_active_version: Optional[int]
    active_rubric_id: Optional[UUID] | int | str
    versions: List[RubricVersionInfo]

class RoundSlotsInfo(BaseModel):
    round_number: int
    round_config_id: str | UUID
    slots_available : bool

class JobOverviewResponseNew(BaseModel):
    job: JobOverviewInfo
    round_slots:List[RoundSlotsInfo] | None
    dashboard: DashboardInfo
    criteria: CriteriaOverview
    
    
class JobSettings(BaseModel):
    title:str
    description:Optional[str]
    location: Optional[str]
    salary: Optional[str]
    status: JobStatus
    target_headcount: int
    manual_rounds_count: int
    
    
class JobSettingsResposnse(BaseModel):
    job_settings: JobSettings
    voice_ai_enabled: bool
    is_confidential: bool
    job_metadata: Optional[Dict[str, Any]]
    closing_reason: Optional[str]

