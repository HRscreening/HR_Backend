from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    func,
    Boolean,
    ForeignKey,
)
from sqlalchemy import Enum as SAEnum
import uuid
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB,UUID

from configs.postgress_db import Base
from .enums import JobStatus 

class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True,default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True),ForeignKey("organizations.id", ondelete="CASCADE"),nullable=True,index=True)
    created_by_id = Column(UUID(as_uuid=True),ForeignKey("users.id", ondelete="RESTRICT"),nullable=False,index=True)
    title = Column(String, nullable=False)
    status = Column(
    SAEnum(JobStatus, name="job_status_enum", native_enum=True),
    nullable=False,
    default=JobStatus.OPEN,
)
    description = Column(String, nullable=True)
    location = Column(String, nullable=True)
    salary = Column(String, nullable=True)
    target_headcount = Column(Integer, nullable=False)
    voice_ai_enabled = Column(Boolean, default=False)
    manual_rounds_count = Column(Integer, default=0)
    is_confidential = Column(Boolean, default=False)
    closing_reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True),server_default=func.now(),nullable=False)
    job_metadata = Column(JSONB, nullable=True)  

    # relationships
    organization = relationship("Organization", back_populates="jobs")
    applications = relationship("Application",back_populates="job",cascade="all, delete-orphan",)
    created_by = relationship("User", back_populates="jobs")
    rubrics = relationship(
        "Rubric",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="Rubric.version",
    )
