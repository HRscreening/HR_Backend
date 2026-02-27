from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    func,
    Boolean,
    ForeignKey,
    Numeric,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB,VARCHAR
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint
import uuid

from configs.postgress_db import Base


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (
        UniqueConstraint('application_id', 'rubric_id', name='uq_app_rubric'),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )


    application_id = Column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    rubric_id = Column(
        UUID(as_uuid=True),
        ForeignKey("rubrics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    overall_score = Column(Numeric(5, 2), nullable=False)
    ai_confidence = Column(Numeric(3, 2), nullable=False)

    grounding_data = Column(JSONB, nullable=True)
    breakdown = Column(JSONB, nullable=True)
    raw_overall_score = Column(Numeric(5, 2), nullable=True, index=True)  # The original overall score before any overrides, for auditing purposes.
    scoring_method = Column(VARCHAR(50), nullable=True, index=True)  # E.g., "AI_Model_v1", "Recruiter_123", etc. Useful for tracking how the score was generated.
    
    criteria = Column(JSONB, nullable=False) #A snapshot of the rubric criteria at the time of scoring. Ensures the score record is self contained even if the rubric changes later.
    threshold_score = Column(Numeric(5, 2), nullable=False) # The threshold that was in effect when this score was calculated. For historical reference.

    is_overridden = Column(Boolean, default=False)

    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True),server_default=func.now(),nullable=False)
    updated_at = Column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now(),nullable=False)

    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    scored_by = Column(VARCHAR(50), nullable=True)  # Identifier for who or what scored the application (e.g., 'AI_Model_v1', 'Recruiter_123')
    ai_model = Column(VARCHAR(255), nullable=True)  # Which AI model was used to generate this score, Useful for auditing and comparing model performance.
    is_latest = Column(Boolean, default=True)  # Indicates if this is the latest score for the application-rubric pair

    rubric = relationship("Rubric", back_populates="scores")
    application = relationship("Application", back_populates="scores")
