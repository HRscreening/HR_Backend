from sqlalchemy import Column, Integer, String, DateTime, func,Boolean,ForeignKey,Enum
from sqlalchemy.orm import relationship
from configs.postgress_db import Base
from models.enums import UserRole
from sqlalchemy.dialects.postgresql import JSONB

class User(Base):
    __tablename__ = "users"   # lowercase is best practice

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    role = Enum(UserRole, nullable=False, default=UserRole.INDIVIDUAL)  # role in the organization if in it else INDIVIDUAL
    
    password = Column(String, nullable=False)
    email_verified = Column(Boolean, default=False)
    otp = Column(String, nullable=True) # For storing OTP temporarily , Will have to hash later and also expiry mechanism
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    user_metadata = Column(JSONB, nullable=True)  # JSON string for additional metadata
    
    organization_id = Column(
    Integer,
    ForeignKey("organizations.id", ondelete="SET NULL"),
    nullable=True
    )

    organization = relationship(
        "Organization",
        back_populates="users"
    )


    
    # User can create multiple Jobs
    jobs = relationship(
        "Job",
        back_populates="created_by",
    )
