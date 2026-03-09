from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    func,
    Boolean,
    ForeignKey,
)
import uuid
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator, VARCHAR as VARCHARType
from sqlalchemy.dialects.postgresql import JSONB, UUID, VARCHAR, TEXT

from configs.postgress_db import Base
from .enums import BulkUploadStatus


class BulkUploadStatusType(TypeDecorator):
    """Stores BulkUploadStatus enum as VARCHAR (no PostgreSQL enum required)."""
    impl = VARCHARType(50)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, BulkUploadStatus):
            return value.value
        if isinstance(value, str):
            v = value.strip()
            # Accept either enum values ("pending") or enum names ("PENDING") and normalize.
            if v in BulkUploadStatus._value2member_map_:
                return v
            if v.upper() in BulkUploadStatus.__members__:
                return BulkUploadStatus[v.upper()].value
            return v
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, BulkUploadStatus):
            return value
        if isinstance(value, str):
            v = value.strip()
            if v in BulkUploadStatus._value2member_map_:
                return BulkUploadStatus(v)
            if v.upper() in BulkUploadStatus.__members__:
                return BulkUploadStatus[v.upper()]
            # Fall back: keep behavior loud so bad DB values are caught early.
            return BulkUploadStatus(v)
        return BulkUploadStatus(str(value))





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
        nullable=False
    )
    
    # DB column is "uploaded_by"; Python attr stays "uploaded_by_id" for service code.
    uploaded_by_id = Column(
        "uploaded_by",
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    
    batch_name = Column(VARCHAR(100), nullable=False) # Name/label for this bulk upload batch


    source_file_url = Column(
        TEXT,
        nullable=False
    )  # folder path where uploaded files live
    
    # DB uses VARCHAR for status (no PostgreSQL enum). Store enum .value: "pending", "processing", "completed", "failed".
    status = Column(
        BulkUploadStatusType,
        nullable=False,
        default=BulkUploadStatus.PENDING,
    )
    
    total_files = Column(Integer, nullable=False, default=0)
    processed_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    processing_results = Column(JSONB, nullable=True)  # Per-file results array — what happened to each individual resume in the batch.
    error_log = Column(JSONB, nullable=True)  # Detailed errors for any files that failed. For debugging.

    # Scoring phase tracking
    scoring_total = Column(Integer, nullable=False, default=0)
    scoring_completed = Column(Integer, nullable=False, default=0)
    scoring_failed = Column(Integer, nullable=False, default=0)
    scoring_status = Column(BulkUploadStatusType, nullable=False, default=BulkUploadStatus.PENDING)
    batch_metadata = Column("metadata",JSONB, nullable=True)  # Any additional info about the batch upload
    
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


