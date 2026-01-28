from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Enum
)
from sqlalchemy.orm import relationship
from .enums import ApplicationStatus
from configs.postgress_db import Base


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True,index=True)

    job_id = Column(Integer,ForeignKey("jobs.id", ondelete="CASCADE"),nullable=False)
    candidate_id = Column(Integer,ForeignKey("candidates.id", ondelete="CASCADE"),nullable=False)
    
    status = Enum(ApplicationStatus, nullable=False, default=ApplicationStatus.APPLIED)
    current_round = Column(Integer, nullable=False, default=0)
    denormalized_rank = Column(Integer, nullable=True)
    offer_letter_url = Column(String, nullable=True)
    resume_url = Column(String, nullable=True)    


    candidate = relationship("Candidate",back_populates="applications")
    job = relationship("Job",back_populates="applications")
    
    resume = relationship(
    "Resume",
    back_populates="application",
    uselist=False,
    cascade="all, delete-orphan"
)

