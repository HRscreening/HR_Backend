from typing import Any, List
# Makes a parallel call for resumes 

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from src.pipelines.models import _tag_generator_model
from configs.log_config import get_logger
from pydantic import BaseModel


class OutputSchema(BaseModel):
    assessment__tags: List[str]

logger = get_logger("TagGeneratorPipeline")

output_parser = PydanticOutputParser(pydantic_object=OutputSchema)

format_instructions = output_parser.get_format_instructions()

prompt = PromptTemplate(
    template="""
You are an expert interviewer designing a structured evaluation form.

Your task is to generate HIGH-LEVEL interview assessment tags **specific to the interview round**.

====================
INPUTS
====================
Job Criteria:
{criteria}

Interview Round Title:
{round_title}

====================
CRITICAL INSTRUCTION — READ FIRST
====================
The Interview Round Title is your PRIMARY filter.
You MUST generate tags that are **only relevant to what is evaluated in this specific round**.

- A "Technical Round" should produce tags like: Problem Solving, Code Quality, System Design Thinking
- A "HR Round" or "Personal Interview" should produce tags like: Communication Skills, Culture Fit, Motivation & Drive, Self-Awareness
- A "Managerial Round" should produce tags like: Leadership Potential, Stakeholder Communication, Prioritization Thinking

If a criteria item does NOT belong to this round type → IGNORE IT COMPLETELY.

====================
GOAL
====================
Generate a SMALL set of BROAD, round-appropriate evaluation tags.

These tags will be used to build an interview feedback form where each tag gets:
  - A rating (1–10)
  - A reasoning/comment

====================
STRICT RULES
====================

1. MAX TAGS: Generate AT MOST 4-5 tags.

2. ROUND-FIRST THINKING:
   - Ask yourself: "What does an interviewer actually evaluate in a {round_title}?"
   - Start from the round type, THEN check if criteria adds anything new.
   - Do NOT copy all criteria blindly.

3. TAG TYPE:
   - Tags MUST be broad and evaluative dimensions, NOT specific skills or tools.

4. AVOID:
   - Specific technologies (e.g., React, SQL, AWS, Python)
   - Narrow technical sub-skills
   - Redundant or overlapping tags
   - Tags that belong to a DIFFERENT round type

5. QUALITY:
   - Tags must be clear, professional, and reusable across candidates.
   - Each tag should be 2–4 words max.

====================
ROUND-TAG EXAMPLES
====================

Technical Round:
  ✅ Problem Solving, Code Quality, System Design Thinking, Debugging Approach, Analytical Thinking
  ❌ Communication Style, Culture Fit, Emotional Intelligence

Personal / HR Interview:
  ✅ Communication Skills, Culture Fit, Motivation & Drive, Self-Awareness, Conflict Resolution
  ❌ Code Quality, System Design, Algorithmic Thinking

====================
OUTPUT REQUIREMENTS
====================

Return ONLY valid JSON.

SCHEMA:
{format_instructions}
""",
    input_variables=["criteria", "round_title"],
    partial_variables={
        "format_instructions": output_parser.get_format_instructions()
    }
)



chain = prompt | _tag_generator_model | output_parser





# For API calls (if uploaded resumes number is less than 5) | Not strictly 5 but idle for small number of resumes
async def create_assessment_tags(criteria: dict, round_title)-> List[str]:
    """Generate assessment tags based on the provided criterias and job title."""
    try:
       
        result = await chain.ainvoke(
            input={
                "criteria": criteria,
                "round_title": round_title
            }
        )

        return result.assessment__tags

    except Exception as e:
        
        logger.exception(f"Resume scoring batch failed with error: {str(e)}")
        raise

