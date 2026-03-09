"""
Gemini Vision OCR utility for image-based PDF pages.

Uses Gemini 2.5 Flash as a multimodal vision model to extract text
from PDF pages where pdfplumber returns little or no text (scanned/image-based).

Fallback chain:
  1. pdfplumber (text-based PDFs)
  2. pdf2image + Gemini Vision (if poppler is installed)
  3. Gemini Native PDF (sends PDF bytes directly to Gemini — no poppler needed)
"""

import base64
import logging
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import List, Tuple

logger = logging.getLogger(__name__)

try:
    from pdf2image import convert_from_path
    from PIL import Image
    import io
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("pdf2image or Pillow not installed — Vision OCR disabled, will use Gemini Native PDF fallback")


MIN_CHARS_PER_PAGE = 50  # pages with fewer chars are considered image-based

# Max PDF size to send directly to Gemini (20 MB)
MAX_GEMINI_PDF_SIZE = 20 * 1024 * 1024

# Timeout for a single Gemini LLM call (seconds).
# If the Gemini API hangs, this prevents blocking the entire worker.
GEMINI_CALL_TIMEOUT = int(os.environ.get("GEMINI_CALL_TIMEOUT", "30"))


def _invoke_llm_with_timeout(llm, messages, timeout: int = GEMINI_CALL_TIMEOUT):
    """
    Invoke an LLM with a hard thread-based timeout.
    SIGALRM doesn't reliably interrupt blocking HTTP I/O, so we use
    concurrent.futures to enforce a real deadline.

    CRITICAL: Do NOT use `with ThreadPoolExecutor` — its __exit__ calls
    shutdown(wait=True) which blocks until the hung thread finishes,
    completely defeating the timeout.
    """
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(llm.invoke, messages)
    try:
        result = future.result(timeout=timeout)
        pool.shutdown(wait=False)
        return result
    except FuturesTimeout:
        # Don't wait for the hung thread — let it die in the background.
        pool.shutdown(wait=False)
        raise
    except Exception:
        pool.shutdown(wait=False)
        raise


def needs_ocr(page_texts: List[str], page_count: int) -> List[int]:
    """
    Return indices of pages where pdfplumber extracted fewer than
    MIN_CHARS_PER_PAGE characters (likely image-based pages).
    """
    ocr_pages = []
    for i in range(page_count):
        text = page_texts[i] if i < len(page_texts) else ""
        if len(text.strip()) < MIN_CHARS_PER_PAGE:
            ocr_pages.append(i)
    return ocr_pages


def _image_to_base64(image: "Image.Image", max_width: int = 1600) -> str:
    """Resize image if needed and convert to base64 JPEG."""
    if image.width > max_width:
        ratio = max_width / image.width
        image = image.resize(
            (max_width, int(image.height * ratio)),
            Image.LANCZOS,
        )
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def extract_with_gemini_native_pdf(file_path: str) -> Tuple[str, float]:
    """
    Extract text from a PDF by sending the entire file to Gemini's multimodal API.
    This does NOT require poppler — it uses Gemini's native PDF understanding.

    Returns:
        (extracted_text, confidence)
    """
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    if file_size > MAX_GEMINI_PDF_SIZE:
        logger.warning(
            f"[GEMINI PDF] {file_name} too large ({file_size} bytes) for Gemini native PDF — skipping"
        )
        return "", 0.0

    from src.pipelines.models import llm  # Gemini 2.5 Flash (multimodal)
    from langchain_core.messages import HumanMessage

    try:
        with open(file_path, "rb") as f:
            pdf_b64 = base64.b64encode(f.read()).decode("utf-8")

        message = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": (
                        "Extract ALL text from this resume PDF exactly as written. "
                        "Preserve structure, formatting, headings, bullet points, and sections. "
                        "Include all pages. Return ONLY the extracted text, no commentary or analysis."
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:application/pdf;base64,{pdf_b64}"},
                },
            ]
        )

        logger.info(f"[GEMINI PDF] Sending {file_name} to Gemini (timeout={GEMINI_CALL_TIMEOUT}s)...")
        response = _invoke_llm_with_timeout(llm, [message])
        extracted_text = response.content.strip()

        confidence = 0.80 if extracted_text else 0.0
        logger.info(
            f"[GEMINI PDF] {file_name} native PDF extraction: {len(extracted_text)} chars "
            f"(confidence={confidence:.2f})"
        )
        return extracted_text, confidence

    except FuturesTimeout:
        logger.error(
            f"[GEMINI PDF] {file_name} timed out after {GEMINI_CALL_TIMEOUT}s — skipping"
        )
        return "", 0.0
    except Exception as e:
        logger.error(f"[GEMINI PDF] Native PDF extraction failed for {file_name}: {e}")
        return "", 0.0


