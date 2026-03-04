from sqlalchemy import (
    Column,
    String,
    DateTime,
    func,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
import uuid
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, TEXT

from configs.postgress_db import Base
from src.models.enums import CalendarProvider


class CalendarConnection(Base):
    """
    Stores OAuth calendar connections for panelists and HR users.
    Supports Google Calendar and Microsoft Outlook.
    A user can have one connection per provider.
    """

    __tablename__ = "calendar_connections"
    __table_args__ = (
        UniqueConstraint(
            "provider_email",
            "provider",
            name="uq_provider_email_provider",
        ),
    )

    id = Column(
        UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4
    )

    provider_email = Column(String, nullable=False, index=True)

    # Set when the connected user is a registered HR user; null for external panelists
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    provider = Column(
        SAEnum(
            CalendarProvider,
            name="calendar_provider_enum",
            native_enum=True,
        ),
        nullable=False,
    )

    # Provider-specific user identifier (Google 'sub' / Microsoft 'oid')
    provider_user_id = Column(String, nullable=True)

    access_token = Column(TEXT, nullable=False)
    refresh_token = Column(TEXT, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=False)

    # Space-separated OAuth scopes that were granted
    scopes = Column(TEXT, nullable=True)

    connected_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="calendar_connections")
