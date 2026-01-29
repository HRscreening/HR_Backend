from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from pipelines.models import llm
from schemas.user_schemas import RubricSchema



# Define the parser
output_parser = PydanticOutputParser(pydantic_object=RubricSchema)

# Create format instructions from the parser
format_instructions = output_parser.get_format_instructions()

# Updated strict prompt
prompt = PromptTemplate(
    template="""
From the job description below, generate a rubric.

Rules:
- threshold_score must be an integer >= 0
- criteria is an object where:
  - keys are skill names
  - each value has:
    - score: integer >= 0
    - sub_criteria: object<string, integer> (optional)
- If sub_criteria exists, score MUST equal the sum of sub_criteria values
- Use only integers (no strings)
- Use concise, relevant skill names only
- Output ONLY valid JSON

Job description:
{jd_text}

{format_instructions}
""",
    input_variables=["jd_text"],
    partial_variables={"format_instructions": format_instructions}
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
