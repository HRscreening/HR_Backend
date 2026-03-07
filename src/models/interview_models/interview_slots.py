from sqlalchemy import (
    Column,
    String,
    DateTime,
    func,
    Boolean,
    ForeignKey,
)
import uuid
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from configs.postgress_db import Base


class Interview_Slot(Base):
    __tablename__ = "interview_slots"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)

    round_config_id = Column(
        UUID(as_uuid=True),
        ForeignKey("interview_round_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    panelist_id = Column(
            UUID(as_uuid=True),
            ForeignKey("panelist.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        )

    slot_start = Column(DateTime(timezone=True), nullable=False)
    slot_end = Column(DateTime(timezone=True), nullable=False)

    is_booked = Column(Boolean, nullable=False, default=False)
    is_expired = Column(Boolean, nullable=False, default=False)

    booked_interview_id = Column(
        UUID(as_uuid=True),
        ForeignKey("interviews.id", ondelete="SET NULL"),
        nullable=True,
    )
    booked_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    round_config = relationship("Interview_Round_Configs", back_populates="slots")
    booked_interview = relationship("Interview", foreign_keys=[booked_interview_id])
    panelist = relationship("Panelist",back_populates="slots")
    
