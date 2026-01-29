from sqlalchemy import Column, Integer, String, DateTime, func,ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from configs.postgress_db import Base
import uuid

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID, primary_key=True, index=True,default=uuid.uuid4)
    name = Column(String, nullable=False,unique=True)
    email = Column(String, nullable=False,unique=True)
    address = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,        
        nullable=False
    )

    users = relationship(
    "User",
    back_populates="organization",
    cascade="all, delete-orphan",
    foreign_keys="User.organization_id"
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
