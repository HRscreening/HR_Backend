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
