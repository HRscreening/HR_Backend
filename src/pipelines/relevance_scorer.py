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

import requests
from configs.env_config import HF_TOKEN, USE_HF_API
from configs.log_config import get_logger


logger = get_logger("relevance_scorer")

# Lazy-loaded singleton — model loads once at first use (~1.1 GB)
_cross_encoder = None

# Hugging Face Inference API Config
HF_MODEL_ID = "BAAI/bge-reranker-v2-m3"
HF_API_URL = f"https://router.huggingface.co/hf-inference/models/{HF_MODEL_ID}"

# Toggle between HF API and Local Inference
# Set to True to use cloud API (reduces Docker size), False for local

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


def _query_hf_inference_api(payload):
    """Call Hugging Face Inference API with retry logic."""
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    for attempt in range(3):
        try:
            response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=120)
            if response.status_code == 200:
                result = response.json()
                # Some models return scores directly, others wrap in a list
                return result
            elif response.status_code == 503:
                # Model is loading
                estimated_time = response.json().get("estimated_time", 20)
                logger.warning(
                    f"[HF-API] Model {HF_MODEL_ID} is loading. Waiting {estimated_time}s (attempt {attempt+1}/3)..."
                )
                time.sleep(estimated_time)
                continue
            else:
                logger.error(f"[HF-API] Error {response.status_code}: {response.text}")
                break
        except Exception as e:
            logger.error(f"[HF-API] Exception: {str(e)}")
            time.sleep(2)
    return None


def _get_cross_encoder():
    """Lazy-load cross-encoder model (singleton, thread-safe enough for workers)."""
    global _cross_encoder
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder

        logger.info(
            f"[CROSS-ENCODER] Loading local model {HF_MODEL_ID} (~1.1 GB) — first use only..."
        )
        _cross_encoder = CrossEncoder(HF_MODEL_ID, max_length=8192)
        logger.info("[CROSS-ENCODER] Local model loaded and cached in memory.")
    else:
        logger.info("[CROSS-ENCODER] Using cached local model.")
    return _cross_encoder


def score_relevance_batch(
    resumes: list[dict],
    jd_text: str,
    top_n: int = DEFAULT_TOP_N,
    min_score: float = _MIN_SCORE,
) -> tuple[list[dict], list[RelevanceResult]]:
    """
    Score all resumes against JD using either HF API or local cross-encoder.

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

    mode_str = "HUGGING FACE API" if USE_HF_API else "LOCAL CROSS-ENCODER"
    logger.info(f"[CROSS-ENCODER] ══════ STAGE 2: {mode_str} RELEVANCE SCORING ══════")
    logger.info(
        "[CROSS-ENCODER] Input: %d resumes | top_n=%d | min_score=%.4f | JD chars=%d",
        total,
        top_n,
        min_score,
        len(jd_text),
    )

    raw_scores = []
    t0 = time.time()

    if USE_HF_API:
        if not HF_TOKEN:
            logger.warning("[HF-API] HF_TOKEN is missing! Falling back to local scoring...")
            # Use local fallback if token is missing
            raw_scores = _run_local_inference(resumes, jd_text)
        else:
            payload = {
                "inputs": [
                    {
                        "text": jd_text[:_JD_MAX_CHARS],
                        "text_pair": r["parsed_text"][:_RESUME_MAX_CHARS],
                    }
                    for r in resumes
                ]
            }
            logger.info("[HF-API] Calling API for %d pairs...", total)
            raw_response = _query_hf_inference_api(payload)
            
            # DEBUG: Print exact response structure
            logger.info(f"[HF-API-DEBUG] Raw Response: {raw_response}")

            if raw_response is None:
                logger.error("[HF-API] API failed. Falling back to local scoring...")
                raw_scores = _run_local_inference(resumes, jd_text)
            else:
                try:
                    # Handle nested list: [[{'label': '...', 'score': 0.9}, ...]]
                    if isinstance(raw_response, list) and len(raw_response) > 0 and isinstance(raw_response[0], list):
                        raw_response = raw_response[0]

                    if isinstance(raw_response, list) and len(raw_response) > 0 and isinstance(raw_response[0], dict):
                        # Some APIs return index, others assumed to be in order
                        # If 'index' exists, sort by it to be safe
                        if "index" in raw_response[0]:
                            scores_with_idx = sorted(raw_response, key=lambda x: x.get("index", 0))
                            raw_scores = [x["score"] for x in scores_with_idx]
                        else:
                            raw_scores = [x["score"] for x in raw_response]
                    else:
                        raw_scores = raw_response
                except Exception as e:
                    logger.error(f"[HF-API] Failed to parse scores: {str(e)}. Falling back to local...")
                    raw_scores = _run_local_inference(resumes, jd_text)
    else:
        # Explicit Local Inference choice
        raw_scores = _run_local_inference(resumes, jd_text)

    elapsed = time.time() - t0
    logger.info(
        "[CROSS-ENCODER] Scoring done in %.2fs (%.0fms/resume)",
        elapsed,
        (elapsed / total * 1000) if total else 0,
    )
    
    if not raw_scores:
        logger.error("[CROSS-ENCODER] Failed to get scores from any source.")
        return [], []

    # Attach scores and sort
    scored = []
    for i, r in enumerate(resumes):
        # Safety check for score index
        raw_val = raw_scores[i] if i < len(raw_scores) else 0.0
        
        # Handle different response formats from various providers/local:
        # 1. Float: 0.95
        # 2. List of float: [0.95]
        # 3. List of dict: [{"score": 0.95}]
        # 4. Dict: {"score": 0.95}
        
        score_val = 0.0
        try:
            if isinstance(raw_val, (list, tuple)) and len(raw_val) > 0:
                inner = raw_val[0]
                if isinstance(inner, dict):
                    score_val = float(inner.get("score", 0.0))
                else:
                    score_val = float(inner)
            elif isinstance(raw_val, dict):
                score_val = float(raw_val.get("score", 0.0))
            else:
                score_val = float(raw_val)
        except (ValueError, TypeError) as e:
            logger.error(f"[CROSS-ENCODER] Error parsing score for {r.get('resume_id')}: {e}")
            score_val = 0.0

        scored.append({**r, "relevance_score": score_val})
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
                rank,
                total,
                r["resume_id"],
                score,
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
                rank,
                total,
                r["resume_id"],
                score,
            )

    return selected, rejected


def _run_local_inference(resumes: list[dict], jd_text: str) -> list[float]:
    """Internal helper to run local inference as a fallback or primary method."""
    try:
        model = _get_cross_encoder()
        pairs = [
            (jd_text[:_JD_MAX_CHARS], r["parsed_text"][:_RESUME_MAX_CHARS])
            for r in resumes
        ]
        logger.info("[CROSS-ENCODER] Running local inference on %d pairs...", len(resumes))
        return model.predict(pairs, show_progress_bar=False)
    except Exception as e:
        logger.error(f"[CROSS-ENCODER] Local inference failed: {str(e)}")
        return []


# Remove _get_cross_encoder if no longer needed or keep for local fallback (commented out)
# def _get_cross_encoder(): ...

