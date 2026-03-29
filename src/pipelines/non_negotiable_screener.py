"""
Non-Negotiable Screener (Stage 2.5) — binary pass/fail checks.

Runs AFTER the cross-encoder relevance filter, BEFORE LLM scoring.
Uses the fast screening model (flash-lite) for cheap, quick binary checks.

Each non-negotiable criterion is verified as:
  - passed=True  (evidence found in resume)
  - passed=False (contradicting evidence or clearly absent)
  - passed=None  (insufficient evidence — flagged for human review, NOT auto-rejected)

Rejection rule:
  If ANY non-negotiable has passed=False AND confidence >= 0.7 → auto-reject.
  Low-confidence failures are flagged but NOT rejected.

Cost: ~$0.001 per resume (flash-lite, simple schema).
Latency: ~200-500ms per resume.
"""

from dataclasses import dataclass
from typing import Optional

from configs.log_config import get_logger
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

logger = get_logger("non_negotiable_screener")

CONFIDENCE_THRESHOLD = 0.7
MAX_RESUME_CHARS_SCREENING = 8000  # less context needed for binary checks


# ─── LLM Output Schema ──────────────────────────────────────────────

class NonNegotiableCheckResult(BaseModel):
    """Result for a single non-negotiable criterion."""
    criterion_name: str = Field(description="Name of the non-negotiable criterion being checked")
    passed: Optional[bool] = Field(
        description="True if evidence supports the requirement, False if contradicted, null if unclear"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="How confident the model is in the pass/fail decision"
    )
    evidence: str = Field(
        default="",
        max_length=300,
        description="Verbatim quote from resume or 'No evidence found'"
    )


class NonNegotiableScreeningOutput(BaseModel):
    """Structured output for non-negotiable screening of a single resume."""
    results: list[NonNegotiableCheckResult] = Field(
        description="One result per non-negotiable criterion"
    )


# ─── Result Dataclass ────────────────────────────────────────────────

@dataclass(frozen=True)
class ScreeningResult:
    """Immutable result for a single resume's non-negotiable screening."""
    resume_id: str
    passed: bool
    failed_criteria: list[str]  # names of failed non-negotiables
    flagged_criteria: list[str]  # names with low confidence (for human review)
    details: list[dict]  # full per-criterion results (stored in DB as JSONB)


# ─── Prompt ──────────────────────────────────────────────────────────

_SCREENING_PROMPT = PromptTemplate(
    template="""You are a resume screening system checking BINARY DEALBREAKER requirements.

For each requirement below, determine if the candidate's resume meets it.

REQUIREMENTS TO CHECK:
{requirements_json}

RESUME TEXT:
{resume_text}

RULES:
- For each requirement, answer the verification question based ONLY on resume content.
- Set "passed" to true if the resume clearly meets the requirement.
- Set "passed" to false ONLY if the resume clearly contradicts or definitely does not meet the requirement.
- Set "passed" to null if the resume does not mention anything related (absence of information is NOT failure).
- Set "confidence" to how certain you are (0.0 to 1.0).
  - 0.9-1.0: Very clear evidence for or against
  - 0.7-0.89: Reasonably clear
  - 0.5-0.69: Somewhat ambiguous
  - Below 0.5: Very uncertain
- "evidence" must be a VERBATIM quote from the resume (max 200 chars), or "No evidence found".
- Do NOT infer or assume information not present in the resume.
- IMPORTANT: Absence of information is NOT failure. If a resume doesn't mention location, that does NOT mean they fail a location requirement — set passed=null.
""",
    input_variables=["requirements_json", "resume_text"],
)


# ─── Core Functions ──────────────────────────────────────────────────

def _build_requirements_json(non_negotiables: list[dict]) -> str:
    """Build a clean JSON string of requirements for the prompt."""
    import json
    requirements = []
    for nn in non_negotiables:
        requirements.append({
            "criterion_name": nn["name"],
            "display_name": nn["display_name"],
            "requirement": nn["requirement"],
            "verification_question": nn["verification_question"],
        })
    return json.dumps(requirements, indent=2)


def _evaluate_results(
    resume_id: str,
    llm_results: list[NonNegotiableCheckResult],
) -> ScreeningResult:
    """Evaluate LLM results and determine pass/fail."""
    failed: list[str] = []
    flagged: list[str] = []
    details: list[dict] = []

    for result in llm_results:
        detail = {
            "criterion_name": result.criterion_name,
            "passed": result.passed,
            "confidence": result.confidence,
            "evidence": result.evidence,
        }
        details.append(detail)

        if result.passed is False and result.confidence >= CONFIDENCE_THRESHOLD:
            failed.append(result.criterion_name)
            logger.info(
                "Non-negotiable FAILED: resume=%s criterion=%s confidence=%.2f evidence=%r",
                resume_id, result.criterion_name, result.confidence, result.evidence[:100],
            )
        elif result.passed is False and result.confidence < CONFIDENCE_THRESHOLD:
            flagged.append(result.criterion_name)
            logger.info(
                "Non-negotiable FLAGGED (low confidence): resume=%s criterion=%s confidence=%.2f",
                resume_id, result.criterion_name, result.confidence,
            )
        elif result.passed is None:
            flagged.append(result.criterion_name)

    overall_passed = len(failed) == 0

    return ScreeningResult(
        resume_id=resume_id,
        passed=overall_passed,
        failed_criteria=failed,
        flagged_criteria=flagged,
        details=details,
    )


