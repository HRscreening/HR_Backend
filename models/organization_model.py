from sqlalchemy import Column, Integer, String, DateTime, func, ForeignKey
from sqlalchemy.orm import relationship
from configs.postgress_db import Base

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False,unique=True)
    email = Column(String, nullable=False,unique=True)
    address = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    created_by = Column(
        Integer,
        unique=True,        
        nullable=False
    )

    users = relationship(
    "User",
    back_populates="organization",
    cascade="all, delete-orphan"
)

    
    jobs = relationship(
        "Job",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    
    candidates = relationship(
        "Candidate",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
