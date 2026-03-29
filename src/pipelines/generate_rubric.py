"""
Rubric Generation Pipeline — single-call JD + job_data → rubric JSON.

Takes raw JD text AND user-entered job_data (temp JSON from basic details form)
to generate a domain-aware, weighted rubric for ATS scoring.

Design:
- NO DB writes (caller handles persistence)
- Includes job_data context in AI prompt so user-entered location/salary/degree
  can inform mandatory constraints without requiring re-upload
- Validates and post-processes the raw LLM response before returning
"""

import asyncio
import json
from typing import Any, Optional

from configs.log_config import get_logger
from langchain_core.prompts import PromptTemplate
from src.pipelines.llm_retry import retry_with_backoff
from src.pipelines.models import llm
from src.pipelines.rubric_prompts import RUBRIC_FROM_JD_PROMPT_V2, RUBRIC_FIXER_PROMPT
from src.pipelines.rubric_post_processor import (
    is_valid_json,
    post_process_rubric,
    validate_rubric_json,
)
from src.services.errors.pipeline_errors import (
    RubricGenerationFailed,
    RubricGenerationTimeout,
    RubricValidationFailed,
)

logger = get_logger("generate_rubric")

MAX_RETRIES = 1
RETRY_BASE_DELAY = 2  # seconds
TIMEOUT_PER_ATTEMPT = 90  # seconds — slightly more to handle context
TIMEOUT_FIXER_ATTEMPT = 60  # seconds — second pass should be faster
MAX_JD_CHARS = 15000


def _extract_json_object(text: str) -> str:
    """
    Best-effort extraction when the model wraps JSON in extra text.
    We still validate strictly after extraction.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return text
    return text[start : end + 1]


_REPAIR_PROMPT = PromptTemplate(
    template="""
You are fixing an ATS rubric JSON to match a strict schema.

You MUST return ONLY valid JSON. No markdown. No explanations.
All numeric fields must be numbers (not strings, not booleans).
Arrays must never be null.

Here is the previous JSON output:
{bad_json}

Validation errors:
{errors}

