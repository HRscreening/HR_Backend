from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    func,
    Boolean,
    ForeignKey,
)
from sqlalchemy import Enum as SAEnum
import uuid
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID,VARCHAR,TEXT

from configs.postgress_db import Base




class CalendlyCollection(Base):
    __tablename__ = "calendly_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True,default=uuid.uuid4)

    panelist_email = Column(String, nullable=False,index=True,unique=True)  # Email of the panelist whose availability is being tracked
    calendly_user_uri = Column(String, nullable=False)  # The unique URI identifier for
    access_token = Column(TEXT, nullable=False)  # The access token for accessing the Calendly API on behalf of the panelist
    refresh_token = Column(TEXT, nullable=True)  # Optional: Refresh token if using OAuth for long-term access
    token_expires_at = Column(DateTime(timezone=True), nullable=False)  # Exp
    
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
