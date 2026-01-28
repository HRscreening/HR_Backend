from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    func,
    Boolean,
    ForeignKey,
    DECIMAL
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from configs.postgress_db import Base

class Score(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True, index=True)

    job_id = Column(
        Integer,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,          
        index=True,
    )
    application_id = Column(
        Integer,
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rubric_id = Column(
        Integer,
        ForeignKey("rubrics.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    
    overall_score = Column(DECIMAL, nullable=False)
    ai_confidence = Column(DECIMAL, nullable=False)
    grounding_data = Column(JSONB, nullable=True)
    is_overridden = Column(Boolean, default=False)
    breakdown = Column(JSONB, nullable=True)

    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, default=True)
    criteria = Column(JSONB, nullable=False)
    threshold_score = Column(Integer, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    rubric = relationship("Rubric", back_populates="score")

