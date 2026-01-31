from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from pipelines.models import llm
from schemas.user_schemas import ExtractedJDSchema
from configs.log_config import get_logger

logger = get_logger(__name__)

# Define the parser
output_parser = PydanticOutputParser(pydantic_object=ExtractedJDSchema)

# Create format instructions from the parser
format_instructions = output_parser.get_format_instructions()
prompt = PromptTemplate(
    template="""
You are given a job description. Your task is to extract ALL possible structured information that fits EXACTLY into the schema described below.

Your output MUST be valid JSON and MUST conform strictly to the schema.
Do NOT add extra fields.
Do NOT include explanations or comments.
Do NOT output anything other than JSON.

========================
SCHEMA TO FOLLOW
========================

Top-level JSON object must have EXACTLY these keys:

1. job_data
2. threshold_score
3. mandatory_criteria
4. screening_criteria

--------------------------------
job_data (object)
--------------------------------
Extract the following:
- title: Job title
- description: Job description summary (maximum 30 words)
- location: Job location if mentioned, otherwise null
- salary: Salary or compensation if mentioned, otherwise null
- target_headcount: Integer headcount (default to 1 if not mentioned)
- metadata: Object of structured key-value info NOT suitable as criteria
  (e.g. employment_type, shift, notice_period). If none, use null.

--------------------------------
threshold_score (integer)
--------------------------------
- Integer >= 0
- Represents minimum score required to qualify
- Infer a reasonable value based on strictness of requirements

--------------------------------
mandatory_criteria (object)
--------------------------------
--------------------------------
screening_criteria (object)
--------------------------------

Each of these is an object where:
- keys are concise, normalized skill names (lowercase, snake_case)
- values follow the Criterion schema below

--------------------------------
Criterion schema
--------------------------------
Each criterion object may contain:

- weight (integer >= 0) [REQUIRED]
- Sum of all criteria weights(excluding weights of their sub-criteria) in mandatory_criteria must be 100, similarly for screening_criteria
- value (a text that should be required for the skill, eg: for cgpa skill , value can be greater than 7) [OPTIONAL]
- sub_criteria (object) [OPTIONAL]

Rules:
- Use value ONLY if the skill is objectively measurable
  (e.g. years_of_experience, cgpa, notice_period_days)
- Use null for value if skill is qualitative (e.g. python, leadership)

--------------------------------
Sub-criteria rules
--------------------------------
- sub-criteria CANNOT have their own sub-criterias (i.e. no nested sub-criteria)
- sub_criteria is an object where:
  - keys are sub-skill names
  - values are Criterion objects (weight REQUIRED, value OPTIONAL)
- Use sub_criteria ONLY when a skill naturally decomposes
  (e.g. python → fastapi, django, machine_learning)
- If sub_criteria exists:
  - Sub-criteria weights must sum to 100% (currently: 20.0%)
- value can be text like anything that can be used to measure the sub-skill

--------------------------------
Classification rules
--------------------------------
- Mandatory criteria = must-have requirements
- Screening criteria = preferred / nice-to-have requirements

--------------------------------
General rules (STRICT)
--------------------------------
- Use ONLY integers or null (no strings for numbers)
- Use ONLY information present or strongly implied in the JD
- Do NOT hallucinate skills
- Extract EVERYTHING that reasonably fits the schema
- If a field cannot be extracted, use null (do NOT omit keys)

========================
JOB DESCRIPTION
========================
{jd_text}

========================
OUTPUT FORMAT
========================
{format_instructions}
""",
    input_variables=["jd_text"],
    partial_variables={"format_instructions": format_instructions},
)



# Create chain
chain = prompt | llm | output_parser



async def generate_rubric_from_jd(jd_text: str):
    """
    Generates a structured rubric JSON from a job description.
    """
    try:
        result = await chain.ainvoke({"jd_text": jd_text})
        return result
    except Exception as e:
        print("LLM output failed schema validation.", e)
        raise
