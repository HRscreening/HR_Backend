import uuid
from typing import List
from arq.connections import ArqRedis
from configs.log_config import get_logger
from src.utils.chunk_generator import  chunk_list
from dataclasses import dataclass
from src.repositories.batch_repositoy import BatchRepository
from src.repositories.resume_respositoy import ResumeRepository
from src.schemas.user_schemas import CandidateInfoSchema

@dataclass
class JobConfig:
    queue_name: str
    worker_func: str




class EmailProducer:
    """
    Async producer for Email jobs
    """

    def __init__(self,redis:ArqRedis):
        self.redis  = redis
        self.default_queue = "default"
        
        # --------------- config ---------------
        # TODO: In arq each queue needs its own worker function. We can optimize this by having a single worker function that can handle both text and url scoring based on the batch metadata. This way we can use a single queue and reduce complexity. For now, we will keep them separate for clarity and ease of scaling different types of scoring independently in the future if needed.
        self.resume_parsing_config = JobConfig(
            queue_name=self.default_queue,
            worker_func="send_email_worker",
        )

        self.logger = get_logger("Email_PRODUCER")


    # =========================
    # Resume Parsing
    # =========================
    async def enqueue_email(
        self,
        recipient_email: str,
        subject: str,
        resume_paths: List[str],
        db_job_id: str,
        batch_id: str,
    ) -> str:
        """
        This producer creates a Redis job for each resume file to be parsed. It also creates a batch record in Redis to track the overall progress of the batch. Each job is enqueued with metadata linking it to the batch and the database job record for later correlation and status updates.
        """
        await self.redis.set("who_am_i", "producer")
        await self.redis.hset(
            f"batch:{str(batch_id)}",
            mapping={
                "total": len(resume_paths),
                "completed": 0,
                "failed": 0,
                "status": "queued",
            },
        )
        

        for path in resume_paths:
            redis_job_id = str(uuid.uuid4())

            await self.redis.hset(
                f"job:{redis_job_id}",
                mapping={
                    "status": "queued",
                    "batch_id": str(batch_id),
                    "db_job_id": str(db_job_id),
                    "file_path": path,
                    "type": "resume_parse",
                },
            )
            
            

            try:
                cfg = self.resume_parsing_config
                payload = {
                    "redis_job_id": redis_job_id,
                    "batch_id": str(batch_id),
                    "file_path": path
                }
                

                await self.redis.enqueue_job(
                    cfg.worker_func,
                    payload,
                    _queue_name=cfg.queue_name,
                )

            except Exception as e:
                self.logger.error(f"Failed to enqueue job {redis_job_id}: {e}")

                await self.redis.hset(
                    f"job:{redis_job_id}",
                    mapping={
                        "status": "failed_to_enqueue",
                        "error": str(e),
                    },
                )

        return batch_id
    
    
    # =========================
    # Resume Scoring (For those having Parsed Text) Producer
    # =========================
    async def _enqueue_scoring(
        self,
        job_id: str,
        resume_ids: list[str],
        batch_size: int,
        cfg: JobConfig,
        batch_type: str,
        db_batch_id: str,
    ) -> list[str]:

        created_batches = []

        for batch in chunk_list(resume_ids, batch_size):
            redis_job_id = str(uuid.uuid4())
            redis_batch_id = str(uuid.uuid4())

            try:
                # Batch metadata (includes db_batch_id for downstream DB operations)
                await self.redis.hset(
                    f"batch:{redis_batch_id}",
                    mapping={
                        "status": "queued",
                        "job_id": str(job_id),
                        "db_batch_id": str(db_batch_id),
                        "redis_job_id": redis_job_id,
                        "type": batch_type,
                        "total_resumes": len(batch),
                        "completed": 0,
                        "failed": 0,
                    },
                )

                # Store resume IDs efficiently
                await self.redis.rpush(
                    f"batch:{redis_batch_id}:resumes",
                    *[str(rid) for rid in batch],
                )

                payload = {
                    "redis_job_id": redis_job_id,
                    "batch_id": redis_batch_id,
                    "db_job_id": str(job_id),   
                    "db_batch_id": str(db_batch_id),  
                }

                # Enqueue job
                await self.redis.enqueue_job(
                    cfg.worker_func,
                    payload,
                    _queue_name=cfg.queue_name,
                )

                created_batches.append(redis_batch_id)

            except Exception as e:
                self.logger.error(f"Failed to enqueue batch {redis_batch_id}: {e}")

                await self.redis.hset(
                    f"batch:{redis_batch_id}",
                    mapping={
                        "status": "failed_to_enqueue",
                        "error": str(e),
                    },
                )

        return created_batches


    async def enqueue_text_scoring(
        self,
        job_id: str,
        resume_ids: list[str],
        db_batch_id: str,
        batch_size: int = 5,
    ) -> list[str]:

        return await self._enqueue_scoring(
            job_id=job_id,
            resume_ids=resume_ids,
            batch_size=batch_size,
            cfg=self.resume_scoring_text_config,
            batch_type="resume_scoring_text",
            db_batch_id=db_batch_id,
        )
        
    async def enqueue_url_scoring(
        self,
        job_id: str,
        resume_ids: list[str],
        db_batch_id: str,
        batch_size: int = 5,
    ) -> list[str]:

        return await self._enqueue_scoring(
            job_id=job_id,
            resume_ids=resume_ids,
            batch_size=batch_size,
            cfg=self.resume_scoring_url_config,
            batch_type="resume_scoring_url",
            db_batch_id=db_batch_id,
        )

    # =========================
    # Candidate Extraction Producer
    # =========================
    async def enqueue_candidate_extraction(
    self,
    resume_id: str,
    candidate: CandidateInfoSchema | None,
    batch_id: str,
    ) -> str | None:

        cfg = self.candidate_extraction_config
        redis_job_id = str(uuid.uuid4())

        payload = {
            "redis_job_id": redis_job_id,
            "resume_id": str(resume_id),
            "batch_id": str(batch_id),
            "candidate": (
                candidate.model_dump() if candidate else None
            ),
        }

        try:
            await self.redis.enqueue_job(
                cfg.worker_func,
                payload,
                _queue_name=cfg.queue_name,
            )

            return redis_job_id

        except Exception as e:
            self.logger.error(
                f"Failed to enqueue candidate extraction job "
                f"{redis_job_id} for resume_id={resume_id}: {e}"
            )

            await self.redis.hset(
                f"job:{redis_job_id}",
                mapping={
                    "status": "failed_to_enqueue",
                    "error": str(e),
                    "resume_id": str(resume_id),
                    "batch_id": str(batch_id),
                    "type": "candidate_extraction",
                },
            )

            return None

