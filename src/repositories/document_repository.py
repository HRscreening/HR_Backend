"""
Document Repository — DB operations for documents table.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional
from uuid import UUID

from src.models.document_model import Document
from src.models.enums import DocumentProcessingStatus
from configs.log_config import get_logger

logger = get_logger("document_repository")

def _status_to_db_value(status: DocumentProcessingStatus | str) -> str:
    if isinstance(status, DocumentProcessingStatus):
        return status.value
    return str(status)


class DocumentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_document(
        self,
        entity_type: str,
        entity_id: UUID,
        document_type: str,
        file_name: str,
        file_size_bytes: int,
        mime_type: str,
        storage_provider: str,
        file_url: str,
        file_path: str,
        uploaded_by: Optional[UUID] = None,
        parsing_status: DocumentProcessingStatus = DocumentProcessingStatus.PENDING,
    ) -> Document:
        """Create a new document record."""
        doc = Document(
            entity_type=entity_type,
            entity_id=entity_id,
            document_type=document_type,
            file_name=file_name,
            file_size_bytes=file_size_bytes,
            mime_type=mime_type,
            storage_provider=storage_provider,
            file_url=file_url,
            file_path=file_path,
            uploaded_by=uploaded_by,
            parsing_status=_status_to_db_value(parsing_status),
        )
        self.db.add(doc)
        await self.db.flush()
        return doc

    async def get_document(self, document_id: UUID) -> Optional[Document]:
        """Get document by ID."""
        result = await self.db.execute(
            select(Document).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def update_parsing_status(
        self,
        document_id: UUID,
        status: DocumentProcessingStatus | str,
        error: Optional[str] = None,
        ai_parsed_data: Optional[dict] = None,
        extracted_text: Optional[str] = None,
    ):
        """Update document parsing status and results."""
        update_data = {"parsing_status": _status_to_db_value(status)}
        if error is not None:
            update_data["parsing_error"] = error
        if ai_parsed_data is not None:
            update_data["ai_parsed_data"] = ai_parsed_data
        if extracted_text is not None:
            update_data["extracted_text"] = extracted_text

        await self.db.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(**update_data)
        )
        await self.db.flush()

    async def get_latest_document_for_entity(
        self, entity_type: str, entity_id: UUID, document_type: str
    ) -> Optional[Document]:
        """Get the latest document for a given entity."""
        result = await self.db.execute(
            select(Document)
            .where(
                Document.entity_type == entity_type,
                Document.entity_id == entity_id,
                Document.document_type == document_type,
                Document.is_latest == True,
            )
            .order_by(Document.created_at.desc())
        )
        return result.scalar_one_or_none()
