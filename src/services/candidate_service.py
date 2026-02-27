from sqlalchemy.ext.asyncio import AsyncSession
from  configs.log_config import get_logger
from src.services.errors.base import DomainError
from pydantic import EmailStr
from src.repositories.candidiate_repository import CandidateRepository
from src.repositories.application_repository import ApplicationRepository
from src.schemas.candidate_schemas import CandidateUpdateSchema,CandidateCreateSchema
from src.schemas.score_schemas import CandidateInfoSchema
from src.repositories.resume_respositoy import ResumeRepository

class BaseCandidateService:
    def __init__(self, candidate_repository: CandidateRepository, application_repository: ApplicationRepository, db: AsyncSession):
        self.db = db
        self.candidate_repository = candidate_repository
        self.application_repository = application_repository
        self.logger = get_logger("BASE_CANDIDATE_SERVICE")
        
    async def get_candidate_by_id(self, candidate_id: str, org_id: str | None = None):
        candidate = await self.candidate_repository.get_candidate_by_id(candidate_id, org_id)
        if not candidate:
            raise DomainError(message="Candidate not found", status_code=404)
        return candidate
    
    async def get_candidate_applications(self, candidate_id: str, org_id: str | None = None):
        candidate = await self.get_candidate_by_id(candidate_id, org_id)
        applications = await self.application_repository.get_applications_by_candidate(candidate.id)
        return applications
    
    async def get_candidate_by_email(self, email: EmailStr, org_id: str | None = None):
        candidate = await self.candidate_repository.get_candidate_by_email(email, org_id)
        if not candidate:
            raise DomainError(message="Candidate not found", status_code=404)
        
        if isinstance(candidate, list) and len(candidate) > 1:
            self.logger.warning(f"Multiple candidates found with email {email} in org {org_id}. Returning the first one.")
            raise DomainError(message="Multiple candidates found with this email. Please contact support.", status_code=400)
        
        return candidate
    
    async def get_candidate_by_phone(self, phone: str, org_id: str | None = None):
        candidate = await self.candidate_repository.get_candidate_by_phone(phone, org_id)
        if not candidate:
            raise DomainError(message="Candidate not found", status_code=404)
        
        if isinstance(candidate, list) and len(candidate) > 1:
            self.logger.warning(f"Multiple candidates found with phone {phone} in org {org_id}. Returning the first one.")
            raise DomainError(message="Multiple candidates found with this phone number. Please contact support.", status_code=400)
        
        return candidate
    

    
    


class CandidateService(BaseCandidateService):
    def __init__(self, candidate_repository:CandidateRepository,application_repository:ApplicationRepository,db: AsyncSession):
        super().__init__(candidate_repository,application_repository,db)
        self.logger = get_logger("Candidate_SERVICE")


    # This is method is not direclty called by route, its called by application service when creating/updating candidate info through application flow.
    async def create_candidate(self,candidate_info: CandidateCreateSchema,org_id: str | None = None):
        try:
            candidate = await self.candidate_repository.create_candidate(
                candidate_info, org_id
            )

            await self.candidate_repository.commit()

            return candidate

        except DomainError:
            await self.candidate_repository.rollback()
            raise

        except Exception as e:
            await self.candidate_repository.rollback()
            self.logger.error(f"Failed to create candidate: {str(e)}")
            raise DomainError(message="Failed to create candidate", status_code=500)
        
 
    async def edit_candidate_info(self,candidate_id: str,candidate_info: CandidateUpdateSchema,org_id: str | None = None):
        try:
            candidate = await self.candidate_repository.get_candidate_by_id(
                candidate_id,
                org_id
            )

            if not candidate:
                raise DomainError("Candidate not found", 404)

            if candidate_info.full_name is not None:
                candidate.full_name = candidate_info.full_name

            if candidate_info.email is not None:
                candidate.email = candidate_info.email

            if candidate_info.phone is not None:
                candidate.phone = candidate_info.phone

            await self.db.commit()

            return candidate

        except DomainError:
            await self.db.rollback()
            raise

        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Failed to edit candidate info: {str(e)}")
            raise DomainError("Failed to edit candidate info", 500)




class CandidateService_ForWorker(BaseCandidateService):
    def __init__(self,candidate_repository:CandidateRepository,application_repository:ApplicationRepository,resume_repository:ResumeRepository,db: AsyncSession):
        super().__init__(candidate_repository,application_repository,db)
        self.resume_repositoy : ResumeRepository = resume_repository
        self.logger = get_logger("Candidate_WORKER_SERVICE")
        
    async def extract_candidate(
        self,
        resume_id: str,
        candidate_info: CandidateInfoSchema | None
    ):
        if not candidate_info:
            raise ValueError("Candidate info is missing")

        try:
            self.logger.info(
                f"Received candidate extraction task for resume_id={resume_id} "
                f"with extracted info: {candidate_info}"
            )

            resume = await self.resume_repositoy.get_resume_by_id(resume_id)

            if not resume or not resume.application_id:
                raise Exception(f"Resume with id {resume_id} not found or not linked to any application")
            

            application = await self.application_repository.get_application_by_id(resume.application_id)

            if not application:
                raise Exception(f"Application for resume {resume_id} not found")

            # ❌ truly insufficient info
            if not any([
                candidate_info.email,
                candidate_info.phone,
                candidate_info.full_name
            ]):
                raise Exception(
                    "Insufficient candidate info to create or link candidate"
                )

            # TODO: To be handled for now is it None
            # org_id = db.execute(
            #     select(Job.organization_id)
            #     .join(Application, Job.id == Application.job_id)
            #     .where(Application.id == application.id)
            # ).scalar_one()
            org_id = None

            candidate = None
            

            # ✅ Prefer email match
            if candidate_info.email:
                candidate = await self.candidate_repository.get_candidate_by_email(candidate_info.email, org_id)

            # ✅ Fallback to phone match
            if not candidate and candidate_info.phone:
                candidate = await self.candidate_repository.get_candidate_by_phone(candidate_info.phone, org_id)

            if candidate:
                application.candidate_id = candidate.id
                resume.candidate_id = candidate.id
                candidate.total_applications += 1
                await self.db.commit()
                return

            new_candidate = await self.candidate_repository.create_candidate(candidate_info, org_id)

            resume.candidate_id = new_candidate.id
            application.candidate_id = new_candidate.id

            await self.db.commit()
            self.logger.info(f"Candidate extraction successful for resume_id={resume_id}, candidate_id={new_candidate.id}")
            
        except Exception as e:
            self.logger.error(f"Candidate extraction failed for resume_id={resume_id}: {str(e)}")
            raise