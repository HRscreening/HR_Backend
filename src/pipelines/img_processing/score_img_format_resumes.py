import asyncio
import httpx
from src.schemas.score_schemas import ResumeDataSchemaURL,ResumeScoreFailure,ResumeScoreResult
from src.pipelines.img_processing.score_resume_ocr import score_img_format_resume_file
from configs.log_config import get_logger

logger = get_logger("score_img_format_resumes")

async def score_resume_with_url(
    resumes: list[ResumeDataSchemaURL],
    criteria: dict,
    max_concurrency: int = 5,
):

    semaphore = asyncio.Semaphore(max_concurrency)

    successes: list[ResumeScoreResult] = []
    failures: list[ResumeScoreFailure] = []

    async with httpx.AsyncClient(timeout=90) as http_client:

        async def worker(r: ResumeDataSchemaURL):
            async with semaphore:
                try:
                    result = await score_img_format_resume_file(
                        resume_url=r.resume_url,
                        criteria=criteria
                    )

                    return (
                        r.resume_id,
                        r.application_id,
                        result,
                        None,
                    )

                except Exception as e:
                    return (
                        r.resume_id,
                        r.application_id,
                        None,
                        e,
                    )

        logger.info(f"Starting scoring for {len(resumes)} resumes with max concurrency of {max_concurrency}.")
        tasks = [worker(r) for r in resumes]

        for coro in asyncio.as_completed(tasks):
            resume_id, application_id, result, error = await coro
            
            

            if error or result is None:  # ✅ treat None result as failure too
                logger.error(f"Scoring failed for resume_id={resume_id}: {error or 'result was None'}")
                failures.append(
                    ResumeScoreFailure(
                        resume_id=resume_id,
                        application_id=application_id,
                        error=str(error) if error else "LLM returned no result",
                    )
                )
                continue

            successes.append(
                ResumeScoreResult(
                    resume_id=resume_id,
                    application_id=application_id,
                    score=result,
                )
            )
            
    logger.info(f"Completed scoring. Successes: {len(successes)}, Failures: {len(failures)}")
    return successes, failures
