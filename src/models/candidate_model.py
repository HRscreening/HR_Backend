from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    func,
    Boolean,
    String,
    ForeignKey,
    UniqueConstraint,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import UUID,TEXT
import uuid
from sqlalchemy.orm import relationship
from configs.postgress_db import Base

class Candidate(Base):
    __tablename__ = "candidates"
    
    

    id = Column(UUID(as_uuid=True), primary_key=True, index=True,default=uuid.uuid4)

    # if same candidate  can be in multiple orgs then no need for organization_id unique constraint
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id",),  
        nullable=True,
        index=True,
    )
    
    #TODO: Add unique constraint on (organization_id, email) and (organization_id, phone) later if needed.
    #TODO: Add validation that at a time wither organization_id is null or created_by_user_id is null. 
    # TODO: For those candidates created by user not in any organization, 
    created_by_user_id = Column(
        UUID(as_uuid=True),ForeignKey("users.id", ondelete="SET NULL"),nullable=True,index=True)



    merged_into_id = Column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="SET NULL"),
        nullable=True,
    )

    full_name = Column(String, nullable=False)
    email = Column(String, nullable=True)  
    phone = Column(String, nullable=True)  


    total_applications = Column(Integer, default=0)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now(),nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    email_hash = Column(String, nullable=True)  # A hash of the email — used for fast dedup detection without exposing raw PII in search queries.
    public_url = Column(TEXT, nullable=True)  # A public-facing URL for the candidate profile, if enabled.
    
    
    
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
    )
