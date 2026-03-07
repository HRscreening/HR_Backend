from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    func,
    Boolean,
    ForeignKey,
)
from sqlalchemy import Enum as SAEnum,UniqueConstraint
import uuid
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB,UUID,VARCHAR,TEXT

from configs.postgress_db import Base
from src.models.enums import InterviewType, PanelMode




class Interview_Round_Configs(Base):
    __tablename__ = "interview_round_configs"
    
   
    __table_args__ = (UniqueConstraint("job_id", "round_number", name="uq_job_round"),)
    id = Column(UUID(as_uuid=True), primary_key=True, index=True,default=uuid.uuid4)

    # if same candidate  can be in multiple orgs then no need for organization_id unique constraint
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id",),  
        nullable=False,
        index=True,
    )
    
    round_number = Column(Integer, nullable=False)  # e.g., 1 for first round, 2 for second round, etc.
    title = Column(String, nullable=False)  # e.g., "Phone Screen", "Technical Interview", etc.

    interview_type =  Column(SAEnum(
        InterviewType,
        name="interview_type_enum",
        native_enum=True
    ),nullable=False)
    
    instructions = Column(TEXT, nullable=True)  # Instructions for the interview round, if any
    duration_minutes = Column(Integer, nullable=False)  

    meet_link = Column(String, nullable=True)  # Optional: link to the virtual meeting room for this round
    
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    
    slots_available = Column(Boolean, nullable=False, default=False)  # Indicates if there are still slots available for this round
    candidate_slot_booking_link = Column(String, nullable=True)  # Optional: link to the slot booking system (e.g., Calendly) for this round
    
    timezone = Column(String, nullable=True, default="UTC")  # IANA timezone (e.g. "Asia/Kolkata") for display purposes; all storage is UTC

    panel_mode = Column(
        SAEnum(PanelMode, name="panel_mode_enum", native_enum=True),
        nullable=False,
        default=PanelMode.SEQUENTIAL,
    )  # PANEL = intersection (all together), SEQUENTIAL = union (1-on-1 each)
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now(),nullable=False)
    
    job = relationship("Job", back_populates="interview_round_configs")
    interviews = relationship("Interview", back_populates="round_config")
    panelists = relationship("Panelist",back_populates="round_config")
    slots = relationship("Interview_Slot", back_populates="round_config", cascade="all, delete-orphan")
    