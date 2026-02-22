from fastapi import UploadFile
import pdfplumber
from io import BytesIO
from typing import Tuple

async def extract_text_from_pdf(file: UploadFile) -> str:
    file_bytes = await file.read()
    file_obj = BytesIO(file_bytes)  # in-memory file

    text = ""
    with pdfplumber.open(file_obj) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    # Normalize whitespace
    return " ".join(text.split())




def extract_text_from_pdf_sync(file_path: str) -> Tuple[str, int]:
    """
    Extract text and page count from a PDF file (sync, worker-safe).

    Returns:
        (parsed_text, page_count)
    """
    text_parts = []
    page_count = 0

    with pdfplumber.open(file_path) as pdf:
        page_count = len(pdf.pages)

        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    # Normalize whitespace
    parsed_text = " ".join(" ".join(text_parts).split())

    return parsed_text, page_count


class PDFTextExtractor:
    def __init__(self):
        pass  # no state for now
    
    @staticmethod
    def _normalize_text(text: str) -> str:
        """
        Normalize whitespace across extracted text.
        """
        return " ".join(text.split())
    
    

    async def extract_from_upload(self, file: UploadFile) -> str:
        """
        Extract text from an uploaded PDF file (async, FastAPI-friendly).
        """
        file_bytes = await file.read()
        file_obj = BytesIO(file_bytes)

        text_parts = []

        with pdfplumber.open(file_obj) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        return self._normalize_text(" ".join(text_parts))

    def extract_from_path(self, file_path: str) -> Tuple[str, int]:
        """
        Extract text and page count from a PDF file path (sync, worker-safe).
        """
        text_parts = []

        with pdfplumber.open(file_path) as pdf:
            page_count = len(pdf.pages)

            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        parsed_text = self._normalize_text(" ".join(text_parts))
        return parsed_text, page_count


