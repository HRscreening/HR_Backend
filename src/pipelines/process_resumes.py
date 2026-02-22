# For resume processing, we will use Gemini batch inference to score resumes in bulk.

import time
import json
from google import genai
from google.genai import types
from src.pipelines.models import scoring_model

def run_gemini_batch(
    jsonl_file_path: str,
    model: str = "models/gemini-2.5-flash-lite",
    display_name: str = "batch-job"
):
    """
    Uploads a JSONL batch request file, runs Gemini batch inference,
    and returns parsed responses.
    """

    client = genai.Client()

    # 1. Upload JSONL file
    uploaded_file = client.files.upload(
        file=jsonl_file_path,
        config=types.UploadFileConfig(
            display_name=display_name,
            mime_type="jsonl"
        )
    )

    # 2. Create batch job
    batch_job = client.batches.create(
        model=model,
        src=uploaded_file.name,
        config={"display_name": display_name}
    )
    
    print(f"Started batch job: {batch_job.name}",f"Batch ID: {str(batch_job)}")

    return batch_job

    # # 3. Poll job status
    # while True:
    #     job = client.batches.get(batch_job.name)

    #     if job.state in ("SUCCEEDED", "FAILED", "CANCELLED"):
    #         break

    #     time.sleep(5)

    # if job.state != "SUCCEEDED":
    #     raise RuntimeError(f"Batch job failed with state: {job.state}")

    # # 4. Download output file
    # output_file_name = job.output_file
    # output_file = client.files.get(output_file_name)

    # content = client.files.download(output_file.name).decode("utf-8")

    # # 5. Parse JSONL responses
    # responses = []
    # for line in content.splitlines():
    #     responses.append(json.loads(line))

    # return responses



async def score_resume(prompt, resume_text: str, model: str = "models/gemini-2.5-flash-lite"):
    """
    Scores a single resume using the provided prompt and Gemini model.
    """

    client = genai.Client()

    messages = [
        prompt,
        types.UserMessage(content=resume_text)
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.0,
        max_output_tokens=1500,
    )

    return response.choices[0].message.content