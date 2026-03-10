# Extract candidate basic info (name, email, phone) from resume text.
#
# Uses Gemini's native structured output (with_structured_output) for
# guaranteed JSON schema compliance — no PydanticOutputParser needed.

from langchain_core.prompts import PromptTemplate
from src.pipelines.models import scoring_model
from src.schemas.user_schemas import CandidateInfoSchema
from configs.log_config import get_logger
from src.utils.pipeline_debug_log import pdlog
import re

logger = get_logger("CandidateInfoExtractor")


_PROMPT = PromptTemplate(
    template="""Extract the candidate's contact information and most recent employment from this resume text.

RESUME TEXT (first 2000 chars):
{resume_header}

RULES:
- full_name: The person's real name. Usually at the very top of the resume as a header.
  Look for a line with 2-4 words that is clearly a person's name (not a job title).
  Convert ALL_CAPS names to Title Case (e.g. "RAHUL VERMA" → "Rahul Verma").
  Return null if you cannot confidently identify the name.
- email: An email address containing '@'. Must be explicitly present in the text.
  Return null if not found.
- phone: A phone number with digits. Must be explicitly present in the text.
  Return null if not found.
- current_title: The candidate's most recent or current job title (e.g. "Senior Software Engineer").
  Look in the work experience or summary section for the latest role.
  Return null if not found.
- current_company: The company where the candidate currently works or most recently worked (e.g. "Google").
  Return null if not found.

CRITICAL:
- Do NOT invent or guess any values.
- Do NOT return placeholder values like "John Doe" or "example@email.com".
- Return null for any field you are not confident about.
""",
    input_variables=["resume_header"],
)


# Use native structured output — Gemini generates JSON matching the schema directly.
_structured_model = scoring_model.with_structured_output(CandidateInfoSchema)
_chain = _PROMPT | _structured_model


# ─── Heuristic fallbacks (no LLM needed) ────────────────────────────

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s\-.]?)?"           # optional country code
    r"(?:\(?\d{2,4}\)?[\s\-.]?)?"         # optional area code
    r"\d{3,4}[\s\-.]?\d{3,4}"            # main number
)


def extract_email_heuristic(text: str) -> str | None:
    """Extract the first valid-looking email from resume text."""
    m = _EMAIL_RE.search(text[:3000])
    return m.group(0) if m else None


def extract_phone_heuristic(text: str) -> str | None:
    """Extract the first phone-like number from resume text."""
    m = _PHONE_RE.search(text[:3000])
    if m:
        digits = re.sub(r"[^\d+]", "", m.group(0))
        if len(digits) >= 7:
            return m.group(0).strip()
    return None


# ─── Public API ──────────────────────────────────────────────────────

def extract_candidate_info_sync(resume_text: str) -> CandidateInfoSchema:
    """
    Extract candidate info from resume text.
    Uses LLM with structured output, falls back to heuristics for missing fields.
    """
    if not resume_text or not resume_text.strip():
        return CandidateInfoSchema()

    # Only send first 2000 chars to LLM — contact info is always at the top
    header = resume_text[:2000]

    llm_name = llm_email = llm_phone = None
    try:
        result = _chain.invoke({"resume_header": header})
        llm_name, llm_email, llm_phone = result.full_name, result.email, result.phone
        logger.info(
            "LLM extracted: name=%r email=%r phone=%r title=%r company=%r",
            result.full_name, result.email, result.phone, result.current_title, result.current_company,
        )
    except Exception as e:
        logger.warning("LLM candidate extraction failed: %s — using heuristics only", e)
        result = CandidateInfoSchema()

    # Fill missing fields with heuristics
    if not result.email:
        result.email = extract_email_heuristic(resume_text)
        if result.email:
            logger.info("Email found via heuristic: %s", result.email)

    if not result.phone:
        result.phone = extract_phone_heuristic(resume_text)
        if result.phone:
            logger.info("Phone found via heuristic: %s", result.phone)

    # Normalize ALL_CAPS names to Title Case
    if result.full_name and result.full_name == result.full_name.upper():
        result.full_name = " ".join(w.capitalize() for w in result.full_name.split())

    # Log to debug file with source breakdown
    pdlog.candidate_info(
        resume_id="(extraction)",
        full_name=result.full_name,
        email=result.email,
        phone=result.phone,
        source=f"llm(name={llm_name!r} email={llm_email!r} phone={llm_phone!r}) + heuristic",
    )

    return result


async def extract_candidate_info_async(resume_text: str) -> CandidateInfoSchema:
    """Async version for API-level calls."""
    if not resume_text or not resume_text.strip():
        return CandidateInfoSchema()

    header = resume_text[:2000]

    try:
        result = await _chain.ainvoke({"resume_header": header})
        logger.info(
            "LLM extracted: name=%r email=%r phone=%r",
            result.full_name, result.email, result.phone,
        )
    except Exception as e:
        logger.warning("LLM candidate extraction failed: %s — using heuristics only", e)
        result = CandidateInfoSchema()

    if not result.email:
        result.email = extract_email_heuristic(resume_text)

    if not result.phone:
        result.phone = extract_phone_heuristic(resume_text)

    if result.full_name and result.full_name == result.full_name.upper():
        result.full_name = " ".join(w.capitalize() for w in result.full_name.split())

    return result
