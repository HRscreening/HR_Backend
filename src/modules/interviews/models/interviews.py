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
from src.modules.interviews.models.interview_timeline_events import Interview_TimeLine_Events



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
    
    # TODO: Add summary,transcript,feedback fields later when we have the interview recording and feedback collection features implemented.
    meet_link = Column(TEXT, nullable=True)  # Link to the video conferencing meeting (e.g., Zoom, Google Meet)
    summary = Column(JSONB, nullable=True)  # AI Generated Summary coming from fireflies for now, can be used to store summary of the interview, key points discussed, etc.
    transcript_id = Column(VARCHAR(255), nullable=True)  # To store the transcript ID from Fireflies, which can be used to fetch the transcript and other details later.
    calendar_event_id = Column(VARCHAR(255), nullable=True)  # To store the calendar event ID for easy updates/deletions from calendar.
    
    scheduled_start = Column(DateTime(timezone=True), nullable=True,index=True)
    scheduled_end = Column(DateTime(timezone=True), nullable=True)
    
    booking_token = Column(TEXT, nullable=True)  # Token for interview scheduling/booking systems
    booking_token_expires_at = Column(DateTime(timezone=True), nullable=True)  # Expiration time for the booking token
    
    rescheduling_token = Column(TEXT, nullable=True)  # Token for interview rescheduling
    rescheduling_token_expires_at = Column(DateTime(timezone=True), nullable=True)  # Expiration time for the rescheduling token
    
    times_rescheduled_by_panelist = Column(Integer, default=0)  # Counter for how many times the interview has been rescheduled
    times_rescheduled_by_candidate = Column(Integer, default=0,nullable=False)  # Counter for how many times the interview has been rescheduled
    
    cancelled_at = Column(DateTime(timezone=True), nullable=True)  # Timestamp for when the interview was cancelled, if applicable
    cancellation_reason = Column(TEXT, nullable=True)  # Reason for cancellation, if applicable
    
    ai_summary = Column(JSONB, nullable=True)  # To store AI-generated summary of the interview, which can be generated after the interview is completed.
    ai_assessment = Column(JSONB, nullable=True)  # To store AI-generated assessment/feedback of the interview, which can be generated after the interview is completed.
    
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
        order_by=lambda: Interview_TimeLine_Events.created_at.desc(),
    )
    
    application = relationship("Application", back_populates="interviews")
    round_config = relationship("Interview_Round_Configs", back_populates="interviews")
    
    assessments = relationship("InterviewAssessment", back_populates="interview")