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
from sqlalchemy.dialects.postgresql import JSONB,UUID,TEXT

from configs.postgress_db import Base
from .enums import JobStatus 
class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)

    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    hiring_manager_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    title = Column(String, nullable=False)

    status = Column(
        SAEnum(
            JobStatus,
            name="job_status_enum",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=JobStatus.OPEN,
    )

    description = Column(TEXT, nullable=True)
    location = Column(String, nullable=True)
    salary = Column(String, nullable=True)
    target_headcount = Column(Integer, nullable=False, default=1)

    voice_ai_enabled = Column(Boolean, default=False)
    manual_rounds_count = Column(Integer, default=0)
    is_confidential = Column(Boolean, default=False)

    closing_reason = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    deleted_at = Column(DateTime(timezone=True), nullable=True)

    raw_jd_text = Column(TEXT, nullable=True)
    parsed_jd = Column(JSONB, nullable=True)
    ai_config = Column(JSONB, nullable=True)
    job_metadata = Column(JSONB, nullable=True)

    total_applications = Column(Integer, default=0)
    opened_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    # ── Public Apply columns ───────────────────────────────────────────────────
    # Unique slug for the shareable application URL (e.g. /apply/senior-backend-a7x3)
    # Uniqueness enforced by a partial index in the DB (excluding deleted rows).
    public_slug = Column(String(80), nullable=True)
    public_apply_enabled = Column(Boolean, nullable=False, default=False, server_default="false")

    # FK to the currently active JD version (use_alter avoids circular-FK issue at DDL time)
    active_jd_id = Column(
        UUID(as_uuid=True),
        ForeignKey("job_descriptions.id", ondelete="SET NULL", use_alter=True, name="fk_jobs_active_jd_id"),
        nullable=True,
    )
    # FK to the currently active form config version
    active_form_config_id = Column(
        UUID(as_uuid=True),
        ForeignKey("application_form_configs.id", ondelete="SET NULL", use_alter=True, name="fk_jobs_active_form_config_id"),
        nullable=True,
    )

    # ── relationships ──────────────────────────────────────────────────────────
    organization = relationship("Organization", back_populates="jobs")

    applications = relationship(
        "Application",
        back_populates="job",
        cascade="all, delete-orphan",
    )

    creator = relationship(
        "User",
        foreign_keys=[created_by_id],
        back_populates="created_jobs",
    )

    hiring_manager = relationship(
        "User",
        foreign_keys=[hiring_manager_id],
        back_populates="managed_jobs",
    )

    rubrics = relationship(
        "Rubric",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="Rubric.version",
    )
    
    interview_round_configs = relationship(
        "Interview_Round_Configs",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="Interview_Round_Configs.round_number",
    )

    job_descriptions = relationship(
        "JobDescription",
        back_populates="job",
        cascade="all, delete-orphan",
        foreign_keys="JobDescription.job_id",
        order_by="JobDescription.version_number",
    )

    form_configs = relationship(
        "ApplicationFormConfig",
        back_populates="job",
        cascade="all, delete-orphan",
        foreign_keys="ApplicationFormConfig.job_id",
        order_by="ApplicationFormConfig.version_number",
    )

    # Convenience accessors — use post_update to resolve the circular FK
    active_jd = relationship(
        "JobDescription",
        foreign_keys=[active_jd_id],
        post_update=True,
        uselist=False,
    )

    active_form_config = relationship(
        "ApplicationFormConfig",
        foreign_keys=[active_form_config_id],
        post_update=True,
        uselist=False,
    )
