from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    func,
    Boolean,
    String,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy.orm import relationship
from configs.postgress_db import Base

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True,default=uuid.uuid4)

    # if same candidate  can be in multiple orgs then no need for organization_id 
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id",),  
        nullable=True,
        index=True,
    )


    merged_into_id = Column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="SET NULL"),
        nullable=True,
    )

    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=True)
    phone = Column(String, unique=True, nullable=True)


    total_applications = Column(Integer, default=0)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # 🔹 relationships
    organization = relationship("Organization", back_populates="candidates")


    # self-referencing merge
    merged_into = relationship(
        "Candidate",
        remote_side=[id],
        back_populates="merged_candidates",
    )

    merged_candidates = relationship(
        "Candidate",
        back_populates="merged_into",
        cascade="save-update",
    )

    # one candidate → many applications
    applications = relationship(
        "Application",
        back_populates="candidate",
        cascade="all, delete-orphan",
    )
    
    resumes = relationship(
        "Resume",
        back_populates="candidate",
        cascade="all, delete-orphan", 
    )
