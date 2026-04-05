from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    func,
    Boolean,
    ForeignKey,

)
from sqlalchemy import Enum as SQLEnum, UniqueConstraint
import uuid
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB,UUID,VARCHAR,TEXT

from configs.postgress_db import Base
from src.models.enums import InterviewStatus, InterviewAssessmentStatus
from src.modules.interviews.models.interview_timeline_events import Interview_TimeLine_Events



class InterviewAssessment(Base):
    __tablename__ = "interview_assessments"

    __table_args__ = (
        UniqueConstraint("interview_id", "panelist_id", name="uq_interview_panelist"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    interview_id = Column(UUID(as_uuid=True), ForeignKey("interviews.id"), nullable=False)
    panelist_id = Column(UUID(as_uuid=True), ForeignKey("panelist.id"), nullable=False)

    status = Column(SQLEnum(InterviewAssessmentStatus, name="interview_assessment_type_enum"), nullable=False,default=InterviewAssessmentStatus.REQUESTED)

    response = Column(JSONB,nullable=True)  # To store the panelist's responses to the assessment form, which can include ratings, comments, and recommendations for the candidate. The structure of this JSON can be flexible to accommodate different types of assessment forms for different interview rounds.
    final_verdict = Column(TEXT, nullable=True)  # Whether the panelist recommends moving the candidate forward or not, can be null if not submitted yet or if the panelist chose not to give a recommendation. True for recommend, False for do not recommend.
    feedback_token = Column(TEXT, unique=True,nullable=True)
    token_expires_at = Column(DateTime(timezone=True),nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    submitted_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    interview = relationship("Interview", back_populates="assessments")
    panelist = relationship("Panelist", back_populates="assessments")