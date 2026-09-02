import os
from logging import Logger
from arq import Retry
from workers_async.context_manager import job_context
from src.modules.interviews.services.Interview_assessment_service import InterviewAssessmentWorkerService
from workers_async.producers.assessment_task_producer import AnalyzeTranscriptPayload
from src.services.errors.base import DomainError

async def transcript_analyzer_worker(ctx, payload: dict):

    logger: Logger = ctx["logger"]

    job_try = ctx.get("job_try", 1)
    max_tries = 3

    interview_id = payload["interview_id"]
    
    logger.info(f"Processing transcript analysis of {interview_id} | try={job_try}/{max_tries}")

    async with job_context(ctx) as deps:
        assessment_worker_service : InterviewAssessmentWorkerService = deps["interview_assessment_worker_service"]

        try:
            await assessment_worker_service.analyze_interview_transcript(interview_id)

        except Exception as e:
            
            if isinstance(e, DomainError):
                logger.warning(f"Domain error occurred for {interview_id}: {str(e)}")
                return  # do not retry on domain errors as it is a conflict or invalid state
            
                
            logger.exception(f"Transcript analysis failed {interview_id}")

            if job_try < max_tries:
                raise Retry(defer=job_try * 10)  # backoff
            
            
            
           

async def request_panelist_worker(ctx, interview_id: str):

    logger: Logger = ctx["logger"]

    job_try = ctx.get("job_try", 1)
    max_tries = 3
    
    logger.info(f"Requesting Panelist of {interview_id} | try={job_try}/{max_tries}")

    logger.info(f"Starting request_panelist_worker for interview_id: {interview_id}")
    async with job_context(ctx) as deps:
        assessment_worker_service : InterviewAssessmentWorkerService = deps["interview_assessment_worker_service"]

        try:
            await assessment_worker_service.request_interview_assessment_to_panelist(interview_id)
            logger.info(f"Successfully requested panelist assessment for interview_id: {interview_id}")

        except Exception as e:
            
            if isinstance(e, DomainError):
                logger.warning(f"Domain error occurred for {interview_id}: {str(e)}")
                return  # do not retry on domain errors as it is a conflict or invalid state
            
                
            logger.exception(f"Request panelist failed {interview_id}")

            if job_try < max_tries:
                raise Retry(defer=job_try * 10)  # backoff
    logger.info(f"Finished request_panelist_worker for interview_id: {interview_id}")
        

            
           

async def interview_post_processing_worker(ctx, interview_id: str):

    logger: Logger = ctx["logger"]

    job_try = ctx.get("job_try", 1)
    max_tries = 3


    logger.info(f"Post Processing  of {interview_id} | try={job_try}/{max_tries}")

    logger.info(f"Starting interview_post_processing_worker for interview_id: {interview_id}")
    async with job_context(ctx) as deps:
        assessment_worker_service : InterviewAssessmentWorkerService = deps["interview_assessment_worker_service"]

        try:
            await assessment_worker_service.move_interview_ahead(interview_id)
            logger.info(f"Successfully processed interview_post_processing for interview_id: {interview_id}")

        except Exception as e:
            
            if isinstance(e, DomainError):
                logger.warning(f"Domain error occurred for {interview_id}: {str(e.message)}")
                return  # do not retry on domain errors as it is a conflict or invalid state
            
                
            logger.exception(f"Post processing failed {interview_id}")

            if job_try < max_tries:
                raise Retry(defer=job_try * 10)  # backoff
            
        

            
           
            
           

async def interview_extraction_and_post_processsing_worker(ctx, meeting_id: str):

    logger: Logger = ctx["logger"]

    job_try = ctx.get("job_try", 1)
    max_tries = 5


    logger.info(f"Interview Extraction and Post Processing  of Meeting {meeting_id} | try={job_try}/{max_tries}")

    logger.info(f"Starting interview_post_processing_worker for interview_id: {meeting_id}")
    async with job_context(ctx) as deps:
        assessment_worker_service : InterviewAssessmentWorkerService = deps["interview_assessment_worker_service"]

        try:
            await assessment_worker_service.processs_interview_extraction_and_post_processsing(meeting_id)
            logger.info(f"Successfully processed interview_extraction_and_post_processing for meeting_id: {meeting_id}")

        except Exception as e:
            
            if isinstance(e, DomainError):
                logger.warning(f"Domain error occurred for {meeting_id}: {str(e.message)}")
                return  # do not retry on domain errors as it is a conflict or invalid state
            
                
            logger.exception(f"Interview extraction and post processing failed for meeting_id {meeting_id}")

            if job_try < max_tries:
                raise Retry(defer=job_try * 10)  # backoff
            
        

            
           