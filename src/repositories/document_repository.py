from src.models import Document
from sqlalchemy.ext.asyncio import AsyncSession
from  configs.log_config import get_logger

class DocumentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = get_logger("DOCUMENT_REPOSITORY")
        
        
    async def add_document(self, document: Document) -> Document:
        self.db.add(document)
        await self.db.flush()  # to get the ID populated
        return document
    