def screen_non_negotiables_sync(
    resumes: list[dict],
    non_negotiables: list[dict],
) -> tuple[list[dict], list[ScreeningResult]]:
    """
    Screen resumes against non-negotiable criteria (synchronous, for workers).

    Args:
        resumes: list of dicts with {resume_id, parsed_text}
        non_negotiables: list of non-negotiable criterion dicts from the rubric

    Returns:
        (passed_resumes, failed_results) — passed resumes keep original dict;
        failed get a ScreeningResult with details.
    """
    from src.pipelines.models import fast_screening_model

    if not non_negotiables:
        logger.info("No non-negotiables defined — all resumes pass screening")
        return resumes, []

    structured_model = fast_screening_model.with_structured_output(
        NonNegotiableScreeningOutput
    )
    chain = _SCREENING_PROMPT | structured_model

    requirements_json = _build_requirements_json(non_negotiables)

    # Build batch inputs
    inputs = []
    resume_ids = []
    for resume in resumes:
        resume_id = str(resume["resume_id"])
        resume_ids.append(resume_id)
        text = (resume.get("parsed_text") or "")[:MAX_RESUME_CHARS_SCREENING]
        inputs.append({
            "requirements_json": requirements_json,
            "resume_text": text,
        })

    # Batch call (fast model, simple schema — can handle high concurrency)
    try:
        results = chain.batch(
            inputs,
            config={"max_concurrency": 20, "return_exceptions": True},
        )
    except Exception as e:
        logger.error("Non-negotiable screening batch failed: %s", e)
        # On total failure, let all resumes pass (fail-open) to avoid blocking pipeline
        logger.warning("Fail-open: all %d resumes pass non-negotiable screening", len(resumes))
        return resumes, []

    passed_resumes: list[dict] = []
    failed_results: list[ScreeningResult] = []

    for resume, resume_id, result in zip(resumes, resume_ids, results):
        if isinstance(result, Exception):
            logger.warning(
                "Non-negotiable screening failed for resume=%s: %s — passing by default",
                resume_id, result,
            )
            passed_resumes.append(resume)
            continue

        screening_result = _evaluate_results(resume_id, result.results)

        if screening_result.passed:
            passed_resumes.append(resume)
        else:
            failed_results.append(screening_result)

    logger.info(
        "Non-negotiable screening: %d passed, %d failed out of %d",
        len(passed_resumes), len(failed_results), len(resumes),
    )

    return passed_resumes, failed_results


async def screen_non_negotiables_async(
    resumes: list[dict],
    non_negotiables: list[dict],
) -> tuple[list[dict], list[ScreeningResult]]:
    """
    Async variant for API calls.
    Same logic as sync but uses abatch.
    """
    from src.pipelines.models import fast_screening_model

    if not non_negotiables:
        return resumes, []

    structured_model = fast_screening_model.with_structured_output(
        NonNegotiableScreeningOutput
    )
    chain = _SCREENING_PROMPT | structured_model

    requirements_json = _build_requirements_json(non_negotiables)

    inputs = []
    resume_ids = []
    for resume in resumes:
        resume_id = str(resume["resume_id"])
        resume_ids.append(resume_id)
        text = (resume.get("parsed_text") or "")[:MAX_RESUME_CHARS_SCREENING]
        inputs.append({
            "requirements_json": requirements_json,
            "resume_text": text,
        })

    try:
        results = await chain.abatch(
            inputs,
            config={"max_concurrency": 20, "return_exceptions": True},
        )
    except Exception as e:
        logger.error("Non-negotiable screening batch failed: %s", e)
        return resumes, []

    passed_resumes: list[dict] = []
    failed_results: list[ScreeningResult] = []

    for resume, resume_id, result in zip(resumes, resume_ids, results):
        if isinstance(result, Exception):
            logger.warning(
                "Non-negotiable screening failed for resume=%s: %s — passing by default",
                resume_id, result,
            )
            passed_resumes.append(resume)
            continue

        screening_result = _evaluate_results(resume_id, result.results)

        if screening_result.passed:
            passed_resumes.append(resume)
        else:
            failed_results.append(screening_result)

    logger.info(
        "Non-negotiable screening: %d passed, %d failed out of %d",
        len(passed_resumes), len(failed_results), len(resumes),
    )

    return passed_resumes, failed_results
