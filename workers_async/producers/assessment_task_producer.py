from dataclasses import dataclass
from datetime import timedelta, datetime, timezone
from typing import Optional
from uuid import UUID, uuid4 as uuid

from arq.connections import ArqRedis
from arq.jobs import Job

from configs.log_config import get_logger

# -------------------- CONFIGS --------------------

@dataclass
class JobConfig:
    queue_name: str
    worker_func: str


@dataclass
class AnalyzeTranscriptPayload:
    interview_id: str | UUID
    
    
    
    def to_dict(self):
        return {
            "interview_id": str(self.interview_id)
        }


# -------------------- PRODUCER --------------------

class AssessmentTaskProducer:
    """
    Async producer for Assessment tasks using ARQ.
    """

    def __init__(self, redis: ArqRedis):
        self.redis = redis
        self.default_queue = "default"

        # Job configs
        self.transcript_analyzer_worker_config = JobConfig(
            queue_name=self.default_queue,
            worker_func="transcript_analyzer_worker",
        )

        self.request_panelist_worker_config = JobConfig(
            queue_name=self.default_queue,
            worker_func="request_panelist_worker",
        )

        self.interview_post_processing_worker_config = JobConfig(
            queue_name=self.default_queue,
            worker_func="interview_post_processing_worker",
        )
        
        
        self.interview_extraction_and_post_processsing = JobConfig(
            queue_name=self.default_queue,
            worker_func="interview_extraction_and_post_processsing_worker",
        )

        self.logger = get_logger("AssessmentTaskProducer")

    # -------------------- HELPERS --------------------

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    # -------------------- JOB ENQUEUE METHODS --------------------

    async def enqueue_transcript_analysis_job(
        self,
        payload: AnalyzeTranscriptPayload,
    ) -> Optional[Job]:

        config = self.transcript_analyzer_worker_config

        try:
            job_id = uuid()
            job = await self.redis.enqueue_job(
                config.worker_func,
                payload.to_dict(),
                _job_id=f"{payload.interview_id}_{str(job_id)}:transcript:analyze",  # idempotent
                _queue_name=config.queue_name,
                _defer_by=timedelta(seconds=5),
            )

            self.logger.info(
                f"[TranscriptAnalysis] Enqueued for interview_id={payload.interview_id}, job_id={job.job_id}"
            )

            return job

        except Exception:
            self.logger.exception(
                f"[TranscriptAnalysis] Failed for interview_id={payload.interview_id}"
            )
            return None

    async def enqueue_request_panelist_job(
        self,
        interview_id: str | UUID,
    ) -> Optional[Job]:

        config = self.request_panelist_worker_config

        try:
            job_id = uuid()
            job = await self.redis.enqueue_job(
                config.worker_func,
                str(interview_id),
                _job_id=f"{interview_id}_{job_id}:panelist:request_assessment",  # idempotent
                _queue_name=config.queue_name,
                _defer_by=timedelta(seconds=10),
            )

            self.logger.info(
                f"[RequestPanelistAssessment] Enqueued for interview_id={interview_id}, job_id={job.job_id}"
            )

            return job

        except Exception:
            self.logger.exception(
                f"[RequestPanelistAssessment] Failed for interview_id={interview_id}"
            )
            return None
        
        
    async def enqueue_interview_post_processing(
        self,
        interview_id: str | UUID,
    ) -> Optional[Job]:

        config = self.interview_post_processing_worker_config

        try:
            job_id = uuid()
            job = await self.redis.enqueue_job(
                config.worker_func,
                str(interview_id),
                _job_id=f"{interview_id}_{str(job_id)}:post_processing",  # idempotent
                _queue_name=config.queue_name,
                _defer_by=timedelta(seconds=5),
            )

            self.logger.info(
                f"[InterviewPostProcessing] Enqueued for interview_id={interview_id}, job_id={job.job_id}"
            )

            return job

        except Exception:
            self.logger.exception(
                f"[InterviewPostProcessing] Failed for interview_id={interview_id}"
            )
            return None
        
        
        
    async def enqueue_interview_extraction_and_post_processsing(
        self,
        meeting_id: str | UUID,
    ) -> Optional[Job]:

        config = self.interview_extraction_and_post_processsing

        try:
            job_id = uuid()
            job = await self.redis.enqueue_job(
                config.worker_func,
                str(meeting_id),
                _job_id=f"{meeting_id}_{str(job_id)}:Metting",  # idempotent
                _queue_name=config.queue_name,
                _defer_by=timedelta(seconds=3),
            )

            self.logger.info(
                f"[InterviewPostProcessing] Enqueued for meeting_id={meeting_id}, job_id={job.job_id}"
            )

            return job

        except Exception:
            self.logger.exception(
                f"[InterviewPostProcessing] Failed for meeting_id={meeting_id}"
            )
            return None