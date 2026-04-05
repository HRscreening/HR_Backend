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




class Panelist(Base):
    __tablename__ = "panelist"
    __table_args__ = (
    UniqueConstraint(
        "round_config_id",
        "email",
        name="uq_round_panelist"
        ),
    )
    
    
    id = Column(UUID(as_uuid=True), primary_key=True, index=True,default=uuid.uuid4)

    # if same candidate  can be in multiple orgs then no need for organization_id unique constraint
    round_config_id = Column(
        UUID(as_uuid=True),
        ForeignKey("interview_round_configs.id",ondelete="CASCADE"),  
        nullable=False,
        index=True,
        
    )
    email = Column(String, nullable=False,index=True)  # Email of the panelist whose availability is being tracked
    name = Column(String, nullable=True)  # Optional: Name of the panelist for easier identification
    role = Column(String, nullable=True)  # Optional: Role of the panelist (e.g., Interviewer, Technical Lead, HR, etc.)
    
    response_status = Column(SAEnum(
        PanelistResponseStatus,
        name="panelist_response_status_enum",
        native_enum=True
    ),nullable=False,default=PanelistResponseStatus.NOT_REQUESTED)  # Status of the panelist's response (e.g., Pending, Accepted, Declined)
    

    availability_token = Column(TEXT, nullable=True)  # e.g., 1 for first round, 2 for second round, etc.
    token_expires_at = Column(DateTime(timezone=True), nullable=True)  # Expiration time for the availability token
        
    edit_token = Column(TEXT, nullable=True)  # Token for interview rescheduling
    edit_token_expires_at = Column(DateTime(timezone=True), nullable=True)  # Expiration time for the rescheduling token
    
    last_requested_at = Column(DateTime(timezone=True), nullable=True)  # Timestamp of the last availability request sent to the panelist
    availability_request_count = Column(Integer, default=0)  # Counter for how many times availability has been requested from the panelist
    
    # TODO: to be implemented here and in service/repo layer too
    is_deleted = Column(Boolean, default=False)  # Soft delete flag to indicate if the panelist record is deleted
    
    calendar_connected = Column(Boolean, default=False)  # Indicates if the panelist has connected a calendar (Google/Microsoft) for automatic scheduling
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    slots = relationship("Interview_Slot",back_populates="panelist",cascade="all, delete-orphan")
    updated_at = Column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now(),nullable=False)
    round_config = relationship("Interview_Round_Configs",back_populates="panelists")
    assessments = relationship("InterviewAssessment", back_populates="panelist")