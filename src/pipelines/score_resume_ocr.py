from src.pipelines.models import client
from google.genai import types
import requests
from src.schemas.score_schema import ScoreOutputSchema
import base64
from langchain_core.messages import HumanMessage
from src.pipelines.models import image_reader_model
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableLambda
import httpx
from configs.env_config import SUPABASE_PUBLIC_URL
from configs.log_config import get_logger

logger = get_logger("RESUME_OCR_SCORING_PIPELINE")

async def score_img_format_resume_file(resume_url: str,criteria: dict):
  try:
    async with httpx.AsyncClient(timeout=60) as client_http:
        file_url=f"{SUPABASE_PUBLIC_URL}/{resume_url}"
        resp = await client_http.get(file_url)
        image_bytes = resp.content
        mime_type = resp.headers.get(
            "Content-Type",
            "application/octet-stream"
        )
        
    image = types.Part.from_bytes(
        data=image_bytes,
        mime_type=mime_type
    )

    prompt = f"""
            You are an enterprise-grade Applicant Tracking System (ATS) scoring engine.

            Your task is to evaluate the resume strictly according to the rubric criteria provided below.
            You MUST base all judgments ONLY on the content explicitly present in the resume.

            ====================
            RUBRIC CRITERIA (AUTHORITATIVE)
            ====================
            {criteria}


            ====================
            SCORING RULES (STRICT)
            ====================
            - Score each criterion independently on a scale of 0–100.
            - All scores must be numeric.
            - Use BOTH explicit evidence and strong implicit evidence.
            - Penalize criteria only when there is truly no supporting evidence.
            - Do NOT reward speculation beyond resume content.


            ====================
            CANDIDATE INFO RULE (CRITICAL)
            ====================
            - If you are NOT 100% certain that a field is explicitly labeled in the resume,
              you MUST return null.
            - NEVER return placeholder values.


            ====================
            BREAKDOWN STRUCTURE RULE (CRITICAL)
            ====================
            - The breakdown JSON structure MUST exactly match the rubric structure.
            - Use EXACT same criterion keys as provided in the rubric.
            - Do NOT add or remove criteria.
            - If a criterion has no sub-criteria, return an EMPTY OBJECT {{}}.
            - NEVER return null for sub_criteria.
            - sub_criteria values must be numeric scores only.


            ====================
            REASON & EVIDENCE RULE (VERY IMPORTANT)
            ====================
            For EACH criterion:

            - "score" must be a number between 0 and 100.
            - "reason" must briefly justify the score in 1–3 factual sentences.
            - "evidence" must:
                - Include AT MOST 2 snippets.
                - Each snippet must be ≤ 120 characters.
                - Be near-verbatim resume excerpts (light trimming allowed).
                - Not repeat across multiple criteria.
                - Be an EMPTY ARRAY [] if no supporting evidence exists.

            IMPORTANT:
            - "reason" explains the evaluation.
            - "evidence" contains direct resume excerpts.
            - Do NOT merge reason and evidence.


            ====================
            AI ANALYSIS SUMMARY
            ====================
            - Provide a qualitative review of the resume.
            - Do NOT reference scores, rubric names, criteria names, or evidence.
            - Use ONLY information present in the resume.
            - Summarize strengths and weaknesses factually and concisely.
            - Do NOT repeat evidence text verbatim.

            Structure inside JSON:

            ai_analysis: {{
              "good_points": ["short bullet sentence", "short bullet sentence"],
              "bad_points": ["short bullet sentence"]
            }}

            If no weaknesses exist, return an empty list for "bad_points".


            ====================
            OUTPUT REQUIREMENTS
            ====================
            - Return ONLY valid JSON.
            - Follow the schema EXACTLY.
            - Every required field must be present.
            - Do NOT include explanations outside JSON.
            - Do NOT wrap JSON in markdown.


            ====================
            FAILURE RULE
            ====================
            If the resume is empty, corrupted, or irrelevant:
            - Set all scores ≤ 10.
            - Set ai_confidence ≤ 0.2.
            - Provide minimal analysis.
            """


    logger.info(f"Scoring resume at URL: {resume_url} ")
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=[prompt, image],
        config={
        "response_mime_type": "application/json",
        "response_json_schema": ScoreOutputSchema.model_json_schema(),
    }
    )

    logger.info(f"Received scoring response for resume at URL: {resume_url} ")
    
    return response.parsed
  
  except Exception as e:
    logger.error(f"Failed to score resume at URL: {resume_url} with error: {e}")




# structured_llm = image_reader_model.with_structured_output(ScoreOutputSchema)


# def build_message(input_data):
#     resume_url = input_data["resume_url"]
#     criteria = input_data["criteria"]

#     response = requests.get(resume_url)
#     image_bytes = response.content
#     mime_type = response.headers.get("Content-Type", "image/jpeg")

