from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    func,
    Boolean,
    ForeignKey,
    String,
    Numeric,
)
import uuid
from sqlalchemy.dialects.postgresql import JSONB,UUID
from sqlalchemy.orm import relationship
from configs.postgress_db import Base
from sqlalchemy import Enum as SAEnum
from .enums import RubricSource


class Rubric(Base):
    __tablename__ = "rubrics"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)

    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, default=True)  # Only one active rubric per job at a time
    criteria = Column(JSONB, nullable=False)
    threshold_score = Column(Numeric(5,2), nullable=False, default=0)  # Minimum score required for passing

    created_at = Column(DateTime(timezone=True),server_default=func.now(),nullable=False)
    updated_at = Column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now(),nullable=False)

    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    source = Column(SAEnum(RubricSource,native_enum=True ,name="rubric_source_enum"), nullable=True,default=RubricSource.AI)  # Source of the rubric (e.g., 'system_generated', 'custom_created')
    ai_metadata = Column(JSONB, nullable=True)  # If source is ai, this stores details about the extraction — model used, confidence, etc.
    
    
    job = relationship("Job", back_populates="rubrics")

    scores = relationship(           
        "Score",
        back_populates="rubric",
        cascade="all, delete-orphan",
    )