Return corrected JSON only.
""",
    input_variables=["bad_json", "errors"],
)


def _build_job_context_string(job_data: Optional[dict]) -> str:
    """
    Convert job_data dict to a human-readable string for the AI prompt.
    This provides the "temp JSON" context from the user's basic details form.
    """
    if not job_data:
        return "No additional job context provided."

    lines = []
    if job_data.get("title"):
        lines.append(f"- Job Title: {job_data['title']}")
    if job_data.get("description"):
        desc = job_data["description"]
        if len(desc) > 500:
            desc = desc[:500] + "..."
        lines.append(f"- Description Summary: {desc}")
    if job_data.get("location"):
        lines.append(f"- Location: {job_data['location']}")
    if job_data.get("salary"):
        lines.append(f"- Salary / Compensation: {job_data['salary']}")
    if job_data.get("target_headcount"):
        lines.append(f"- Target Headcount: {job_data['target_headcount']}")
    if job_data.get("voice_ai_enabled"):
        lines.append(f"- Voice AI Screening Enabled: {job_data['voice_ai_enabled']}")
    if job_data.get("is_confidential"):
        lines.append(f"- Confidential Posting: {job_data['is_confidential']}")

    if not lines:
        return "No additional job context provided."

    return "\n".join(lines)


async def generate_rubric_from_jd(
    jd_text: str,
    job_data: Optional[dict] = None,
    use_cache: bool = True,
) -> dict:
    """
    Generate a weighted rubric JSON from a JD + optional job_data (temp JSON).

    Args:
        jd_text:  Raw extracted JD text.
        job_data: Optional dict from the user's basic-details form (temp JSON).
                  Used to provide context for location/salary/degree constraints.
        use_cache: Kept for API compatibility; not used in single-call version.

    Returns:
        PipelineRubricOutput-compatible dict: domain, domain_confidence,
        threshold_score, version, sections (with criteria + importance + weight).
    """
    # Keep signature arg for compatibility; not used in single-call version
    _ = use_cache

    if len(jd_text) > MAX_JD_CHARS:
        jd_text = jd_text[:MAX_JD_CHARS]
        logger.warning("JD text truncated to %d chars", MAX_JD_CHARS)

    job_context_str = _build_job_context_string(job_data)

    chain = RUBRIC_FROM_JD_PROMPT_V2 | llm
    fixer_chain = RUBRIC_FIXER_PROMPT | llm

    async def _op() -> Any:
        return await chain.ainvoke({"jd_text": jd_text, "job_context": job_context_str})

    async def _fixer_op(rubric_json: str) -> Any:
        return await fixer_chain.ainvoke({"jd_text": jd_text, "rubric_json": rubric_json})

    async def _repair(bad_json: str, errors: list[str]) -> str:
        repair_chain = _REPAIR_PROMPT | llm
        repaired = await repair_chain.ainvoke(
            {
                "bad_json": bad_json,
                "errors": "\n".join(errors[:25]),
            }
        )
        return (getattr(repaired, "content", None) or str(repaired)).strip()

    try:
        result = await retry_with_backoff(
            operation=_op,
            operation_name="rubric_from_jd",
            max_retries=MAX_RETRIES,
            base_delay=RETRY_BASE_DELAY,
            timeout_per_attempt=TIMEOUT_PER_ATTEMPT,
        )

        raw_text = getattr(result, "content", None) or str(result)
        candidate = raw_text.strip()

        if not is_valid_json(candidate):
            candidate = _extract_json_object(candidate).strip()

        if not is_valid_json(candidate):
            raise RubricValidationFailed(message="LLM did not return valid JSON.")

        payload = json.loads(candidate)
        processed = post_process_rubric(payload)

        ok, errors = validate_rubric_json(processed)
        if not ok:
            logger.warning("Rubric validation failed (first pass): %s", "; ".join(errors[:12]))
            # One repair attempt using the model (only on failure)
            repaired_text = await _repair(candidate, errors)
            if not is_valid_json(repaired_text):
                repaired_text = _extract_json_object(repaired_text).strip()
            if not is_valid_json(repaired_text):
                raise RubricValidationFailed(message="; ".join(errors[:10]))

            repaired_payload = json.loads(repaired_text)
            processed = post_process_rubric(repaired_payload)
            ok2, errors2 = validate_rubric_json(processed)
            if not ok2:
                logger.warning("Rubric validation failed (after repair): %s", "; ".join(errors2[:12]))
                raise RubricValidationFailed(message="; ".join(errors2[:10]))

        logger.info(
            "Rubric generated: sections=%d, total_criteria=%d (with job_data context=%s)",
            len(processed.get("sections", [])),
            sum(len(s.get("criteria", [])) for s in processed.get("sections", [])),
            bool(job_data),
        )

        # --- Second pass: compact + de-duplicate rubric (best-effort) ---
        try:
            rubric_json_in = json.dumps(processed, ensure_ascii=False)
            fixer_result = await retry_with_backoff(
                operation=lambda: _fixer_op(rubric_json_in),
                operation_name="rubric_fixup",
                max_retries=1,
                base_delay=RETRY_BASE_DELAY,
                timeout_per_attempt=TIMEOUT_FIXER_ATTEMPT,
            )

            fixer_text = (getattr(fixer_result, "content", None) or str(fixer_result)).strip()
            if not is_valid_json(fixer_text):
                fixer_text = _extract_json_object(fixer_text).strip()

            if is_valid_json(fixer_text):
                fixer_payload = json.loads(fixer_text)
                fixed = post_process_rubric(fixer_payload)
                ok_fix, fix_errors = validate_rubric_json(fixed)
                if ok_fix:
                    processed = fixed
                    logger.info(
                        "Rubric fixup applied: sections=%d, total_criteria=%d",
                        len(processed.get("sections", [])),
                        sum(len(s.get("criteria", [])) for s in processed.get("sections", [])),
                    )
                else:
                    logger.warning("Rubric fixup failed validation: %s", "; ".join(fix_errors[:8]))
            else:
                logger.warning("Rubric fixup did not return valid JSON; keeping first-pass rubric.")
        except Exception as e:
            logger.warning("Rubric fixup failed; keeping first-pass rubric: %s", e)

        # Keep domain deterministic to avoid "domain identification" behavior
        processed["domain"] = "other"
        processed["domain_confidence"] = 0.5
        return processed

    except asyncio.TimeoutError:
        logger.error("Rubric generation timed out after %d attempts", MAX_RETRIES)
        raise RubricGenerationTimeout()

    except RubricValidationFailed:
        raise

    except Exception as e:
        logger.exception("Rubric generation failed: %s", e)
        raise RubricGenerationFailed(message=str(e))
