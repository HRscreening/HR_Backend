# Makes a parallel call for resumes 

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from src.pipelines.models import llm
from src.schemas.score_schemas import ScoreOutputSchema,ResumeDataSchema,ResumeScoreResult,ResumeScoreFailure

from configs.log_config import get_logger
from src.pipelines.models import scoring_model
from configs.log_config import get_logger
import json
from dataclasses import dataclass
# from data.test_data import data
from pydantic import BaseModel

logger = get_logger("ResumeScoringPipeline")

output_parser = PydanticOutputParser(pydantic_object=ScoreOutputSchema)

format_instructions = output_parser.get_format_instructions()

prompt = PromptTemplate(
    template="""
You are an enterprise-grade Applicant Tracking System (ATS) scoring engine.

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
SCORING RULES (STRICT)
====================
- Score each criterion independently on a scale of 0–100.
- Use BOTH explicit evidence and strong implicit evidence.
- Penalize criteria only when there is truly no supporting evidence.
- Do NOT reward speculation beyond resume content.

====================
CANDIDATE INFO RULE (CRITICAL)
====================
- If you are NOT 100"%" certain that a field is explicitly labeled,
  you MUST return null.
- NEVER return placeholder values such as "John Doe".

====================
BREAKDOWN RULE (CRITICAL)
====================
- The breakdown JSON structure MUST exactly match the rubric structure.
- Use the same criterion keys as in the rubric.
- Do NOT add or remove criteria.
- If a criterion has no sub-criteria, return an EMPTY OBJECT.
- NEVER return null for sub_criteria.


====================
GROUNDING RULE (VERY IMPORTANT)
====================
- grounding_data provides minimal evidence justifying each score.
- For EACH criterion:
  - Include AT MOST 2 evidence snippets.
  - Each snippet must be ≤ 120 characters.
  - Prefer the STRONGEST and most specific evidence only.
- Use near-verbatim resume excerpts (light trimming allowed).
- Do NOT repeat the same evidence across multiple criteria.
- If no evidence exists, return an EMPTY ARRAY [] for that criterion.
- grounding_data must be concise and readable by humans.

====================
AI ANALYSIS SUMMARY
====================
- Provide a qualitative, high-level review of the resume.
- Do NOT reference scores, rubric, criteria, or grounding data.
- Use ONLY information present in the resume.
- Summarize overall strengths and weaknesses without repeating earlier evidence.
- Be factual, neutral, and concise.

    OUTPUT:
    - Return exactly two keys: "good_points" and "bad_points".
    - Each value is a list of short bullet-style sentences (1–2 lines).
    - If no weaknesses exist, return an empty list for "bad_points".

====================
OUTPUT REQUIREMENTS
====================
- Return ONLY valid JSON.
- Follow the schema EXACTLY.

SCHEMA:
{format_instructions}

====================
FAILURE RULE
====================
- If the resume is empty or irrelevant, return very low scores.
""",
    input_variables=["criteria", "resume_text"],
    partial_variables={
        "format_instructions": output_parser.get_format_instructions()
    }
)


chain = prompt | scoring_model | output_parser





# For API calls (if uploaded resumes number is less than 5) | Not strictly 5 but idle for small number of resumes
async def score_resume_async(resumes: list[ResumeDataSchema], criteria: dict):
    try:
        inputs = []
        application_ids = []
        resume_ids = []

        for resume in resumes:
            application_ids.append(resume.application_id)
            resume_ids.append(resume.resume_id)
            inputs.append({
                "criteria": json.dumps(criteria),
                "resume_text": resume.resume_text
            })
            
        # return inputs

        results = await chain.abatch(
            inputs,
            config={
                "max_concurrency": 5,
                "return_exceptions": True
            }
        )
        


        final_responses = []

        for app_id,resume_id,result in zip(application_ids,resume_ids, results):
            if isinstance(result, Exception):
                logger.error(f"Scoring failed for application_id={app_id}: {result}")
                final_responses.append({
                    "application_id": app_id,
                    "resume_id": resume_id,
                    "error": str(result)
                })
            else:
                final_responses.append({
                    "application_id": app_id,
                    "resume_id": resume_id,
                    "score": result
                })

        return final_responses

    except Exception:
        logger.exception("Resume scoring batch failed")
        raise








