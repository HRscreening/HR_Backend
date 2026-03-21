from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    func,
    Boolean,
    ForeignKey,
    text
)
from sqlalchemy import Enum as SAEnum
import uuid
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB,UUID,TEXT

from configs.postgress_db import Base
from .enums import RescoreOnRubricChange,AutoMoveSettingsEnum

class JobSetting(Base):
    __tablename__ = "job_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,   
        index=True
    )



    voice_ai_enabled = Column(Boolean, default=False)
    manual_rounds_count = Column(Integer, default=0)
    is_confidential = Column(Boolean, default=False)
    auto_score_every_resume = Column(Boolean, default=False)
    auto_score_every_resume_on_manual_upload = Column(Boolean, default=False)
    auto_offer_enabled = Column(Boolean, default=False)
    ai_assessment_enabled = Column(Boolean, default=False)

    rescore_on_rubric_change = Column(
        SAEnum(RescoreOnRubricChange, name="rescore_enum",values_callable=lambda obj: [e.value for e in obj],),
        nullable=False,
        default=RescoreOnRubricChange.ONLY_NEW,
    )

    auto_move_to_next_round = Column(
        SAEnum(AutoMoveSettingsEnum, name="auto_move_enum",values_callable=lambda obj: [e.value for e in obj],),
        nullable=False,
        default=AutoMoveSettingsEnum.PANEL,
    )

    panel_reminders = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    candidate_reminders = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    feedback_reminders = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    escalation = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    rescheduling = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    voice_nudges = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))


    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    job = relationship("Job",back_populates="setting")