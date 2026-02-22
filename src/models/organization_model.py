from sqlalchemy import Column, Integer, String, DateTime, func,ForeignKey
from sqlalchemy.dialects.postgresql import UUID,JSONB
from sqlalchemy.orm import relationship
from configs.postgress_db import Base
import uuid

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID, primary_key=True, index=True,default=uuid.uuid4)
    name = Column(String, nullable=False,unique=True)
    email = Column(String, nullable=False,unique=True)
    address = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(),nullable=False)

    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,        #  esnuring only one organization per user
        nullable=False
    )
    
    
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
    DateTime(timezone=True),
    server_default=func.now(),
    onupdate=func.now(),
    nullable=False
)

    subscription_tier = Column(String, nullable=True)
    subscription_status = Column(String, nullable=True)  # enum to be added later
    limits = Column(JSONB, nullable=True)  # Store various limits as JSON
    settings = Column(JSONB, nullable=True)  # Store organization-specific settings as JSON 

    users = relationship(
    "User",
    back_populates="organization",
    foreign_keys="User.organization_id",
    passive_deletes=True
)


    
    jobs = relationship(
        "Job",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    
    candidates = relationship(
        "Candidate",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
      
    creator = relationship(
        "User",
        foreign_keys=[created_by],  
        uselist=False,
    )
