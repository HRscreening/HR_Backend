"""
Standalone test script for resume parsing pipeline.

Tests the same extraction mechanism used in the app (pdfplumber → Gemini Vision → Gemini Native PDF)
against each PDF in a zip file, without needing a running server, DB, or Redis.

Usage:
    python test_resume_parsing.py /path/to/resumes.zip
"""

import os
import sys
import time
import zipfile
import tempfile
import logging
import traceback

# Load .env BEFORE any app imports so GOOGLE_API_KEY etc. are available
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_resume_parsing")

# Silence noisy sub-loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("google").setLevel(logging.WARNING)


# ── Main test ──────────────────────────────────────────────────────────────────

def test_zip(zip_path: str):
    from src.utils.extract_pdf import extract_text_from_file_sync

    SUPPORTED_EXTS = {".pdf", ".docx", ".doc"}

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = [
            n for n in zf.namelist()
            if not n.startswith("__MACOSX")
            and not os.path.basename(n).startswith(".")
            and os.path.splitext(n)[1].lower() in SUPPORTED_EXTS
        ]

    logger.info(f"Found {len(names)} resume(s) in {os.path.basename(zip_path)}")

    results = []

    with tempfile.TemporaryDirectory() as tmpdir:
        # Extract all files first
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in names:
                zf.extract(name, tmpdir)

        for i, name in enumerate(names, 1):
            file_path = os.path.join(tmpdir, name)
            file_name = os.path.basename(name)

            logger.info(f"\n{'='*60}")
            logger.info(f"[{i}/{len(names)}] Parsing: {file_name}")
            logger.info(f"{'='*60}")

            start = time.time()
            try:
                parsed_text, page_count, method = extract_text_from_file_sync(file_path)
                elapsed = time.time() - start

                char_count = len(parsed_text.strip())
                preview = parsed_text.strip()[:200].replace("\n", " ")

                status = "OK" if char_count >= 50 else "WARN (low text)"

                results.append({
                    "file": file_name,
                    "status": status,
                    "method": method,
                    "chars": char_count,
                    "pages": page_count,
                    "elapsed": elapsed,
                    "preview": preview,
                    "error": None,
                })

                logger.info(f"  Status  : {status}")
                logger.info(f"  Method  : {method}")
                logger.info(f"  Pages   : {page_count}")
                logger.info(f"  Chars   : {char_count}")
                logger.info(f"  Time    : {elapsed:.1f}s")
                logger.info(f"  Preview : {preview[:120]}...")

            except Exception as e:
                elapsed = time.time() - start
                logger.error(f"  FAILED after {elapsed:.1f}s: {e}")
                traceback.print_exc()
                results.append({
                    "file": file_name,
                    "status": "ERROR",
                    "method": "—",
                    "chars": 0,
                    "pages": 0,
                    "elapsed": elapsed,
                    "preview": "",
                    "error": str(e),
                })

    # ── Summary table ────────────────────────────────────────────────────────
    print(f"\n\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"{'File':<35} {'Status':<18} {'Method':<15} {'Chars':>6} {'Time':>6}")
    print(f"{'-'*35} {'-'*18} {'-'*15} {'-'*6} {'-'*6}")
    for r in results:
        print(
            f"{r['file'][:34]:<35} {r['status']:<18} {r['method']:<15} "
            f"{r['chars']:>6} {r['elapsed']:>5.1f}s"
        )

    ok     = sum(1 for r in results if r["status"] == "OK")
    warn   = sum(1 for r in results if "WARN" in r["status"])
    errors = sum(1 for r in results if r["status"] == "ERROR")
    print(f"\n  OK: {ok}  |  WARN: {warn}  |  ERROR: {errors}  |  Total: {len(results)}")
    print(f"{'='*70}\n")

    return errors == 0


if __name__ == "__main__":
    zip_path = sys.argv[1] if len(sys.argv) > 1 else "/Users/prahsantsingh/Desktop/resume1.zip"

    if not os.path.exists(zip_path):
        print(f"Error: file not found: {zip_path}")
        sys.exit(1)

    success = test_zip(zip_path)
    sys.exit(0 if success else 1)
