from typing import List
from pydantic import BaseModel, Field


class ResumeParsingJobSchema(BaseModel):
    db_job_id: str = Field(..., description="Unique identifier for the resume in the database")
    redis_job_id: str = Field(..., description="Unique identifier for the job in Redis")
    batch_id: str = Field(..., description="Identifier for the batch this job belongs to")
    file_path: str = Field(..., description="Path to the resume file to be parsed")
    
    