from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    func,
    Boolean,
    ForeignKey,
    Numeric,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint
import uuid

from configs.postgress_db import Base


class Score(Base):
    __tablename__ = "scores"

    __table_args__ = (
        UniqueConstraint("application_id", "rubric_id", name="uq_app_rubric"),
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

    grounding_data = Column(JSONB)
    breakdown = Column(JSONB)
    criteria = Column(JSONB, nullable=False)

    threshold_score = Column(Integer)
    is_overridden = Column(Boolean, default=False)

    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, default=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    rubric = relationship("Rubric", back_populates="scores")
    application = relationship("Application", back_populates="scores")
