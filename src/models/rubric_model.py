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

    version = Column(Integer, nullable=False, default=1) #TODO: MAke it unique per job_id and increment on update
    is_active = Column(Boolean, default=True)  # Only one active rubric per job at a time
    criteria = Column(JSONB, nullable=False)
    threshold_score = Column(Numeric(5,2), nullable=False, default=0)  # Minimum score required for passing

    created_at = Column(DateTime(timezone=True),server_default=func.now(),nullable=False)
    updated_at = Column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now(),nullable=False)

    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    # NOTE: In the current DB, `rubrics.source` is VARCHAR (not a Postgres enum).
    # Store the enum *value* (e.g. "ai" / "manual" / "combined") to match the DB.
    source = Column(String, nullable=True, default=RubricSource.AI.value)
    ai_metadata = Column(JSONB, nullable=True)  # If source is ai, this stores details about the extraction — model used, confidence, etc.

    # Versioning / audit (production-grade)
    parent_rubric_id = Column(UUID(as_uuid=True), ForeignKey("rubrics.id", ondelete="SET NULL"), nullable=True)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_via = Column(String, nullable=True)      # e.g. "create_job", "ui_edit", "ai_regen"
    change_reason = Column(String, nullable=True)    # e.g. "edit", "ai_regen", "copy"
    change_type = Column(String, nullable=True)      # e.g. "minor", "major"
    
    
    job = relationship("Job", back_populates="rubrics")

    scores = relationship(           
        "Score",
        back_populates="rubric",
        cascade="all, delete-orphan",
    )
