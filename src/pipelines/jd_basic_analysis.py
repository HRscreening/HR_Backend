"""
Basic JD analysis — fast UI prefill (Step 1: Upload JD).

This should be materially faster than full rubric generation.
It extracts: domain + job_data (title/description/location/salary).
"""

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate

from src.pipelines.models import llm
from src.schemas.jd_basic_analysis_schema import JDBasicAnalysisSchema
from src.schemas.rubric_schemas import VALID_DOMAINS


_parser = PydanticOutputParser(pydantic_object=JDBasicAnalysisSchema)

_PROMPT = PromptTemplate(
    template="""
You are an expert Job Description (JD) analyzer.

TASK
Extract only the minimum fields needed to prefill a job creation form.

OUTPUT KEYS (ONLY)
- domain: one of {valid_domains}
- domain_confidence: 0.0–1.0
- job_data:
  - title (best-guess role title)
  - description (2–5 sentences summary of responsibilities)
  - location (ONLY if explicitly present; else null)
  - salary (ONLY if explicitly present as a range/figure; else null)
  - target_headcount (default 1 unless explicitly stated)

RULES (CRITICAL)
- Use ONLY the JD text below. Do NOT hallucinate.
- Return ONLY valid JSON (no markdown, no explanations).
- If a field is not present, use null (for location/salary) or sensible defaults (target_headcount=1).

JOB DESCRIPTION
{jd_text}

OUTPUT SCHEMA
{format_instructions}
""",
    input_variables=["jd_text"],
    partial_variables={
        "format_instructions": _parser.get_format_instructions(),
        "valid_domains": VALID_DOMAINS,
    },
)


async def analyze_jd_basic(jd_text: str) -> dict:
    chain = _PROMPT | llm | _parser
    result = await chain.ainvoke({"jd_text": jd_text})
    return result.model_dump()

