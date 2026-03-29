# Scores resumes against rubric criteria using LLM native structured output
# + weighted post-processing.
#
# Key design: uses with_structured_output() instead of PydanticOutputParser.
# This uses Gemini's native JSON mode (response_mime_type="application/json"
# + response_json_schema) which GUARANTEES the output matches the Pydantic
# schema structurally. No more malformed JSON or missing keys.

from langchain_core.prompts import PromptTemplate
from src.pipelines.models import scoring_model
from src.pipelines.score_post_processor import compute_flat_score_v2
from src.schemas.user_schemas import (
    LLMScoringOnlyOutput,
    ScoreOutputSchema,
    ResumeDataSchema,
    ResumeScoreResult,
    CandidateInfoSchema,
)
from configs.log_config import get_logger
from src.utils.pipeline_debug_log import pdlog
import json
import os

logger = get_logger("ResumeScoringPipeline")

MAX_RESUME_CHARS = int(os.environ.get("MAX_RESUME_CHARS", "24000"))


prompt = PromptTemplate(
    template="""You are an enterprise-grade Applicant Tracking System (ATS) scoring engine.

Your task is to evaluate the resume strictly according to the rubric criteria provided below.
You MUST base all judgments ONLY on the content explicitly present in the resume.

====================
RUBRIC CRITERIA (AUTHORITATIVE)
====================
{criteria}

====================
RESUME TEXT
====================
{resume_text}

====================
SCORING SCALE (MANDATORY — 0 to 10 integer, use these anchors for every criterion)
====================
10: World-class — top 1% evidence (patents, publications, major awards)
 9: Exceptional — exceeds requirement with multiple strong signals
 8: Strong+     — fully meets with specific, quantified evidence
 7: Strong      — meets with clear evidence, concrete but not quantified
 6: Adequate+   — meets with minor gaps
 5: Adequate    — basic requirement met, lacks depth
 4: Partial     — significant gaps or only adjacent skill
 3: Weak+       — tangential evidence only
 2: Weak        — keyword appears, no supporting context
 1: Trace       — barely mentioned
 0: None        — no evidence found

====================
SCORING RULES (STRICT)
====================
- Score each criterion and sub-criterion independently using the 0-10 scale above.
- For each criterion and sub-criterion, provide a concise "reasoning" (1 sentence) explaining the score.
- Use BOTH explicit evidence and strong implicit evidence from the resume.
- Penalize criteria only when there is truly no supporting evidence.
- Do NOT reward speculation beyond resume content.
- Consider these differentiators carefully:
  * Years of experience specificity (exact numbers like "7 years" vs vague "extensive experience")
  * Technology version specificity (e.g., "React 18" vs just "React")
  * Project scale indicators (team size, user count, revenue impact)
  * Certifications vs self-reported skills
  * Quantified achievements vs generic statements (e.g., "increased revenue 30%" vs "improved performance")
  * Leadership scope (managed 2 people vs managed 50 people)
- Do NOT produce an overall_score. Only produce per-section, per-criterion scores.

====================
SECTIONS RULE (CRITICAL — READ CAREFULLY)
====================
- The "sections" keys in your output MUST be EXACTLY these keys from the rubric: {section_keys}
- Within each section, criteria keys MUST EXACTLY match the rubric criterion names.
- If a criterion has sub_criteria in the rubric, score each sub_criterion individually.
- Do NOT add, remove, or rename any sections or criteria. Copy the keys exactly.

====================
GROUNDING RULE (VERY IMPORTANT)
====================
- grounding_data provides evidence justifying each criterion's score.
- Structure: grounding_data[section_key][criterion_name] with these fields:
  - "jd_requirement": What the JD requires (from rubric criterion's value or display_name). 1 concise sentence.
  - "evidence": AT MOST 3 evidence snippets, each <= 200 characters. Use EXACT VERBATIM quotes from the resume. Do NOT paraphrase.
  - "match_assessment": One of "exceeds", "strong", "partial", "weak", "none".
- If no evidence exists, return empty array [] for evidence and "none" for match_assessment.

====================
DISTINGUISHING FACTORS
====================
- Identify 2-4 unique or rare qualifications that make this candidate stand out (positively OR negatively).
- Return as a list of short strings (1 sentence each).

====================
AI ANALYSIS SUMMARY
====================
- Provide a qualitative, high-level review of the resume.
- Do NOT reference scores, rubric, criteria, or grounding data.
- Use ONLY information present in the resume.
- Return exactly two keys: "good_points" and "bad_points" (lists of short bullet sentences, 1-2 lines each).

====================
FAILURE RULE
====================
- If the resume is empty or irrelevant, return 0 for all criteria.
""",
    input_variables=["criteria", "resume_text", "section_keys"],
)


