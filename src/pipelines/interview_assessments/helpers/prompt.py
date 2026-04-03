import json

def build_chunk_prompt(chunk: str, job_criterias: dict, assessment_parameters: list[str]):
    return f"""
You are an expert technical interviewer evaluating a candidate.

You must evaluate the candidate STRICTLY based on:

1. Job Requirements:
{json.dumps(job_criterias, indent=2)}

2. Assessment Criteria:
{assessment_parameters}

---

Analyze the following interview transcript chunk and return STRICT JSON:

{{
  "criteria_evaluation": [
    {{
      "criteria": "<criteria name>",
      "score": 1-5,
      "reason": "specific justification from transcript"
    }}
  ],
  "skills_detected": ["..."],
  "strengths": ["..."],
  "weaknesses": ["..."],
  "overall_chunk_score": 1-5,
  "summary": "short, specific summary"
}}

---

Rules:
- Scores must be based ONLY on evidence in this chunk
- Do NOT hallucinate skills
- Keep reasons specific (quote or refer to behavior)
- Be strict (this is a real interview evaluation)

---

Transcript:
{chunk}
"""




def build_final_prompt(chunk_analysis, assessment_parameters):
    return f"""
You are a senior technical interviewer.

You are given multiple chunk-level evaluations of a candidate interview.

Your task is to produce a FINAL evaluation.

---

Assessment Criteria:
{assessment_parameters}

---

Chunk Evaluations:
{json.dumps(chunk_analysis, indent=2)}

---

Return STRICT JSON in this format:

{{
  "criteria_ratings": [
    {{
      "criteria": "<criteria name>",
      "rating": 1-5,
      "comment": "clear reasoning based on entire interview"
    }}
  ],
  "interview_summary": "concise summary of candidate performance",
  "final_recommendation": "Hire or No Hire",
  "justification": "clear reasoning for decision"
}}

---

Rules:
- Aggregate insights across ALL chunks
- Do NOT repeat chunk summaries
- Be decisive (no vague language)
- Ratings must reflect overall performance, not just one chunk
- Comments must be specific and evidence-based
"""