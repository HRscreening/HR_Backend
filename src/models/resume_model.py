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
from sqlalchemy.dialects.postgresql import UUID,TEXT
from pgvector.sqlalchemy import Vector
import uuid
from sqlalchemy import Enum as SAEnum
from .enums import ResumeStatus



class Resume(Base):
    __tablename__ = "resumes"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True,default=uuid.uuid4)

    application_id = Column(
        UUID(as_uuid=True),
        ForeignKey("applications.id"), # No cascade delete to preserve resume data even if application is deleted for candidate history
        nullable=False,
        unique=True,
        index=True,
    )

    candidate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=True,                                  # Nullable because resume can exist without being linked to a candidate yet
        index=True,
    )
    
    raw_file_url = Column(TEXT, nullable=True)  # Nullable at time of creation because file might be processed later

    parsed_text = Column(TEXT, nullable=True)
    page_count = Column(Integer, nullable=True)

    embedding = Column(Vector(1536), nullable=True)

    uploaded_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    status = Column(
        SAEnum(ResumeStatus, native_enum=True, name="resume_status_enum"),
        nullable=False,
        default=ResumeStatus.UPLOADED,
        server_default=ResumeStatus.UPLOADED.value,
    )
    
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    

    # relationships (singular, no cascade here)
    application = relationship(
        "Application",
        foreign_keys=[application_id],
        uselist=False
    )

    candidate = relationship(
        "Candidate",
        back_populates="resumes",
    )
