from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    func,
    ForeignKey,
    Index,
)
import uuid
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from configs.postgress_db import Base

# ── Default question set ───────────────────────────────────────────────────────
# Always-included fields (removable=False) must stay at the top.
# Remaining fields are on by default but the recruiter can toggle them off.
DEFAULT_QUESTIONS = [
    {
        "id": "q_full_name",
        "key": "full_name",
        "label": "Full Name",
        "type": "text",
        "required": True,
        "removable": False,
        "placeholder": "Enter your full name",
    },
    {
        "id": "q_email",
        "key": "email",
        "label": "Email Address",
        "type": "email",
        "required": True,
        "removable": False,
        "placeholder": "you@example.com",
    },
    {
        "id": "q_resume",
        "key": "resume",
        "label": "Resume",
        "type": "file",
        "required": True,
        "removable": False,
        "placeholder": "Upload your resume (PDF or DOCX, max 5 MB)",
    },
    {
        "id": "q_phone",
        "key": "phone",
        "label": "Phone Number",
        "type": "text",
        "required": False,
        "removable": True,
        "placeholder": "+91 98765 43210",
    },
    {
        "id": "q_current_role",
        "key": "current_role",
        "label": "Current Job Title",
        "type": "text",
        "required": False,
        "removable": True,
        "placeholder": "e.g. Software Engineer",
    },
    {
        "id": "q_current_company",
        "key": "current_company",
        "label": "Current Company",
        "type": "text",
        "required": False,
        "removable": True,
        "placeholder": "e.g. Acme Corp",
    },
    {
        "id": "q_experience_years",
        "key": "experience_years",
        "label": "Total Years of Experience",
        "type": "number",
        "required": False,
        "removable": True,
        "placeholder": "e.g. 5",
    },
    {
        "id": "q_location",
        "key": "location",
        "label": "Current Location / City",
        "type": "text",
        "required": False,
        "removable": True,
        "placeholder": "e.g. Bangalore",
    },
    {
        "id": "q_linkedin",
        "key": "linkedin_url",
        "label": "LinkedIn Profile URL",
        "type": "url",
        "required": False,
        "removable": True,
        "placeholder": "https://linkedin.com/in/...",
    },
    {
        "id": "q_portfolio",
        "key": "portfolio_url",
        "label": "Portfolio / GitHub URL",
        "type": "url",
        "required": False,
        "removable": True,
        "placeholder": "https://github.com/...",
    },
    {
        "id": "q_notice_period",
        "key": "notice_period",
        "label": "Notice Period / Available From",
        "type": "text",
        "required": False,
        "removable": True,
        "placeholder": "e.g. Immediate / 30 days",
    },
    {
        "id": "q_expected_salary",
        "key": "expected_salary",
        "label": "Expected Salary / CTC",
        "type": "text",
        "required": False,
        "removable": True,
        "placeholder": "e.g. 15 LPA",
    },
]

# Allowed question field types for validation
ALLOWED_QUESTION_TYPES = {"text", "email", "number", "url", "textarea", "file", "select", "boolean"}


class ApplicationFormConfig(Base):
    __tablename__ = "application_form_configs"
    __table_args__ = (
        Index("afc_job_id_version_uq", "job_id", "version_number", unique=True),
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
        nullable=True,
        index=True,
    )

    # Ordered array of question objects (JSONB preserves insertion order)
    questions = Column(JSONB, nullable=False, default=lambda: list(DEFAULT_QUESTIONS))

    version_number = Column(Integer, nullable=False, default=1)

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

    # ── Relationships ──────────────────────────────────────────────────────────
    job = relationship("Job", back_populates="form_configs", foreign_keys=[job_id])
    creator = relationship("User", foreign_keys=[created_by_id])
