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
from sqlalchemy.dialects.postgresql import JSONB,UUID,VARCHAR,TEXT

from configs.postgress_db import Base
from src.models.enums import InterviewStatus




class Interview(Base):
    __tablename__ = "interviews"
    

    id = Column(UUID(as_uuid=True), primary_key=True, index=True,default=uuid.uuid4)

    application_id = Column(
        UUID(as_uuid=True),
        ForeignKey("applications.id",),  
        nullable=False,
        index=True,
    )
    round_config_id = Column(
        UUID(as_uuid=True),
        ForeignKey("interview_round_configs.id",),  
        nullable=False,
        index=True,
    )
    
    round_number = Column(Integer, nullable=False,index=True)  # e.g., 1 for first round, 2 for second round, etc.
   
    status = Column(SAEnum(
        InterviewStatus,
        name="interview_status_enum",
        native_enum=True
    ),nullable=False,default=InterviewStatus.COLLECTING_AVAILABILITY,index=True)
    scheduled_start = Column(DateTime(timezone=True), nullable=True,index=True)
    scheduled_end = Column(DateTime(timezone=True), nullable=True)
    
    booking_token = Column(TEXT, nullable=True)  # Token for interview scheduling/booking systems
    booking_token_expires_at = Column(DateTime(timezone=True), nullable=True)  # Expiration time for the booking token
    cancelled_at = Column(DateTime(timezone=True), nullable=True)  # Timestamp for when the interview was cancelled, if applicable
    cancellation_reason = Column(TEXT, nullable=True)  # Reason for cancellation, if applicable
    
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now(),nullable=False)
    
    
    events = relationship(
        "Interview_TimeLine_Events",
        back_populates="interview",
         cascade="all, delete-orphan",
        order_by="Interview_TimeLine_Events.created_at",
    )
    
    application = relationship("Application", back_populates="interviews")
    round_config = relationship("Interview_Round_Configs", back_populates="interviews")
    panelist_availability = relationship("Panelist_Availability", back_populates="interview", cascade="all, delete-orphan")