from sqlalchemy import Column, Integer, String, DateTime, func, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SAEnum
from configs.postgress_db import Base
from src.models.enums import UserRole
from sqlalchemy.dialects.postgresql import JSONB,UUID
import uuid

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True,default=uuid.uuid4)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)

    role = Column(
        SAEnum(UserRole, native_enum=True, name="userrole"),
        nullable=False,
        default=UserRole.INDIVIDUAL
    )

    password = Column(String, nullable=False)
    email_verified = Column(Boolean, default=False)
    otp = Column(String, nullable=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())  # Timestamp when the user joined/created account
    user_metadata = Column(JSONB, nullable=True)
    
    
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),onupdate=func.now(), nullable=False)
    
    preferences = Column(JSONB, nullable=True)  #  User's UI preferences — theme, timezone, notification settings.
    permissions = Column(JSONB, nullable=True)  #  Granular permission flags beyond the base role. Allows finetuning access per user.
    last_login_at = Column(DateTime(timezone=True), nullable=True)  # Timestamp of the user's last login.
    login_count = Column(Integer, default=0)  # Total number of times the user has logged in.

    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        index=True,
        nullable=True
    )

    organization = relationship("Organization", back_populates="users",foreign_keys=[organization_id])

    
    created_jobs = relationship(
        "Job",
        foreign_keys="Job.created_by_id",
        back_populates="creator",
    )

    managed_jobs = relationship(
        "Job",
        foreign_keys="Job.hiring_manager_id",
        back_populates="hiring_manager",
    )

    calendar_connections = relationship(
        "CalendarConnection",
        back_populates="user",
        cascade="all, delete-orphan",
    )
