from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    UniqueConstraint
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .enums import ApplicationStatus
from configs.postgress_db import Base
import uuid


class Application(Base):
    __tablename__ = "applications"

    
    __table_args__ = (
        UniqueConstraint("job_id", "candidate_id", name="uq_job_candidate"),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True,index=True,default=uuid.uuid4)

    job_id = Column(UUID(as_uuid=True),ForeignKey("jobs.id", ondelete="CASCADE"),nullable=False)
    candidate_id = Column(UUID(as_uuid=True),ForeignKey("candidates.id", ondelete="CASCADE"),nullable=False)
    
    status = Column(SAEnum(ApplicationStatus,name="application_status_enum",native_enum=True), nullable=False, default=ApplicationStatus.APPLIED)
    current_round = Column(Integer, nullable=False, default=0)
    denormalized_rank = Column(Integer, nullable=True)
    offer_letter_url = Column(String, nullable=True)   


    candidate = relationship("Candidate",back_populates="applications")
    job = relationship("Job",back_populates="applications")
    
    resume = relationship(
    "Resume",
    back_populates="application",
    uselist=False,
    cascade="all, delete-orphan"    
    )
    
    scores = relationship(
        "Score",
        back_populates="application",
        cascade="all, delete-orphan"
    )