# Use native structured output — Gemini generates JSON matching the schema directly.
# This is the key fix: no more PydanticOutputParser text-based parsing.
_structured_model = scoring_model.with_structured_output(LLMScoringOnlyOutput)
chain = prompt | _structured_model


def _truncate_resume(text: str) -> str:
    """Truncate resume text to prevent token bloat."""
    if len(text) > MAX_RESUME_CHARS:
        logger.warning(
            "Resume text truncated from %d to %d chars",
            len(text), MAX_RESUME_CHARS
        )
        return text[:MAX_RESUME_CHARS]
    return text


def _extract_section_keys(criteria: dict) -> str:
    """Extract section keys from rubric criteria to pass explicitly in the prompt."""
    sections = criteria.get("sections", [])
    keys = [s.get("key", "") for s in sections if s.get("key")]
    return json.dumps(keys)


def _post_process_score(
    llm_result: LLMScoringOnlyOutput,
    rubric_criteria: dict,
    candidate_info: CandidateInfoSchema | None = None,
) -> ScoreOutputSchema:
    """Convert raw LLM per-criterion scores into weighted overall score."""
    rubric_sections = rubric_criteria.get("sections", [])

    # Convert pydantic models to dicts for the post-processor
    llm_sections = {}
    for section_key, section_data in llm_result.sections.items():
        criteria_dict = {}
        for c_name, c_data in section_data.criteria.items():
            sub_dict = {}
            for s_name, s_data in (c_data.sub_criteria or {}).items():
                sub_dict[s_name] = {
                    "score": s_data.score,
                    "reasoning": s_data.reasoning,
                }
            criteria_dict[c_name] = {
                "score": c_data.score,
                "reasoning": c_data.reasoning,
                "sub_criteria": sub_dict,
            }
        llm_sections[section_key] = {"criteria": criteria_dict}

    # Log what LLM returned before post-processing
    rubric_keys = [s["key"] for s in rubric_sections]
    section_criterion_scores = {
        sk: {cn: cd["score"] for cn, cd in sv["criteria"].items()}
        for sk, sv in llm_sections.items()
    }
    pdlog.scoring_llm_output(
        resume_id="(batch)",
        llm_section_keys=list(llm_sections.keys()),
        rubric_section_keys=rubric_keys,
        section_criterion_scores=section_criterion_scores,
    )

    computed = compute_flat_score_v2(
        llm_sections=llm_sections,
        rubric_sections=rubric_sections,
    )

    # Log if score looks suspicious
    if computed["overall_score"] == 0:
        logger.error(
            "Post-processed score is 0. LLM section keys: %s | Rubric section keys: %s",
            list(llm_result.sections.keys()),
            [s["key"] for s in rubric_sections],
        )

    # Convert grounding_data pydantic models to dicts
    grounding_dict = {}
    for section_key, section_grounding in llm_result.grounding_data.items():
        if isinstance(section_grounding, dict):
            grounding_dict[section_key] = {}
            for c_name, c_grounding in section_grounding.items():
                if hasattr(c_grounding, 'model_dump'):
                    grounding_dict[section_key][c_name] = c_grounding.model_dump()
                elif isinstance(c_grounding, dict):
                    grounding_dict[section_key][c_name] = c_grounding
                else:
                    grounding_dict[section_key][c_name] = c_grounding
        else:
            grounding_dict[section_key] = section_grounding

    # Determine non-negotiable status based on rubric
    has_non_negotiables = bool(rubric_criteria.get("non_negotiables"))
    nn_status = "all_passed" if has_non_negotiables else "no_non_negotiables"

    return ScoreOutputSchema(
        candidate_info=candidate_info or CandidateInfoSchema(),
        ai_analysis=llm_result.ai_analysis,
        overall_score=computed["overall_score"],
        ai_confidence=llm_result.ai_confidence,
        breakdown=computed["section_scores"],
        grounding_data=grounding_dict,
        distinguishing_factors=llm_result.distinguishing_factors,
        scoring_method=computed.get("scoring_method", "flat_v1"),
        non_negotiable_status=nn_status,
    )


