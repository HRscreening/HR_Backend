from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    UniqueConstraint,
    DateTime,
    func,
    Boolean,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB,ARRAY,TEXT
from sqlalchemy.orm import relationship
from .enums import ApplicationStatus
from configs.postgress_db import Base
import uuid


class Application(Base):
    __tablename__ = "applications"

    
    # __table_args__ = (
    #     UniqueConstraint("job_id", "candidate_id", name="uq_job_candidate"),
    # )
    # TODO: Above unique constraint cannot be added because initially application can be created without candidate_id when candidate is not known yet.
    
    id = Column(UUID(as_uuid=True), primary_key=True,index=True,default=uuid.uuid4)

    job_id = Column(UUID(as_uuid=True),ForeignKey("jobs.id", ondelete="CASCADE"),nullable=False)
    # TODO: think onDelete cascade is required or not
    candidate_id = Column(UUID(as_uuid=True),ForeignKey("candidates.id", ondelete="CASCADE"),nullable=True) #Nullable b'coz first application can be created without candidate being there
    
    status = Column(SAEnum(ApplicationStatus,name="application_status_enum",native_enum=True), nullable=False, default=ApplicationStatus.APPLIED)
    current_round = Column(Integer, default=0)
    denormalized_rank = Column(Integer, nullable=True)
    offer_letter_url = Column(String, nullable=True) 
    
    current_resume_id = Column(UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True)  # The resume used for the current evaluation round
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=False, server_default=func.now())
    ai_analysis = Column(JSONB, nullable=True)  # The AI's holistic assessment of this application — a summary/evaluation beyond just the score
    is_starred = Column(Boolean, default=False)  # Whether the application is marked as important by a recruiter
    is_flagged = Column(Boolean, default=False)  # Whether the application is flagged for review (e.g., potential issues)
    flag_reason = Column(String, nullable=True)  # Reason for flagging the application, if applicable
    tags = Column(ARRAY(String), nullable=True)  # Custom tags/labels assigned to the application for categorization
    last_activity_at = Column(DateTime(timezone=True), nullable=True)  # Timestamp of the last activity on this application
    
    candidate = relationship("Candidate",back_populates="applications")
    job = relationship("Job",back_populates="applications")
    
    resume = relationship(
    "Resume",
    foreign_keys=[current_resume_id],
    uselist=False,
    )
    
    scores = relationship(
        "Score",
        back_populates="application",
        cascade="all, delete-orphan"
    )


    # owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # The user who created the application, used for personal mode to isolate applications per user