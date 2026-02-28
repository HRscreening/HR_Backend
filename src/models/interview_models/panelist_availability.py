from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    func,
    Boolean,
    ForeignKey,
)
from sqlalchemy import Enum as SAEnum, UniqueConstraint
import uuid
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB,UUID,VARCHAR,TEXT

from configs.postgress_db import Base
from src.models.enums import PanelistResponseStatus




class Panelist_Availability(Base):
    __tablename__ = "panelist_availability"
    __table_args__ = (
    UniqueConstraint(
        "round_config_id",
        "panelist_email",
        name="uq_round_panelist"
        ),
    )
    
    
    id = Column(UUID(as_uuid=True), primary_key=True, index=True,default=uuid.uuid4)

    interview_id = Column(
        UUID(as_uuid=True),
        ForeignKey("interviews.id"),
        nullable=False,
        index=True,
    )
    # if same candidate  can be in multiple orgs then no need for organization_id unique constraint
    round_config_id = Column(
        UUID(as_uuid=True),
        ForeignKey("interview_round_configs.id"),  
        nullable=False,
        index=True,
    )
    panelist_email = Column(String, nullable=False,index=True)  # Email of the panelist whose availability is being tracked
    panelist_name = Column(String, nullable=True)  # Optional: Name of the panelist for easier identification
    response_status = Column(SAEnum(
        PanelistResponseStatus,
        name="panelist_response_status_enum",
        native_enum=True
    ),nullable=False,default=PanelistResponseStatus.PENDING)  # Status of the panelist's response (e.g., Pending, Accepted, Declined)
    responded_at = Column(DateTime(timezone=True), nullable=True)  # Timestamp of when the panelist responded
    
    available_slots = Column(JSONB, nullable=True)  # Optional: List of available time slots provided by the panelist (if they accepted)
    availability_token = Column(TEXT, nullable=False)  # e.g., 1 for first round, 2 for second round, etc.
    token_expires_at = Column(DateTime(timezone=True), nullable=False)  # Expiration time for the availability token
    calendly_connected = Column(Boolean, nullable=False, default=False)  # Indicates if the panelist has connected their Calendly for automatic scheduling
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now(),nullable=False)
    interview = relationship("Interview", back_populates="panelist_availability")
    round_config = relationship("Interview_Round_Configs",back_populates="panelist_availability")