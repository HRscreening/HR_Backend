"""
Rubric Generation Prompt — single-call JD + job_data → weighted rubric JSON.

This prompt is designed to:
- Group requirements into one or more rubric sections (each with key and label)
- Each section contains criteria (groups) with optional sub_criteria
- Assign weights from JD language and ordering
- Include constraints (location/work-auth/degree/etc) from JD and job_data when relevant
- Return strict JSON matching the rubric schema (domain, domain_confidence, threshold_score, sections; value optional, value_type always "none")
"""

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate

from src.schemas.rubric_schemas import ExtractedJDSchemaV2, PipelineRubricOutput


rubric_parser = PydanticOutputParser(pydantic_object=ExtractedJDSchemaV2)
fixer_parser = PydanticOutputParser(pydantic_object=PipelineRubricOutput)

RUBRIC_FROM_JD_PROMPT = PromptTemplate(
    template="""
You are an enterprise ATS rubric designer.

GOAL
Analyse this JD and build a rubric that will be used to process resumes and build a solid ATS scoring system.

WHAT TO BUILD
Return a rubric with one or more sections. Each section has:
- key: snake_case identifier (e.g. required_skills, preferred_skills, experience, education)
- label: human-readable title (e.g. "Required Skills", "Preferred Qualifications")
- criteria: list of criterion groups

Group requirements in a way that fits the JD (e.g. required vs preferred, or by domain: technical_skills, experience, education, soft_skills, certifications). Each criterion MAY include sub_criteria (the individual requirements within that group).

GROUP / DOMAIN CONTEXT
- If this is a tech profile: group requirements into Technical Skills, Experience, Education, Tools & Platforms, Domain Knowledge, Soft Skills, Certifications, etc.
- If this is a non-tech profile: group into relevant categories (e.g., Sales Skills, Domain Experience, Communication, Leadership, etc.)
- Think of groups as rubric dimensions — the sub_criteria are the specific line items the LLM will later evaluate resumes against.

IMPORTANCE SCORING (CRITICAL — this drives ATS scoring)
- Assign `importance` (1–10 integer) to EACH criterion in a section.
  - 10: Critical, dealbreaker
  - 7-9: Highly Expected
  - 4-6: Good to Have
  - 1-3: Minor Bonus
- If a criterion has sub_criteria, assign `importance` (1–5 integer) to EACH sub_criterion.
  - 5: Most important detail
  - 3: Standard expectation
  - 1: Nice extra detail
- Do NOT worry about making any weights sum to 100. Just assign the raw importance score based on JD wording and ordering.
- Requirements listed EARLIER in the JD typically get HIGHER importance.
- Put required/must-have items in a section (e.g. key "required_skills"); put preferred items in another (e.g. "preferred_skills").

CONSTRAINTS (when JD or Job Context mentions them)
- Use `value` (string) only when a criterion/sub-criterion has a concrete constraint.
- The `value` MUST be highly concise (e.g., "5+ years", not "more than 5 years of experience").
- Include constraints for: Location, Work authorization, Security clearance, Minimum education (degree), Salary requirement on the candidate side.

VALUE FIELD (OPTIONAL)
- Use `value` (string) only when a criterion/sub-criterion has a concrete constraint to capture:
  - Years of experience → value="5+ years"
  - Degree requirement → value="Bachelor's in Computer Science"
  - Location constraint → value="Bangalore (onsite)"
- For pure skill groups without a specific threshold, omit value or set value=null.
- Always set value_type="none" (no other types).

NAMING (IMPORTANT)
- Use snake_case for `name` fields (unique within a section).
- Use human-friendly Title Case for `display_name`.
- `priority` starts at 1 and increases by 1 in descending importance order.

DOMAIN (SIMPLIFIED)
- Set domain to "other" and domain_confidence to 0.5 (do NOT try to classify domain).

THRESHOLD (DEFAULT)
Set threshold_score to 60 unless JD explicitly indicates a very senior/strict role; then set 65–75.

RULES (NON-NEGOTIABLE)
- Use ONLY the JD content and Job Context below. Do NOT hallucinate.
- Return ONLY valid JSON. No markdown. No explanations. No comments.
- All numeric fields must be numbers (not strings): domain_confidence, threshold_score, weight, priority.
- Arrays must never be null. Use [] when empty.
- If you cannot extract something, omit it or use null only where schema allows.

JOB DESCRIPTION
{jd_text}

JOB CONTEXT (from user-entered form data — use this to cross-check location, salary, headcount, etc.)
{job_context}

OUTPUT SCHEMA (MUST MATCH)
{format_instructions}
""",
    input_variables=["jd_text", "job_context"],
    partial_variables={"format_instructions": rubric_parser.get_format_instructions()},
)


RUBRIC_FIXER_PROMPT = PromptTemplate(
    template="""
You are an ATS rubric editor.

TASK
Given a JD and an initial rubric JSON, rewrite the rubric to be cleaner and non-duplicative.

RULES (KEEP IT SIMPLE)
- Do NOT invent new requirements. Only reorganize/merge what is already present and what is explicitly supported by the JD.
- Keep differences as sub_criteria.
  Example: "Python" + "Functional programming" → one criterion like "Programming" with sub_criteria ["Python", "Functional programming"].
- Keep the rubric compact (avoid repeating the same concept in multiple criteria).
- If you merge two criteria, use the higher importance score of the two.
- Always set value_type="none". value may be a highly concise string constraint (e.g., "5+ years") or null.

JOB DESCRIPTION
{jd_text}

INITIAL RUBRIC JSON
{rubric_json}

OUTPUT (MUST MATCH)
{format_instructions}
""",
    input_variables=["jd_text", "rubric_json"],
    partial_variables={"format_instructions": fixer_parser.get_format_instructions()},
)