def extract_with_gemini_vision(
    file_path: str,
    ocr_page_indices: List[int] | None = None,
) -> Tuple[str, float, str]:
    """
    Extract text from image-based PDF pages using Gemini 2.5 Flash vision.

    Args:
        file_path: Path to the PDF file on disk.
        ocr_page_indices: Which 0-based page indices to OCR.
                          If None, OCR all pages.

    Returns:
        (extracted_text, confidence, source)
        source is one of: "vision" | "native_pdf"
    """
    if not OCR_AVAILABLE:
        logger.warning("Vision OCR not available — trying Gemini native PDF fallback")
        text, confidence = extract_with_gemini_native_pdf(file_path)
        return text, confidence, "native_pdf"

    from src.pipelines.models import llm  # Gemini 2.5 Flash (multimodal)
    from langchain_core.messages import HumanMessage

    try:
        images = convert_from_path(file_path, dpi=200)
    except Exception as e:
        logger.warning(
            f"convert_from_path failed (poppler missing?): {e} — "
            f"falling back to Gemini native PDF extraction"
        )
        text, confidence = extract_with_gemini_native_pdf(file_path)
        return text, confidence, "native_pdf"

    if ocr_page_indices is None:
        ocr_page_indices = list(range(len(images)))

    extracted_pages: List[str] = []

    for idx in ocr_page_indices:
        if idx >= len(images):
            continue

        b64 = _image_to_base64(images[idx])

        message = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": (
                        "Extract all text from this resume page exactly as written. "
                        "Preserve structure, formatting, headings, and bullet points. "
                        "Return ONLY the extracted text, no commentary."
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                },
            ]
        )

        try:
            response = _invoke_llm_with_timeout(llm, [message])
            page_text = response.content.strip()
            extracted_pages.append(page_text)
        except FuturesTimeout:
            logger.error(
                f"Gemini Vision OCR timed out for page {idx} after {GEMINI_CALL_TIMEOUT}s"
            )
            extracted_pages.append("")
        except Exception as e:
            logger.error(f"Gemini Vision OCR failed for page {idx}: {e}")
            extracted_pages.append("")

    full_text = "\n\n".join(extracted_pages)
    confidence = 0.85 if full_text.strip() else 0.0
    return full_text, confidence, "vision"


def determine_extraction_method(
    pdfplumber_text: str,
    ocr_text: str,
    page_count: int,
    ocr_pages_count: int,
) -> str:
    """
    Determine extraction method label based on what was used.

    Returns: "text" | "ocr" | "mixed" | "extraction_failed"
    """
    has_plumber = len(pdfplumber_text.strip()) >= MIN_CHARS_PER_PAGE
    has_ocr = len(ocr_text.strip()) >= MIN_CHARS_PER_PAGE

    if not has_plumber and not has_ocr:
        return "extraction_failed"

    if ocr_pages_count == 0:
        return "text"

    if ocr_pages_count >= page_count:
        return "ocr"

    return "mixed"
