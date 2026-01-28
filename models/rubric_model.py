from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    func,
    Boolean,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from configs.postgress_db import Base

class Rubric(Base):
    __tablename__ = "rubrics"

    id = Column(Integer, primary_key=True, index=True)

    job_id = Column(
        Integer,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,          
        index=True,
    )

    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, default=True)
    criteria = Column(JSONB, nullable=False)
    threshold_score = Column(Integer, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    job = relationship("Job", back_populates="rubrics")
    score = relationship(
        "Score",
        back_populates="rubric",
        uselist=False,
        cascade="all, delete-orphan",
    )
