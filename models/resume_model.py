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
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
import uuid


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True,default=uuid.uuid4)

    application_id = Column(
        UUID(as_uuid=True),
        ForeignKey("applications.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    candidate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
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
