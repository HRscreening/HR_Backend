import json
import os
import uuid
from typing import List


def write_resume_scoring_jsonl(
    resumes: List,
    job_id: str,
    base_dir: str = "data/batches",
    system_prompt: str | None = None,
) -> str:
    """
    Writes a JSONL file for resume scoring batch inference.
    Returns the file path.
    """

    os.makedirs(base_dir, exist_ok=True)

    file_name = f"resume_scoring_{job_id}_{uuid.uuid4().hex}.jsonl"
    file_path = os.path.join(base_dir, file_name)

    if not system_prompt:
        system_prompt = (
            "You are an ATS system. Score the resume for the given job. "
            "Return a JSON with score (0-100), strengths, weaknesses, and summary."
        )

    with open(file_path, "w", encoding="utf-8") as f:
        for resume in resumes[:2]:
            if not resume.parsed_text:
                continue

            payload = {
                "key": f"resume_{resume.id}_application_{resume.application_id}",
                "request": {
                    "contents": [
                        {
                            "parts": [
                                {
                                    "text": f"{system_prompt}\n\nRESUME:\n{resume.parsed_text}"
                                }
                            ]
                        }
                    ]
                }
            }

            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    return file_path