# For synchronous calls (if uploaded resumes number is more than 5) | Will be used by workers 
def score_resume_sync(resumes: list[ResumeDataSchema], criteria: dict):
    try:
        inputs = []
        application_ids = []
        resume_ids = []
        

        for resume in resumes:
            resume_ids.append(resume.resume_id)
            application_ids.append(resume.application_id)
            inputs.append({
                "criteria": json.dumps(criteria),
                "resume_text": resume.resume_text
            })

        results = chain.batch(
            inputs,
            config={
                "max_concurrency": 5, # TODO: Can be made dynamic
                "return_exceptions": True
            }
        )
        
        print("\n\n\nLLM CALL DONE. Processing results...\n\n\n")
        # print("Raw results from chain.batch:\n\n\n", results,"\n\n\n\n")

        response: list[ResumeScoreResult] = []

        for resume_id,application_id,result in zip(resume_ids,application_ids, results):
            if isinstance(result, Exception):
                logger.error(f"Scoring failed for resume_id={resume_id}: {result}")
                continue

            response.append(ResumeScoreResult(
                resume_id=resume_id,
                application_id=application_id,
                score=result
            ))

        return response

    except Exception:
        logger.exception("Resume scoring batch failed")
        raise








async def score_resume_with_text(
    resumes: list[ResumeDataSchema],
    criteria: dict,
):

    inputs = []
    application_ids = []
    resume_ids = []

    
    for r in resumes:
        resume_ids.append(r.resume_id)
        application_ids.append(r.application_id)

        inputs.append({
            "criteria": json.dumps(criteria),
            "resume_text": r.resume_text,
        })

    logger.info(f"Initiating scoring for Text Formatted  {len(resumes)} resumes with criteria: {criteria.keys()}")
    results = await chain.abatch(
        inputs,
        config={
            "max_concurrency": 5,
            "return_exceptions": True,
        },
    )

    successes: list[ResumeScoreResult] = []
    failures: list[ResumeScoreFailure] = []

    for resume_id, application_id, result in zip(
        resume_ids,
        application_ids,
        results,
    ):

        if isinstance(result, Exception):
            logger.error(
                f"Scoring failed for resume_id={resume_id}: {result}"
            )

            failures.append(
                ResumeScoreFailure(
                    resume_id=resume_id,
                    application_id=application_id,
                    error=str(result),
                )
            )
            continue

        successes.append(
            ResumeScoreResult(
                resume_id=resume_id,
                application_id=application_id,
                score=result,
            )
        )
        
    logger.info(f"Completed scoring for Text Format Resumes {len(resumes)} resumes. Successes: {len(successes)}, Failures: {len(failures)}")

    return successes, failures


# # For synchronous calls (if uploaded resumes number is more than 5) | Will be used by workers 
# async def score_resume_with_text(resumes: list[ResumeDataSchema], criteria: dict):
#     try:
#         inputs = []
#         application_ids = []
#         resume_ids = []
        

#         for resume in resumes:
#             resume_ids.append(resume.resume_id)
#             application_ids.append(resume.application_id)
#             inputs.append({
#                 "criteria": json.dumps(criteria),
#                 "resume_text": resume.resume_text
#             })

#         results = await chain.abatch(
#             inputs,
#             config={
#                 "max_concurrency": 5, # TODO: Can be made dynamic
#                 "return_exceptions": True
#             }
#         )
        
#         print("\n\n\nLLM CALL DONE. Processing results...\n\n\n")
#         # print("Raw results from chain.batch:\n\n\n", results,"\n\n\n\n")

#         response: list[ResumeScoreResult] = []

#         for resume_id,application_id,result in zip(resume_ids,application_ids, results):
#             if isinstance(result, Exception):
#                 logger.error(f"Scoring failed for resume_id={resume_id}: {result}")
#                 continue

#             response.append(ResumeScoreResult(
#                 resume_id=resume_id,
#                 application_id=application_id,
#                 score=result
#             ))

#         return response

#     except Exception:
#         logger.exception("Resume scoring batch failed")
#         raise



















# def score_resume_sync(resumes: list[ResumeDataSchema], criteria: dict):
#     try:
#         # 🔥 MOCKED Gemini output (to save API key)
#         results = data  

#         if len(results) != len(resumes):
#             raise ValueError(
#                 f"Mocked data length ({len(results)}) "
#                 f"does not match resumes length ({len(resumes)})"
#             )

#         response: list[ResumeScoreResult] = []

#         for resume, result in zip(resumes, results):
#             response.append(
#                 ResumeScoreResult(
#                     resume_id=resume.resume_id,
#                     application_id=resume.application_id,
#                     score=result
#                 )
#             )

#         return response

#     except Exception:
#         logger.exception("Resume scoring batch failed")
#         raise
