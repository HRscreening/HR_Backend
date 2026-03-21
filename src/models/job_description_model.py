from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    func,
    ForeignKey,
    Index,
    text,
)
import uuid
from sqlalchemy.dialects.postgresql import JSONB, UUID, TEXT
from sqlalchemy.orm import relationship

from configs.postgress_db import Base


class JobDescription(Base):
    __tablename__ = "job_descriptions"
    __table_args__ = (
        Index("jd_job_id_version_uq", "job_id", "version_number", unique=True),
        Index(
            "jd_one_active_per_job_uq",
            "job_id",
            unique=True,
            postgresql_where=text("status = 'active' AND deleted_at IS NULL"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)

    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    version_number = Column(Integer, nullable=False, default=1)

    title = Column(String, nullable=False)
    content = Column(TEXT, nullable=False)  # Full markdown JD text

    # Q&A answers used by the AI builder — null for manually written JDs
    raw_answers = Column(JSONB, nullable=True)

    # 'ai_builder' | 'manual' | 'upload'
    generation_method = Column(String(20), nullable=True)

    # 'draft' | 'active' | 'archived'
    status = Column(String(20), nullable=False, server_default="draft")

    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────────
    job = relationship("Job", back_populates="job_descriptions", foreign_keys=[job_id])
    creator = relationship("User", foreign_keys=[created_by_id])
