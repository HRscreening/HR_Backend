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




class Interview_TimeLine_Events(Base):
    __tablename__ = "interview_timeline_events"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True,default=uuid.uuid4)

    # if same candidate  can be in multiple orgs then no need for organization_id unique constraint
    interview_id = Column(
        UUID(as_uuid=True),
        ForeignKey("interviews.id",),  
        nullable=False,
        index=True,
    )
    
    event_type = Column(String, nullable=False,index=True)  
    actor = Column(String, nullable=True)  # Email or user ID of who triggered it 
    details = Column(JSONB, nullable=True)  # Additional details about the event (e
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    interview = relationship("Interview", back_populates="events")
