from contextlib import asynccontextmanager

from async_workers.producer import ARQProducer

from src.repositories.job_repository import JobRepository
from src.repositories.resume_respositoy import ResumeRepository
from src.repositories.application_repository import ApplicationRepository
from src.repositories.batch_repositoy import BatchRepository
from src.repositories.score_repository import ScoreRepository
from src.repositories.document_repository import DocumentRepository
from src.repositories.candidiate_repository import CandidateRepository

from src.services.resume_services import ResumeService_ForWorker
from src.services.candidate_service import CandidateService_ForWorker
from src.services.batch_service import BatchService_ForWorker


@asynccontextmanager
async def job_context(ctx):
    """
    Create per-job dependencies automatically.
    """

    sessionmaker = ctx["db_sessionmaker"]
    redis = ctx["redis"]

    async with sessionmaker() as db:

        producer = ARQProducer(redis)

        # repos
        job_repo = JobRepository(db)
        resume_repo = ResumeRepository(db)
        application_repo = ApplicationRepository(db)
        batch_repo = BatchRepository(db)
        score_repo = ScoreRepository(db)
        document_repo = DocumentRepository(db)
        candidate_repo = CandidateRepository(db)

        # services
        resume_service = ResumeService_ForWorker(
            db=db,
            resume_repository=resume_repo,
            score_repository=score_repo,
            job_producer=producer,
            application_repository=application_repo,
            batch_repository=batch_repo,
            document_repository=document_repo,
            job_repository=job_repo,
        )

        batch_service = BatchService_ForWorker(
            db=db,
            batch_repository=batch_repo,
            resume_repository=resume_repo,
            job_producer=producer,
        )

        candidate_service = CandidateService_ForWorker(
            db=db,
            candidate_repository=candidate_repo,
            application_repository=application_repo,
            resume_repository=resume_repo,
        )
        
        

        yield {
            "db": db,
            "resume_service": resume_service,
            "batch_service": batch_service,
            "candidate_service": candidate_service,
        }