# For API calls (small number of resumes — async)
async def score_resume_async(
    resumes: list[ResumeDataSchema],
    criteria: dict,
    candidate_infos: dict[str, CandidateInfoSchema] | None = None,
):
    """Score resumes asynchronously. candidate_infos maps resume_id → CandidateInfoSchema."""
    try:
        inputs = []
        application_ids = []
        resume_ids = []
        section_keys = _extract_section_keys(criteria)

        for resume in resumes:
            application_ids.append(resume.application_id)
            resume_ids.append(resume.resume_id)
            inputs.append({
                "criteria": json.dumps(criteria),
                "resume_text": _truncate_resume(resume.resume_text),
                "section_keys": section_keys,
            })

        results = await chain.abatch(
            inputs,
            config={
                "max_concurrency": 15,
                "return_exceptions": True
            }
        )

        final_responses = []

        for app_id, resume_id, result in zip(application_ids, resume_ids, results):
            if isinstance(result, Exception):
                logger.error(f"Scoring failed for application_id={app_id}: {result}")
                final_responses.append({
                    "application_id": app_id,
                    "resume_id": resume_id,
                    "error": str(result)
                })
            else:
                ci = (candidate_infos or {}).get(str(resume_id))
                final_responses.append({
                    "application_id": app_id,
                    "resume_id": resume_id,
                    "score": _post_process_score(result, criteria, ci)
                })

        return final_responses

    except Exception:
        logger.exception("Resume scoring batch failed")
        raise


# For synchronous calls (workers — larger batches)
def score_resume_sync(
    resumes: list[ResumeDataSchema],
    criteria: dict,
    candidate_infos: dict[str, CandidateInfoSchema] | None = None,
):
    """Score resumes synchronously. candidate_infos maps resume_id → CandidateInfoSchema."""
    try:
        inputs = []
        application_ids = []
        resume_ids = []
        section_keys = _extract_section_keys(criteria)

        for resume in resumes:
            resume_ids.append(resume.resume_id)
            application_ids.append(resume.application_id)
            inputs.append({
                "criteria": json.dumps(criteria),
                "resume_text": _truncate_resume(resume.resume_text),
                "section_keys": section_keys,
            })

        results = chain.batch(
            inputs,
            config={
                "max_concurrency": 15,
                "return_exceptions": True
            }
        )

        logger.info("LLM scoring call done. Processing %d results.", len(results))

        response: list[ResumeScoreResult] = []

        for resume_id, application_id, result in zip(resume_ids, application_ids, results):
            if isinstance(result, Exception):
                logger.error(f"Scoring failed for resume_id={resume_id}: {result}")
                continue

            ci = (candidate_infos or {}).get(str(resume_id))
            response.append(ResumeScoreResult(
                resume_id=resume_id,
                application_id=application_id,
                score=_post_process_score(result, criteria, ci)
            ))

        return response

    except Exception:
        logger.exception("Resume scoring batch failed")
        raise
