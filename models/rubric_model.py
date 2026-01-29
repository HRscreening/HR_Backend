from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    func,
    Boolean,
    ForeignKey
)
import uuid
from sqlalchemy.dialects.postgresql import JSONB,UUID
from sqlalchemy.orm import relationship
from configs.postgress_db import Base


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
    is_active = Column(Boolean, default=True)
    criteria = Column(JSONB, nullable=False)
    threshold_score = Column(Integer)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    job = relationship("Job", back_populates="rubrics")

    scores = relationship(           # ✅ plural
        "Score",
        back_populates="rubric",
        cascade="all, delete-orphan",
    )
