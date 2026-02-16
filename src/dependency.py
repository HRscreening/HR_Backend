from configs.postgress_db import AsyncSession,get_db
from fastapi import Depends



from src.repositories.user_repository import UserRepository
from src.repositories.job_repository import JobRepository
from src.repositories.org_repository import OrganizationRepository
from src.repositories.batch_repositoy import BatchRepository
from src.repositories.application_repository import ApplicationRepository
from src.repositories.candidiate_repository import CandidateRepository 



from src.services.auth_services import AuthService
from src.services.user_services import UserService
from src.services.job_service import JobService
from src.utils.file_manager import FileManagerService
from src.services.batch_service import BatchService
from src.services.application_service import ApplicationService
from src.services.candidate_service import CandidateService
from src.utils.email_service import emailService 
from src.utils.security import passwordService


# --------------------------- Repositories --------------------------

def get_batch_repository(
    db: AsyncSession = Depends(get_db)
):
    return BatchRepository(db)

def get_user_repository(
    db: AsyncSession = Depends(get_db)
):
    return UserRepository(db)

def get_job_repository(
    db: AsyncSession = Depends(get_db)
):
    return JobRepository(db)

def get_org_repository(
    db: AsyncSession = Depends(get_db)
):
    return OrganizationRepository(db)

def get_application_repository(
    db: AsyncSession = Depends(get_db)
):
    return ApplicationRepository(db)

def get_candidate_repository(
    db: AsyncSession = Depends(get_db)
): 
    return CandidateRepository(db)



# -------------------------- Services --------------------------

def get_jwt_service():
    from src.utils.jwt import JWTService
    return JWTService()


def get_file_manager_service():
    return FileManagerService()


def get_auth_service(
    repo: UserRepository = Depends(get_user_repository),
    db: AsyncSession = Depends(get_db)
):
    return AuthService(repo,emailService,passwordService,db)

def get_user_service(
    repo: UserRepository = Depends(get_user_repository),
    db: AsyncSession = Depends(get_db)
):

    return UserService(repo,db)


def get_job_service(
    jobRepo: JobRepository = Depends(get_job_repository),
    db: AsyncSession = Depends(get_db),
    batch_repository: BatchRepository = Depends(get_batch_repository),
    org_repository: OrganizationRepository = Depends(get_org_repository),
    application_repository: ApplicationRepository = Depends(get_application_repository)
):
    return JobService(db=db,  job_repositoy=jobRepo,batch_repository=batch_repository,org_repository=org_repository,application_repository=application_repository)

def get_batch_service(
    batch_repository: BatchRepository = Depends(get_batch_repository),
    db: AsyncSession = Depends(get_db)
):
    return BatchService(batch_repository=batch_repository, db=db)

def get_application_service(
    application_repository: ApplicationRepository = Depends(get_application_repository),
    candidate_repository: CandidateRepository = Depends(get_candidate_repository),
    db: AsyncSession = Depends(get_db)
):
    return ApplicationService(application_repository=application_repository , candidate_repository=candidate_repository, db=db)

def get_candidate_service(
    candidate_repository: CandidateRepository = Depends(get_candidate_repository),
    application_repository: ApplicationRepository = Depends(get_application_repository),
    db: AsyncSession = Depends(get_db)
):
    return CandidateService(candidate_repository=candidate_repository, application_repository=application_repository, db=db)