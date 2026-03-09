from fastapi import UploadFile
import pdfplumber
from io import BytesIO
from typing import Tuple
import logging
import os

from src.utils.ocr_extract import (
    OCR_AVAILABLE,
    needs_ocr,
    extract_with_gemini_vision,
    extract_with_gemini_native_pdf,
    determine_extraction_method,
    MIN_CHARS_PER_PAGE,
)

logger = logging.getLogger(__name__)


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


def _extract_docx_text(file_path: str) -> Tuple[str, int, str]:
    """Extract text from a DOCX file using python-docx."""
    file_name = os.path.basename(file_path)
    try:
        import docx
    except ImportError:
        logger.warning(
            f"[DOCX EXTRACT] python-docx not installed — "
            f"falling back to Gemini native PDF for {file_name}"
        )
        text, confidence = extract_with_gemini_native_pdf(file_path)
        method = "gemini_native" if text.strip() else "extraction_failed"
        return text, 1, method

    try:
        doc = docx.Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n".join(paragraphs)
        normalized = " ".join(text.split())
        page_count = max(1, len(normalized) // 3000)  # estimate

        if len(normalized.strip()) < MIN_CHARS_PER_PAGE:
            logger.warning(f"[DOCX EXTRACT] {file_name} yielded only {len(normalized)} chars")
            return normalized, page_count, "extraction_failed"

        logger.info(f"[DOCX EXTRACT] {file_name} extracted {len(normalized)} chars")
        return normalized, page_count, "text"
    except Exception as e:
        logger.error(f"[DOCX EXTRACT] Failed for {file_name}: {e!r}")
        # Fall back to Gemini
        text, confidence = extract_with_gemini_native_pdf(file_path)
        method = "gemini_native" if text.strip() else "extraction_failed"
        return text, 1, method


def extract_text_from_file_sync(file_path: str) -> Tuple[str, int, str]:
    """
    Extract text from a resume file (PDF, DOCX, DOC). Detects file type
    and routes to the appropriate extractor.

    Returns:
        (parsed_text, page_count, extraction_method)
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext in (".docx", ".doc"):
        return _extract_docx_text(file_path)

    # Default: treat as PDF
    return extract_text_from_pdf_sync(file_path)


def extract_text_from_pdf_sync(file_path: str) -> Tuple[str, int, str]:
    """
    Extract text and page count from a PDF file (sync, worker-safe).

    Fallback chain:
      1. pdfplumber (text-based PDFs)
      2. Gemini Vision OCR via pdf2image+poppler (image-based pages)
      3. Gemini Native PDF (sends entire PDF to Gemini — no poppler needed)

    Returns:
        (parsed_text, page_count, extraction_method)
        extraction_method is one of: "text", "ocr", "mixed", "gemini_native", "extraction_failed"
    """
    file_name = os.path.basename(file_path)
    logger.info(f"[PDF EXTRACT] Starting extraction for {file_name}")

    page_texts = []
    page_count = 0
    pdfplumber_failed = False

    # Step 1: pdfplumber extraction
    try:
        with pdfplumber.open(file_path) as pdf:
            page_count = len(pdf.pages)
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text() or ""
                page_texts.append(page_text)
                char_count = len(page_text.strip())
                logger.info(f"[PDF EXTRACT] {file_name} page {i+1}/{page_count}: {char_count} chars via pdfplumber")
    except Exception as e:
        logger.error(f"[PDF EXTRACT] pdfplumber failed for {file_name}: {e!r} — will try Gemini fallback")
        pdfplumber_failed = True

    # If pdfplumber completely failed, go straight to Gemini native PDF
    if pdfplumber_failed:
        logger.info(f"[PDF EXTRACT] {file_name} using Gemini native PDF fallback (pdfplumber failed)")
        gemini_text, confidence = extract_with_gemini_native_pdf(file_path)
        if gemini_text.strip():
            logger.info(
                f"[PDF EXTRACT] {file_name} Gemini native PDF extracted {len(gemini_text)} chars"
            )
            return gemini_text, 1, "gemini_native"
        else:
            logger.error(f"[PDF EXTRACT] {file_name} all extraction methods failed")
            return "", 0, "extraction_failed"

    pdfplumber_text = " ".join(" ".join(page_texts).split())
    logger.info(
        f"[PDF EXTRACT] {file_name} pdfplumber total: {len(pdfplumber_text)} chars across {page_count} pages"
    )

    # Step 2: OCR for image-based pages (uses poppler if available, else Gemini native PDF)
    ocr_text = ""
    ocr_pages_count = 0

    ocr_page_indices = needs_ocr(page_texts, page_count)
    ocr_pages_count = len(ocr_page_indices)

    if ocr_page_indices:
        logger.info(
            f"[PDF EXTRACT] {file_name} pages needing OCR: {ocr_page_indices} "
            f"(OCR_AVAILABLE={OCR_AVAILABLE})"
        )
        # extract_with_gemini_vision will fall back to Gemini native PDF
        # if poppler is not available
        ocr_text, confidence, ocr_source = extract_with_gemini_vision(file_path, ocr_page_indices)
        logger.info(
            f"[PDF EXTRACT] {file_name} OCR returned {len(ocr_text)} chars "
            f"(confidence={confidence:.2f})"
        )

        # If poppler is missing, extract_with_gemini_vision falls back to Gemini native PDF.
        # That output is NOT page-split, so never try to split it and "merge" per-page
        # (doing so truncates the document to the first chunk).
        if ocr_text.strip() and ocr_source == "native_pdf":
            parsed_text = " ".join(ocr_text.split())
            logger.info(
                f"[PDF EXTRACT] {file_name} using Gemini native PDF OCR fallback text directly "
                f"(len={len(parsed_text)})"
            )
            return parsed_text, page_count or 1, "gemini_native"

        # Merge: replace low-text pages with OCR text (vision per-page output)
        if ocr_text.strip():
            ocr_texts_iter = iter(ocr_text.split("\n\n"))
            for idx in ocr_page_indices:
                if idx < len(page_texts):
                    ocr_page = next(ocr_texts_iter, "")
                    if len(page_texts[idx].strip()) < MIN_CHARS_PER_PAGE and ocr_page:
                        page_texts[idx] = ocr_page
    else:
        logger.info(f"[PDF EXTRACT] {file_name} all pages have sufficient text, no OCR needed")

    # Step 3: Rebuild full text
    parsed_text = " ".join(" ".join(page_texts).split())

    extraction_method = determine_extraction_method(
        pdfplumber_text, ocr_text, page_count, ocr_pages_count
    )

    # Step 4: If still insufficient text, try Gemini native PDF as last resort
    if len(parsed_text.strip()) < MIN_CHARS_PER_PAGE:
        logger.warning(
            f"[PDF EXTRACT] {file_name} insufficient text ({len(parsed_text)} chars) after "
            f"pdfplumber+OCR — trying Gemini native PDF as last resort"
        )
        gemini_text, confidence = extract_with_gemini_native_pdf(file_path)
        if len(gemini_text.strip()) > len(parsed_text.strip()):
            parsed_text = gemini_text
            extraction_method = "gemini_native"
            logger.info(
                f"[PDF EXTRACT] {file_name} Gemini native PDF rescued extraction: "
                f"{len(parsed_text)} chars"
            )

    # Quality check: if multi-page PDF yields almost nothing
    if page_count > 1 and len(parsed_text.strip()) < 100:
        logger.warning(
            f"[PDF EXTRACT] {file_name} multi-page PDF yielded only {len(parsed_text)} chars — marking extraction_failed"
        )
        extraction_method = "extraction_failed"

    logger.info(
        f"[PDF EXTRACT] {file_name} DONE: method={extraction_method} "
        f"final_text_len={len(parsed_text)} page_count={page_count}"
    )

    return parsed_text, page_count, extraction_method


class PDFTextExtractor:
    def __init__(self):
        pass  # no state for now

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join(text.split())

    async def extract_from_upload(self, file: UploadFile) -> str:
        file_bytes = await file.read()
        file_obj = BytesIO(file_bytes)

        text_parts = []

        with pdfplumber.open(file_obj) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        return self._normalize_text(" ".join(text_parts))

    def extract_from_path(self, file_path: str) -> Tuple[str, int, str]:
        return extract_text_from_file_sync(file_path)
