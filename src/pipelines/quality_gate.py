"""
Quality Gate (Stage 1) — Structural checks only, never content-based.

Catches unusable files: parse failures, too-short text, duplicates, and
non-resume uploads. Zero risk of rejecting a good candidate based on
writing style, keywords, or domain language.

Expected filter rate: 5-10% of uploads.
Cost: $0, < 1 second for any batch size.
"""

import hashlib
from dataclasses import dataclass

from configs.log_config import get_logger

logger = get_logger("quality_gate")

MIN_WORD_COUNT = 50


@dataclass(frozen=True)
class GateResult:
    """Immutable result for a single resume's quality gate check."""

    resume_id: str
    passed: bool
    rejection_reason: str = ""


def run_quality_gate(
    resumes: list[dict],
    seen_hashes: set[str] | None = None,
) -> tuple[list[dict], list[GateResult]]:
    """
    Run structural quality checks on a batch of resumes.

    Args:
        resumes: list of dicts with at least {resume_id, parsed_text, status}.
        seen_hashes: optional pre-populated set for cross-batch dedup.

    Returns:
        (passed_resumes, rejected_results) — passed resumes keep their
        original dict; rejected get a GateResult with the reason.
    """
    if seen_hashes is None:
        seen_hashes = set()

    passed: list[dict] = []
    rejected: list[GateResult] = []

    for resume in resumes:
        resume_id = str(resume["resume_id"])
        parsed_text = resume.get("parsed_text") or ""
        status = resume.get("status", "")

        result = _check_single(resume_id, parsed_text, status, seen_hashes)
        if result.passed:
            passed.append(resume)
        else:
            rejected.append(result)
            logger.info(
                "Quality gate rejected resume=%s reason=%r",
                resume_id,
                result.rejection_reason,
            )

    logger.info(
        "Quality gate: %d passed, %d rejected out of %d",
        len(passed),
        len(rejected),
        len(resumes),
    )

    return passed, rejected


def _check_single(
    resume_id: str,
    parsed_text: str,
    status: str,
    seen_hashes: set[str],
) -> GateResult:
    """Run all structural checks on one resume. Order matters."""

    # 1. Parse check
    if not parsed_text.strip() or status in ("error", "parse_failed"):
        return GateResult(
            resume_id=resume_id,
            passed=False,
            rejection_reason="Parse failed — no extractable text",
        )

    # 2. Minimum content
    word_count = len(parsed_text.split())
    if word_count < MIN_WORD_COUNT:
        return GateResult(
            resume_id=resume_id,
            passed=False,
            rejection_reason=(
                f"Too short ({word_count} words) — likely corrupt or incomplete"
            ),
        )

    # 3. Duplicate detection (MD5 of normalised text)
    text_hash = hashlib.sha256(
        parsed_text.strip().lower().encode()
    ).hexdigest()
    if text_hash in seen_hashes:
        return GateResult(
            resume_id=resume_id,
            passed=False,
            rejection_reason="Duplicate of another uploaded resume",
        )
    seen_hashes.add(text_hash)

    # 4. Non-resume detection (simple heuristics only)
    lower_head = parsed_text[:500].lower()
    is_jd = (
        "job description" in lower_head
        and "responsibilities" in lower_head
        and "qualifications" in lower_head
    )
    is_template = "[your name]" in lower_head or "[insert" in lower_head

    if is_jd or is_template:
        return GateResult(
            resume_id=resume_id,
            passed=False,
            rejection_reason="File appears to be a JD or blank template, not a resume",
        )

    return GateResult(resume_id=resume_id, passed=True)
