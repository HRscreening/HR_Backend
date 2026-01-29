from sqlalchemy import Column, Integer, String, DateTime, func, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SAEnum
from configs.postgress_db import Base
from models.enums import UserRole
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
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    user_metadata = Column(JSONB, nullable=True)

    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True
    )

    organization = relationship("Organization", back_populates="users")
    jobs = relationship("Job", back_populates="created_by")
