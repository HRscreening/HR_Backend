"""
Prompt templates for the JD Builder AI pipeline.
"""

JD_FROM_PROMPT = """You are an expert technical recruiter. A recruiter has described a role in their own words below.
Your job is to turn that description into a professional, well-structured Job Description in Markdown format.

## INSTRUCTIONS
- Write clear sections: About the Role, Key Responsibilities, Required Qualifications, Nice-to-Have, What We Offer
- Be specific — avoid vague filler like "passionate", "rockstar", "ninja"
- Infer missing details intelligently from context (e.g. if they mention Python, infer a tech role)
- If salary / location are not mentioned, omit those sections
- Keep between 400–700 words
- Return a suggested job title, and extract location and salary if mentioned

## RECRUITER'S DESCRIPTION

{prompt}

---

Write the complete Job Description now. Return only the requested JSON structure."""

JD_GENERATION_PROMPT = """You are an expert technical recruiter and HR professional.
Your task is to write a professional, compelling Job Description based on the structured information provided below.

## INSTRUCTIONS
- Write a well-structured JD in Markdown format
- Use clear section headings: About the Role, Key Responsibilities, Required Qualifications, Nice-to-Have, What We Offer, About the Company (if company description provided)
- Be specific and concrete — avoid vague filler phrases like "passionate", "rockstar", "ninja"
- For Required Qualifications, clearly distinguish must-have from preferred
- If salary range is not provided, omit the compensation section
- Keep the JD between 400-700 words in the content field
- The title must exactly match the role_title input
- Extract location from location input, or use null if not provided
- Extract salary_range from salary input, or use null if not provided

## JOB INFORMATION

**Role Title:** {role_title}
**Department:** {department}
**Number of Openings:** {openings}
**Experience Level:** {experience_level}
**Years of Experience:** {experience_range}
**Employment Type:** {employment_type}
**Work Mode:** {work_mode}
**Location:** {location}
**Salary Range:** {salary_range}

**Key Responsibilities:**
{responsibilities}

**Required Skills:**
{skills_required}

**Nice-to-Have Skills:**
{skills_nice_to_have}

**Education / Degree Required:**
{education}

**Certifications:**
{certifications}

**About the Company / Team:**
{company_description}

**What Makes This Role Exciting:**
{role_highlights}

**Benefits & Perks:**
{benefits}

**Special Requirements:**
{special_requirements}

---

Write the complete Job Description now. Return only the requested JSON structure.
"""
