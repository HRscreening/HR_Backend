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


# Enterprise-grade rubric prompt (V2): deterministic, requirement_level, strict grouping
RUBRIC_FROM_JD_PROMPT_V2 = PromptTemplate(
    template="""
You are an enterprise-grade ATS rubric designer.

Your task is to generate a stable, scoring-ready rubric from a Job Description (JD) and Job Context. The rubric must support consistent resume evaluation, ranking stability, and explainable scoring.

This is a production system. Precision, structural stability, and determinism are mandatory.

CORE DESIGN PHILOSOPHY

Criteria = Scoring Dimensions
Each criterion represents a high-level measurable capability (e.g., ML Engineering Depth, Client Engagement, Cloud Deployment).

Sub-criteria = Atomic Evidence Signals
Sub-criteria represent single, atomic, resume-verifiable requirements inside a criterion.

No vague personality traits.
Do NOT include subjective or unscorable traits such as:

Passionate

Hard-working

Innovative thinker

Self-starter
Only include behaviors or skills that can be evidenced in resumes.

No duplication.
Do NOT repeat the same requirement across multiple sections.
Consolidate related requirements under one logical criterion using sub-criteria.

No hallucination.
Use ONLY information explicitly present in:

JD text

Job Context
Do NOT infer industry-standard requirements that are not written.

OUTPUT STRUCTURE

Return a rubric containing:

job_id

job_title

rubric_id

version (set to 1)

threshold_score (number)

source ("combined")

criteria

domain ("other")

domain_confidence (0.5)

criteria contains:

sections (array)

schema_version (set to 1)

Each section must contain:

key (snake_case)

label (Title Case)

importance (integer 1–10, see SECTION IMPORTANCE CALIBRATION below)

criteria (array)

Each criterion must contain:

name (snake_case, unique within section)

display_name (Title Case)

importance (integer 1–10)

requirement_level ("must" | "should" | "nice")

priority (integer, sequential starting at 1)

value (string or null)

value_type ("none")

sub_criteria (array; use [] if none)

Each sub_criterion must contain:

name (snake_case)

display_name (Title Case)

importance (integer 1–5)

value (string or null)

value_type ("none")

Arrays must NEVER be null. Use [].

SECTION IMPORTANCE CALIBRATION

Each section receives an importance score (1-10) reflecting its overall weight toward the final candidate score.
- required_qualifications: ALWAYS 9-10 (mandatory constraints are dealbreakers)
- technical_skills / core_skills: 7-9 for roles where domain skills are central
- experience: 6-8 depending on how much the JD emphasizes seniority
- tools_platforms: 4-6 (supportive but rarely dealbreaker)
- soft_skills: 3-5 (hard to verify from resumes)
- preferred_qualifications: 3-5 (nice-to-have by definition)
- certifications: 3-6 (depends on whether JD lists them as required or preferred)

Do NOT assign identical importance to all sections unless the JD truly treats them equally.
Section importance drives the weighted scoring formula, so calibrate carefully based on the JD.

SECTION ORDER RULES

If tech role, use this section order (only include relevant ones):

required_qualifications

technical_skills

experience

tools_platforms

domain_knowledge

soft_skills

certifications

preferred_qualifications

If non-tech role:

required_qualifications

core_skills

experience

soft_skills

preferred_qualifications

Do NOT create unnecessary or empty sections.

Do NOT create sections containing only one minor criterion.
Combine logically related items when appropriate.

REQUIRED QUALIFICATIONS RULE

If JD contains explicit constraints, they MUST appear under required_qualifications:

Examples:

Years of experience (e.g., "7+ years")

Degree requirement

Location requirement

Work authorization

Clearance

Working hours / timezone

Travel %

Salary constraints (if candidate-side)

Numeric minimum experience requirements MUST appear in required_qualifications even if there is a separate experience section.

CRITERIA DESIGN RULES

Each criterion must represent a coherent, measurable capability dimension.

Do NOT create overly broad criteria mixing unrelated skills.

Do NOT create excessively narrow criteria for trivial single skills.

Use sub-criteria only when multiple atomic requirements belong under one conceptual capability.

Each sub-criterion must represent ONE atomic requirement.

Do NOT use sub-criteria for:

Binary constraints

Numeric thresholds

Standalone simple constraints

IMPORTANCE CALIBRATION

For each criterion (1–10):

10 = Explicitly mandatory / dealbreaker
8–9 = Strongly emphasized core requirement
6–7 = Important but not explicitly mandatory
4–5 = Good to have
1–3 = Minor bonus

For each sub-criterion (1–5):

5 = Most critical signal in that group
3 = Standard expectation
1 = Minor detail

CONSISTENCY RULES:

If requirement_level = "must" → importance MUST be ≥ 8

If requirement_level = "nice" → importance MUST be ≤ 5

Sub-criteria importance must vary based on JD emphasis.

Do NOT assign identical importance to all sub-criteria unless JD clearly treats them equally.

PRIORITY RULE

Within each section:

Sort criteria by importance (descending)

Assign priority starting at 1

Increment by 1 without gaps

Priority must strictly reflect descending importance

VALUE FIELD RULES

Use value ONLY when an explicit strict constraint exists.

Examples:

"7+ years"

"Bachelor's in Computer Science"

"Bangalore (onsite)"

"8am–5pm EST"

"30% travel"

Value must be concise.
Do NOT include descriptive sentences.
If no strict constraint exists → set value = null.

Always set value_type = "none".

CONSTRAINT EXTRACTION RULE

Extract ALL explicit constraints:

Years of experience

Degree level

Location

Work authorization

Clearance

Travel %

Timezone / working hours

Team size (if explicitly stated)

Reporting structure (if explicitly stated)

Do NOT infer unstated constraints.

THRESHOLD SCORE RULE

Set threshold_score based on seniority:

Entry-level (0–3 years) → 55–60
Mid-level (3–7 years) → 60–65
Senior (7+ years) → 65–70
Leadership / managerial → 70–75

If unclear → default 60.

ANTI-HALLUCINATION RULE

Use ONLY JD text and Job Context.

Do NOT invent requirements.

Do NOT add common tools unless explicitly written.

Do NOT expand scope beyond JD.

STRICT OUTPUT RULES

Return ONLY valid JSON.

No markdown.

No explanations.

No comments.

All numeric fields must be numbers.

Arrays must never be null.

Follow OUTPUT SCHEMA exactly.

JD FORMAT HANDLING

Job descriptions come in many formats. Adapt your parsing accordingly:

- BULLET-LIST JD: Each bullet is typically one requirement. Map bullets to criteria/sub-criteria directly.
- NARRATIVE/PARAGRAPH JD: Extract individual requirements from prose. Split compound sentences into separate criteria.
- MINIMAL JD (< 5 requirements): Create fewer sections. Do NOT pad with invented requirements. A 3-criterion rubric is perfectly valid.
- STRUCTURED JD (with clear headings like "Requirements", "Preferred"): Use headings as section boundaries.

RUBRIC COMPLETENESS

Every rubric MUST cover at minimum:
- At least one skills-related section (technical_skills, core_skills, or equivalent)
- At least one experience-related criterion (years, domain experience, or equivalent)

If the JD lacks one of these entirely, create a minimal criterion with importance=3 and requirement_level="nice".

INPUTS

JOB DESCRIPTION
{jd_text}

JOB CONTEXT
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
