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
from .enums import BulkUploadStatus





class BulkUploadBatches(Base):
    __tablename__ = "bulk_upload_batches"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id",ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    uploaded_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )  
    
    batch_name = Column(VARCHAR(255), nullable=False) # Name/label for this bulk upload batch


    source_file_url = Column(
        TEXT,
        nullable=False
    )  # folder path where uploaded files live
    
    status = Column(SAEnum(
        BulkUploadStatus,
        name="bulk_upload_status_enum",
        native_enum=True
    ),nullable=False,default=BulkUploadStatus.PENDING,index=True)
    
    total_files = Column(Integer, nullable=False, default=0)
    processed_count = Column(Integer, nullable=True, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    processing_results = Column(JSONB, nullable=True)  # Per-file results array — what happened to each individual resume in the batch.
    error_log = Column(JSONB, nullable=True)  # Detailed errors for any files that failed. For debugging.
    batch_metadata = Column("metadata",JSONB, nullable=True)  # Any additional info about the batch upload
    
    scoring_total = Column(Integer, nullable=False,default=0)  # Total score for the batch if applicable (e.g., average candidate score from resume parsing)
    scoring_completed = Column(Integer, nullable=False,default=0 )  # Whether any scoring operations for this batch have completed yet.
    scoring_failed = Column(Integer, nullable=False,default=0 )  # Whether any scoring operations for this batch have failed.
    scoring_status = Column(VARCHAR(100), nullable=True)  # e.g., "Not Started", "In Progress", "Completed", "Failed"
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    completed_at = Column(DateTime(timezone=True), nullable=True)


