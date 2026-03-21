"""
JD Generation Pipeline — Q&A answers → polished Job Description markdown.

Design:
  - Uses Gemini 2.5 Flash via LangChain with_structured_output() for reliable JSON
  - Single LLM call (no post-processing needed for simple text generation)
  - No DB writes — caller handles persistence
  - Mirrors the existing rubric generation pattern
"""

from typing import Optional
from pydantic import BaseModel

from configs.log_config import get_logger
from src.pipelines.models import llm
from src.pipelines.jd_builder_prompts import JD_GENERATION_PROMPT, JD_FROM_PROMPT
from src.schemas.jd_builder_schemas import JDBuilderAnswers
from src.pipelines.llm_retry import retry_with_backoff

logger = get_logger("generate_jd")

TIMEOUT_SECONDS = 90


# ── LLM output schema ──────────────────────────────────────────────────────────

class _JDLLMOutput(BaseModel):
    """Structured output the LLM must return."""
    job_description_markdown: str
    suggested_title: str
    suggested_location: Optional[str] = None
    suggested_salary: Optional[str] = None


# ── Pipeline ───────────────────────────────────────────────────────────────────

_jd_chain = llm.with_structured_output(_JDLLMOutput)


def _format_list(items: Optional[list]) -> str:
    if not items:
        return "Not specified"
    return "\n".join(f"- {item}" for item in items)


def _fmt(value) -> str:
    if not value:
        return "Not specified"
    return str(value)


def _build_prompt(answers: JDBuilderAnswers) -> str:
    exp_range = "Not specified"
    if answers.experience_years_min is not None and answers.experience_years_max is not None:
        exp_range = f"{answers.experience_years_min}–{answers.experience_years_max} years"
    elif answers.experience_years_min is not None:
        exp_range = f"{answers.experience_years_min}+ years"
    elif answers.experience_years_max is not None:
        exp_range = f"Up to {answers.experience_years_max} years"

    return JD_GENERATION_PROMPT.format(
        role_title=answers.role_title,
        department=_fmt(answers.department),
        openings=_fmt(answers.openings),
        experience_level=answers.experience_level.title(),
        experience_range=exp_range,
        employment_type=_fmt(answers.employment_type).replace("_", "-").title() if answers.employment_type else "Not specified",
        work_mode=_fmt(answers.work_mode).title() if answers.work_mode else "Not specified",
        location=_fmt(answers.location),
        salary_range=_fmt(answers.salary_range),
        responsibilities=answers.responsibilities,
        skills_required=_format_list(answers.skills_required),
        skills_nice_to_have=_format_list(answers.skills_nice_to_have),
        education=_fmt(answers.education),
        certifications=_fmt(answers.certifications),
        company_description=_fmt(answers.company_description),
        role_highlights=_fmt(answers.role_highlights),
        benefits=_fmt(answers.benefits),
        special_requirements=_fmt(answers.special_requirements),
    )


async def generate_jd_from_prompt(prompt: str) -> _JDLLMOutput:
    """Generate a JD from a free-form recruiter prompt."""
    logger.info(f"[GENERATE_JD] Generating JD from prompt ({len(prompt)} chars)")
    filled = JD_FROM_PROMPT.format(prompt=prompt)

    async def _call():
        return await _jd_chain.ainvoke(filled)

    result = await retry_with_backoff(
        _call,
        max_retries=2,
        base_delay=2,
        timeout_per_attempt=TIMEOUT_SECONDS,
        operation_name="jd_generation_from_prompt",
    )
    logger.info(f"[GENERATE_JD] Done: title='{result.suggested_title}' chars={len(result.job_description_markdown)}")
    return result


async def generate_jd_from_answers(answers: JDBuilderAnswers) -> _JDLLMOutput:
    """
    Generate a polished Job Description from structured Q&A answers.

    Returns a _JDLLMOutput with:
      - job_description_markdown: full markdown JD text
      - suggested_title: normalised job title
      - suggested_location: extracted location or None
      - suggested_salary: extracted salary range or None

    Raises:
      DomainError on LLM failure (via retry_with_backoff)
    """
    prompt = _build_prompt(answers)
    logger.info(f"[GENERATE_JD] Generating JD for role: {answers.role_title}")

    async def _call():
        return await _jd_chain.ainvoke(prompt)

    result = await retry_with_backoff(
        _call,
        max_retries=2,
        base_delay=2,
        timeout_per_attempt=TIMEOUT_SECONDS,
        operation_name="jd_generation",
    )

    logger.info(
        f"[GENERATE_JD] Generated JD: title='{result.suggested_title}' "
        f"chars={len(result.job_description_markdown)}"
    )
    return result
