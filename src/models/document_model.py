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
from sqlalchemy.dialects.postgresql import JSONB,UUID,VARCHAR,BIGINT,TEXT

from configs.postgress_db import Base
from .enums import DocumentProcessingStatus





class Document(Base):
    __tablename__ = "documents"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    entity_type = Column(VARCHAR(100), nullable=False)  # e.g., Which table this document is associated with
    entity_id = Column(UUID(as_uuid=True), nullable=False)  # e.g., ID of the record in that entity table
    document_type = Column(VARCHAR(100), nullable=False)  # e.g., 'resume', 'cover_letter', 'job_description'
    file_name = Column(VARCHAR(255), nullable=False) # Original file name as uploaded
    file_size_bytes = Column(BIGINT, nullable=False) 
    mime_type = Column(VARCHAR(100), nullable=False)  # e.g., 'application/pdf', 'application/msword'
    storage_provider = Column(VARCHAR(100), nullable=False)  # e.g., 's3', 'gcs' 
    file_url = Column(TEXT, nullable=False)  # URL to access the document directly
    file_path = Column(TEXT, nullable=False)  # The internal storage path (e.g., bucket path). Distinct from the public URL.
    extracted_text = Column(TEXT, nullable=True)  # Text extracted from the document after parsing
    # NOTE: DB schema uses VARCHAR for parsing_status (no enum type).
    # Store enum values as strings, e.g. "pending", "parsed", "error".
    parsing_status = Column(
        VARCHAR(100),
        nullable=True,
        default=DocumentProcessingStatus.PENDING.value,
    )
    parsing_error = Column(TEXT, nullable=True)  # Any error encountered during parsing/extraction
    ai_parsed_data = Column(JSONB, nullable=True)  # Structured data extracted by AI (e.g., parsed resume fields)
    version = Column(Integer, nullable=False, default=1)  # Versioning for documents
    is_latest = Column(Boolean, default=True)  # True if this is the most recent version. Lets you query the current version quickly
    is_public = Column(Boolean, default=False)  # Whether the document is publicly accessible via its URL
    access_token = Column(VARCHAR(255), nullable=True)  # Token required to access the document if it's not public
    
    uploaded_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
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

    deleted_at = Column(DateTime(timezone=True), nullable=True)

    