#     image_base64 = base64.b64encode(image_bytes).decode()

#     prompt = f"""
#                 You are an enterprise-grade Applicant Tracking System (ATS) scoring engine.

#                 Your task is to evaluate the resume strictly according to the rubric criteria provided below.
#                 You MUST base all judgments ONLY on the content explicitly present in the resume.

#                 ====================
#                 RUBRIC CRITERIA (AUTHORITATIVE)
#                 ====================
#                 {criteria}


#                 ====================
#                 SCORING RULES (STRICT)
#                 ====================
#                 - Score each criterion independently on a scale of 0–100.
#                 - All scores must be numeric.
#                 - Use BOTH explicit evidence and strong implicit evidence.
#                 - Penalize criteria only when there is truly no supporting evidence.
#                 - Do NOT reward speculation beyond resume content.


#                 ====================
#                 CANDIDATE INFO RULE (CRITICAL)
#                 ====================
#                 - If you are NOT 100% certain that a field is explicitly labeled in the resume,
#                   you MUST return null.
#                 - NEVER return placeholder values.


#                 ====================
#                 BREAKDOWN STRUCTURE RULE (CRITICAL)
#                 ====================
#                 - The breakdown JSON structure MUST exactly match the rubric structure.
#                 - Use EXACT same criterion keys as provided in the rubric.
#                 - Do NOT add or remove criteria.
#                 - If a criterion has no sub-criteria, return an EMPTY OBJECT {{}}.
#                 - NEVER return null for sub_criteria.
#                 - sub_criteria values must be numeric scores only.


#                 ====================
#                 REASON & EVIDENCE RULE (VERY IMPORTANT)
#                 ====================
#                 For EACH criterion:

#                 - "score" must be a number between 0 and 100.
#                 - "reason" must briefly justify the score in 1–3 factual sentences.
#                 - "evidence" must:
#                     - Include AT MOST 2 snippets.
#                     - Each snippet must be ≤ 120 characters.
#                     - Be near-verbatim resume excerpts (light trimming allowed).
#                     - Not repeat across multiple criteria.
#                     - Be an EMPTY ARRAY [] if no supporting evidence exists.

#                 IMPORTANT:
#                 - "reason" explains the evaluation.
#                 - "evidence" contains direct resume excerpts.
#                 - Do NOT merge reason and evidence.


#                 ====================
#                 AI ANALYSIS SUMMARY
#                 ====================
#                 - Provide a qualitative review of the resume.
#                 - Do NOT reference scores, rubric names, criteria names, or evidence.
#                 - Use ONLY information present in the resume.
#                 - Summarize strengths and weaknesses factually and concisely.
#                 - Do NOT repeat evidence text verbatim.

#                 Structure inside JSON:

#                 ai_analysis: {{
#                   "good_points": ["short bullet sentence", "short bullet sentence"],
#                   "bad_points": ["short bullet sentence"]
#                 }}

#                 If no weaknesses exist, return an empty list for "bad_points".


#                 ====================
#                 OUTPUT REQUIREMENTS
#                 ====================
#                 - Return ONLY valid JSON.
#                 - Follow the schema EXACTLY.
#                 - Every required field must be present.
#                 - Do NOT include explanations outside JSON.
#                 - Do NOT wrap JSON in markdown.


#                 ====================
#                 FAILURE RULE
#                 ====================
#                 If the resume is empty, corrupted, or irrelevant:
#                 - Set all scores ≤ 10.
#                 - Set ai_confidence ≤ 0.2.
#                 - Provide minimal analysis.
#                 """


#     message =  HumanMessage(
#         content=[
#             {"type": "text", "text": prompt},
#             {
#                 "type": "image_url",
#                 "image_url": {
#                     "url": f"data:{mime_type};base64,{image_base64}"
#                 },
#             },
#         ]
#     )
    
#     return [message]
    

# output_parser = PydanticOutputParser(pydantic_object=ScoreOutputSchema)
# structured_model = image_reader_model.with_structured_output(ScoreOutputSchema)
   
# image_chain = (
#   RunnableLambda(build_message)
#   | structured_model
# )


# # Async for api testing
# async def score_image_resumes_async(resume_urls: list[str], criteria: dict):

#     inputs = [
#         {"resume_url": url, "criteria": criteria}
#         for url in resume_urls
#     ]

#     results = await image_chain.abatch(
#         inputs,
#         config={
#             "max_concurrency": 5,
#             "return_exceptions": True
#         }
#     )

#     return results



# # # For workers
# # async def score_image_resumes_async(resume_urls: list[str], criteria: dict):

# #     inputs = [
# #         {"resume_url": url, "criteria": criteria}
# #         for url in resume_urls
# #     ]

# #     results = image_chain.batch(
# #         inputs,
# #         config={
# #             "max_concurrency": 5,
# #             "return_exceptions": True
# #         }
# #     )

# #     return results
