"""
Cross-Encoder Relevance Scoring (Stage 2) — Resume × JD joint scoring.

Uses BAAI/bge-reranker-v2-m3 (8192-token context, ~1.1 GB) to score
each resume against the JD in a single forward pass. Top-N selection
(no arbitrary threshold) ensures no calibration is needed.

Cost: $0 (local inference). Speed: ~50-80 ms per pair on CPU.
For 92 resumes: ~6.5 seconds total.

Skip this stage entirely for < 50 resumes (not worth the complexity).
"""

import time
from dataclasses import dataclass

from configs.log_config import get_logger

logger = get_logger("relevance_scorer")

# Lazy-loaded singleton — model loads once at first use (~1.1 GB)
_cross_encoder = None

# Absolute floor: catches nonsensical matches only (cooking resume → React job)
_MIN_SCORE = 0.01

# Default top-N sent to LLM scoring
DEFAULT_TOP_N = 25

# Cross-encoder always runs (no skip threshold)

# Truncation limits (cross-encoder context = 8192 tokens ≈ ~6000 chars resume)
_JD_MAX_CHARS = 2000
_RESUME_MAX_CHARS = 6000


@dataclass(frozen=True)
class RelevanceResult:
    """Immutable result for a single resume's relevance scoring."""

    resume_id: str
    relevance_score: float
    rank: int  # 1-based rank (1 = most relevant)
    selected: bool
    rejection_reason: str = ""


def _get_cross_encoder():
    """Lazy-load cross-encoder model (singleton, thread-safe enough for workers)."""
    global _cross_encoder
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder

        logger.info(
            "[CROSS-ENCODER] Loading model BAAI/bge-reranker-v2-m3 (~1.1 GB) — first use only..."
        )
        _cross_encoder = CrossEncoder(
            "BAAI/bge-reranker-v2-m3", max_length=8192
        )
        logger.info("[CROSS-ENCODER] Model loaded and cached in memory.")
    else:
        logger.info("[CROSS-ENCODER] Using cached model (already loaded).")
    return _cross_encoder


def score_relevance_batch(
    resumes: list[dict],
    jd_text: str,
    top_n: int = DEFAULT_TOP_N,
    min_score: float = _MIN_SCORE,
) -> tuple[list[dict], list[RelevanceResult]]:
    """
    Score all resumes against JD using cross-encoder, select top-N.

    Args:
        resumes: list of dicts with at least {resume_id, parsed_text}.
        jd_text: the job description text.
        top_n: how many to send to full LLM scoring.
        min_score: absolute floor for nonsensical matches.

    Returns:
        (selected_resumes, rejected_results) — selected keep their
        original dict (enriched with relevance_score + rank);
        rejected get a RelevanceResult with rank and reason.
    """
    total = len(resumes)

    logger.info(
        "[CROSS-ENCODER] ══════ STAGE 2: CROSS-ENCODER RELEVANCE SCORING ══════"
    )
    logger.info(
        "[CROSS-ENCODER] Input: %d resumes | top_n=%d | min_score=%.4f | JD chars=%d",
        total, top_n, min_score, len(jd_text),
    )

    model = _get_cross_encoder()

    # Build input pairs (JD truncated, resume truncated)
    pairs = [
        (jd_text[:_JD_MAX_CHARS], r["parsed_text"][:_RESUME_MAX_CHARS])
        for r in resumes
    ]

    logger.info("[CROSS-ENCODER] Running inference on %d pairs...", total)
    t0 = time.time()
    raw_scores = model.predict(pairs, show_progress_bar=False)
    elapsed = time.time() - t0
    logger.info(
        "[CROSS-ENCODER] Inference done in %.2fs (%.0fms/resume)",
        elapsed, (elapsed / total * 1000) if total else 0,
    )

    # Attach scores and sort
    scored = []
    for i, r in enumerate(resumes):
        scored.append({**r, "relevance_score": float(raw_scores[i])})
    scored.sort(key=lambda r: -r["relevance_score"])

    selected: list[dict] = []
    rejected: list[RelevanceResult] = []

    logger.info("[CROSS-ENCODER] Ranking results:")
    for rank_0, r in enumerate(scored):
        rank = rank_0 + 1
        r["rank"] = rank
        score = r["relevance_score"]
        is_selected = len(selected) < top_n and score >= min_score

        if is_selected:
            selected.append(r)
            logger.info(
                "[CROSS-ENCODER]   [%d/%d] resume=%-36s score=%.4f → SELECTED",
                rank, total, r["resume_id"], score,
            )
        else:
            reason = (
                f"Relevance ranked {rank} of {total} — "
                "not selected for full evaluation"
            )
            rejected.append(
                RelevanceResult(
                    resume_id=str(r["resume_id"]),
                    relevance_score=score,
                    rank=rank,
                    selected=False,
                    rejection_reason=reason,
                )
            )
            logger.info(
                "[CROSS-ENCODER]   [%d/%d] resume=%-36s score=%.4f → PRE-SCREENED OUT",
                rank, total, r["resume_id"], score,
            )

    logger.info(
        "[CROSS-ENCODER] ══ RESULT: %d selected for LLM scoring, %d pre-screened out of %d total ══",
        len(selected), len(rejected), total,
    )

    return selected, rejected
