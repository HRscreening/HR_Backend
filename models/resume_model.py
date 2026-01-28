from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    func,
    Boolean,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from configs.postgress_db import Base
from pgvector.sqlalchemy import Vector

class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)

    application_id = Column(
        Integer,
        ForeignKey("applications.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    candidate_id = Column(
        Integer,
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    is_current = Column(Boolean, default=False)

    raw_file_url = Column(String, nullable=False)

    parsed_text = Column(String, nullable=True)
    page_count = Column(Integer, nullable=True)

    embedding = Column(Vector(1536), nullable=True)

    uploaded_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    

    # relationships (singular, no cascade here)
    application = relationship(
        "Application",
        back_populates="resume"
    )

    candidate = relationship(
        "Candidate",
        back_populates="resumes",
    )
