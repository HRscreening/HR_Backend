from configs.postgress_db import AsyncSession,get_db
from fastapi import Depends



from src.repositories.user_repository import UserRepository
from src.repositories.job_repository import JobRepository
from src.repositories.org_repository import OrganizationRepository



from src.services.auth_services import AuthService
from src.services.job_service import JobService
from src.utils.file_manager import FileManagerService




def get_user_repository(
    db: AsyncSession = Depends(get_db)
):
    return UserRepository(db)


def get_jwt_service():
    from src.utils.jwt import JWTService
    return JWTService()


def get_file_manager_service():
    return FileManagerService()


def get_auth_service(
    repo: UserRepository = Depends(get_user_repository),
    db: AsyncSession = Depends(get_db)
):
    return AuthService(repo, db)



def get_job_repository(
    db: AsyncSession = Depends(get_db)
):
    return JobRepository(db)



def get_org_repository(
    db: AsyncSession = Depends(get_db)
):
    return OrganizationRepository(db)


def get_job_service(
    jobRepo: JobRepository = Depends(get_job_repository),
    db: AsyncSession = Depends(get_db),
    org_repository: OrganizationRepository = Depends(get_org_repository)
):
    return JobService(db=db,  job_repositoy=jobRepo,org_repository=org_repository)
