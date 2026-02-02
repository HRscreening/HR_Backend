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
from sqlalchemy.dialects.postgresql import JSONB,UUID,VARCHAR,TEXT,NUMERIC
from configs.postgress_db import Base
from .enums import AIProcessingStatus





class AIProcessingLogs(Base):
    __tablename__ = "ai_processing_logs"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id",ondelete="CASCADE"),
        index=True,
        nullable=True   # Nullable as Individual users might trigger processing without an organization context
    )
    
    entity_type = Column(VARCHAR(100), nullable=False)  # e.g., 'job', 'application', 'candidate'
    entity_id = Column(UUID(as_uuid=True), nullable=False)  # ID of the record

    operation_type = Column(VARCHAR(100), nullable=False)  # e.g., 'JD_Parsing', 'Resume_Parsing', 'Candidate_Scoring'
    ai_provider = Column(VARCHAR(100), nullable=False)  # e.g., 'OpenAI', 'Anthropic'
    ai_model = Column(VARCHAR(100), nullable=False)  # e.g., 'gpt-4', 'claude-2'
    input_data = Column(JSONB, nullable=True)  # Data sent to the AI for processing
    output_data = Column(JSONB, nullable=True)  # Data received from the AI after processing
    processing_time_ms = Column(Integer, nullable=True)  # Time taken for the AI operation in milliseconds
    tokens_used = Column(Integer, nullable=True)  # Number of tokens used in the AI request/response
    cost_usd = Column(NUMERIC(10, 4), nullable=True)  # Cost incurred for this AI operation in Dollars,Enables per organization cost tracking
    status = Column(
    SAEnum(AIProcessingStatus,
        name="ai_processing_status_enum",
        native_enum=True
    ),
    nullable=False,
    default=AIProcessingStatus.PENDING
)

    error_message = Column(TEXT, nullable=True)  # Error details if the AI processing failed
    log_metadata = Column("metadata",JSONB, nullable=True)  # Any extra context that doesn't fit the fixed columns.
    triggered_by = Column(UUID(as_uuid=True),ForeignKey("users.id", ondelete="SET NULL"),nullable=True,index=True) # User ID who initiated the AI processing, if applicable.
    created_at = Column(DateTime(timezone=True),server_default=func.now(),nullable=False)
    updated_at = Column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now(),nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)


