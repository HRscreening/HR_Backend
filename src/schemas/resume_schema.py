from pydantic import BaseModel, Field
from src.models.enums import ResumeStatus

class ResumeCreateSchema(BaseModel):
    application_id: str = Field(..., description="ID of the application this resume is associated with")
    raw_file_url: str = Field(..., description="URL where the raw resume file is stored")
    parsed_text: str = Field(..., description="Extracted text content from the resume")
    page_count: int = Field(..., description="Number of pages in the resume")
    status: ResumeStatus = Field(..., description="Processing status of the resume (e.g., 'pending', 'processed', 'error')")