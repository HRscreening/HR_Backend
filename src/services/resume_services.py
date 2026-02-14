# ! : This service uses synchronous DB session for workers.

from configs.postgress_db import get_sync_db,AsyncSession
from src.models import Resume, Application,BulkUploadBatches,Document,Rubric,Candidate,Score,Job
from src.utils.extract_pdf import extract_text_from_pdf_sync
from src.utils.manage_supabase_buckets import supabase_file_handler,save_file_from_path
import aiofiles
import os
from src.schemas.worker_task_schemas import ResumeParsingJobSchema
from src.schemas.user_schemas import ResumeDataSchema,BatchResumeDataSchema,ScoreOutputSchema,CandidateInfoSchema
from src.models.enums import ResumeStatus, DocumentProcessingStatus,BulkUploadStatus
from configs.env_config import SUPABASE_PUBLIC_URL
import os
import mimetypes
from sqlalchemy import select,func,update,and_
import json
from workers.producer import enqueue_resumes_scoring,enqueue_candidate_extraction
from src.services.errors.base import DomainError 
from src.pipelines.process_resumes import run_gemini_batch
from src.utils.jsonl_creator import write_resume_scoring_jsonl
from langchain.messages import SystemMessage
from src.pipelines.prompts import Prompts
from src.pipelines.score_resumes import score_resume_async,score_resume_sync


    
def parse_resume_service(
    *,
    file_path: str,
    batch_id: str,
    redis_job_id: str | None = None,
):
    with get_sync_db() as db:
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            parsed_text, page_count = extract_text_from_pdf_sync(file_path)
            file_name = os.path.basename(file_path)
            
            job_id_result = db.execute(
                select(BulkUploadBatches).where(BulkUploadBatches.id == batch_id)
            )
            batch = job_id_result.scalar_one_or_none()
            
            if not batch:
                raise ValueError(f"Batch with id {batch_id} not found in DB")
            
            job_id = batch.job_id

            print("\n",file_path,"\n")
            uploaded_file_url = save_file_from_path(
                local_file_path=file_path,
                bucket_name="resumes",
                destination_path=f"{job_id}/{file_name}"
            )

            application = Application(
                job_id=job_id,
            )
            db.add(application)
            db.flush()

            resume = Resume(
                application_id=application.id,
                raw_file_url=uploaded_file_url,
                parsed_text=parsed_text,
                page_count=page_count,
                status=ResumeStatus.PARSED
            )
            db.add(resume)
            db.flush()

            mime_type, _ = mimetypes.guess_type(file_path)
            mime_type = mime_type or "application/pdf"

            document = Document(
                entity_type="resume",
                entity_id=resume.id,
                document_type="Resume",
                file_name=os.path.basename(file_path),
                file_size_bytes=os.path.getsize(file_path),
                mime_type=mime_type,
                storage_provider="supabase",
                file_path=str(uploaded_file_url),
                file_url=f"{SUPABASE_PUBLIC_URL}/{uploaded_file_url}",
                extracted_text=parsed_text,
                parsing_status=DocumentProcessingStatus.PARSED,
            )
            
            db.add(document)
            
            application.current_resume_id = resume.id
            
            
            #TODO: Update the batch table with the count of processed files and any errors if needed. This can help in tracking the progress of the batch processing.
            
            if batch:
                batch.success_count += 1
            
            parse_result = f"{file_name} parsed successfully"
            batch.processing_results = (batch.processing_results or "") + json.dumps({
                "file_name": file_name,
                "result": parse_result
            }) + "\n"
            
            db.commit()

        except Exception:
            db.rollback()
            raise


def mark_fail_job(batch_id: str, file_name: str, error_msg: str):
    with get_sync_db() as db:
        result = db.execute(
            select(BulkUploadBatches).where(BulkUploadBatches.id == batch_id)  
        )
        batch = result.scalar_one_or_none()
        
        if batch:
            batch.failed_count += 1
            batch.processing_results = (batch.processing_results or "") + json.dumps({
                "file_name": file_name,
                "result": f"Failed: {error_msg}"
            }) + "\n"
            db.commit()


def finalize_batch_parsed(batch_id: str):
    with get_sync_db() as db:
        batch = db.execute(
            select(BulkUploadBatches)
            .where(BulkUploadBatches.id == batch_id)
            .with_for_update()   # 🔒 critical
        ).scalar_one_or_none()

        if not batch:
            return

        # ✅ batch not fully processed yet
        if batch.total_files != (batch.failed_count + batch.success_count):
            return

        # ✅ idempotency guard USING EXISTING STATUS
        if batch.status == BulkUploadStatus.COMPLETED:
            return

        job_id = batch.job_id

        resumes = db.execute(
            select(Resume)
            .join(Application, Resume.application_id == Application.id)
            .where(
                Application.job_id == job_id,
                Resume.status == ResumeStatus.PARSED
            )
            .with_for_update()   
        ).scalars().all()

        resume_ids = []

        for resume in resumes:
            resume.status = ResumeStatus.QUEUED_FOR_SCORING
            resume_ids.append(resume.id)

        if resume_ids:
            enqueue_resumes_scoring(
                job_id=str(job_id),
                resume_ids=resume_ids
            )

        # 🔒 single-winner state transition
        batch.status = BulkUploadStatus.COMPLETED
        db.commit()


# Should be for worker but now testing as an API
# TODO: For workers we will be passing batch_id only
async def score_resumes_service(job_id: str, db: AsyncSession):
    try:
        result = await db.execute(
            select(Resume)
            .join(
                Application,
                Resume.application_id == Application.id
            )
            .where(
                Application.job_id == job_id,
                Resume.status == ResumeStatus.PARSED
            )
        )

        resumes = result.scalars().all()

        if not resumes:
            raise DomainError(f"No parsed resumes found for job {job_id}")

        # Split into batches (1000 max per Gemini batch)
        
        rubric_result = await db.execute(
            select(Rubric).where(Rubric.job_id == job_id , Rubric.is_active == True)
        ) 
        
        rubric = rubric_result.scalar_one_or_none()
        
        if not rubric:
            raise DomainError(f"No active rubric found for job {job_id}")

        resumes = [ResumeDataSchema(application_id=r.application_id,resume_id=r.id ,resume_text=r.parsed_text) for r in resumes]
        
        res = await score_resume_async(
            resumes=resumes,
            criteria=rubric.criteria
        )
        
        
        return res


    except Exception as e:
        raise DomainError(
            f"Error scoring resumes for job {job_id}"
        ) from e


# WORKER TASKS BELOW - NOT API SERVICES
def score_resumes_service_sync(
    *,
    db_job_id: str,
    resume_ids: list[str],
    batch_id: str,
    redis_job_id: str | None = None
):
    if not resume_ids:
        raise DomainError("Empty resume batch received")

    with get_sync_db() as db:
        
        print(f"""
              Resume scoring service called with db_job_id={db_job_id}, batch_id={batch_id}, resume_ids={resume_ids}
              """
        )

        job = db.execute(
            select(Job).where(Job.id == db_job_id)
        ).scalar_one_or_none()

        # TODO: We can also check if the job is in a correct state to be processed (like not paused or completed) and raise error if not.
        if not job :
            raise DomainError(f"Job {db_job_id} not found or not active")
        
        org_id = job.organization_id
        
        # 1️⃣ Fetch ONLY resumes in this batch
        result = db.execute(
            select(Resume)
            .join(
                Application,
                Resume.application_id == Application.id
            )
            .where(
                Application.job_id == db_job_id,
                Resume.id.in_(resume_ids),
                Resume.status == ResumeStatus.QUEUED_FOR_SCORING
            )
        )

        resumes = result.scalars().all()

        if not resumes:
            raise DomainError(
                f"No parsed resumes found for batch {batch_id}"
            )

        # 2️⃣ Fetch active rubric
        rubric_result = db.execute(
            select(Rubric)
            .where(
                Rubric.job_id == db_job_id,
                Rubric.is_active.is_(True)
            )
        )
        
        rubric = rubric_result.scalar_one_or_none()

        if not rubric:
            raise DomainError(
                f"No active rubric found for job {db_job_id}"
            )
            
        

        # 3️⃣ Prepare LLM input
        resume_payload = [
            ResumeDataSchema(
                application_id=r.application_id,  # derived here
                resume_id=r.id,
                resume_text=r.parsed_text
            )
            for r in resumes
        ]

        # 4️⃣ ONE batch LLM call
        score_results = score_resume_sync(
            resumes=resume_payload,
            criteria=rubric.criteria
        )
        
        applications = {
            a.id: a
            for a in db.execute(
                select(Application).where(
                    Application.id.in_(
                        {r.application_id for r in resumes}
                    )
                )
            ).scalars()
        }

        resume_map = {r.id: r for r in resumes}
        
        # 5️⃣ Persist results
        for item in score_results:
 
            # Can add a check for existing score for the resume and decide to update or skip based on that. For now assuming one score per resume.
            appl = db.execute(
                select(Application).where(Application.id == item.application_id)
            ).scalar_one_or_none()
            
            appl = applications.get(item.application_id)
            
            if appl:
                appl.ai_analysis = item.score.ai_analysis
                
            candidate_info = item.score.candidate_info
            

            if candidate_info and candidate_info.full_name :
                print(f"Enqueuing candidate extraction for resume_id={item.resume_id} with candidate info: {candidate_info}")
                enqueue_candidate_extraction(
                    resume_id=item.resume_id,
                    batch_id=batch_id,
                    candidate=item.score.candidate_info
                )
            
            
            resume = resume_map.get(item.resume_id)

            if resume:
                resume.status = ResumeStatus.SCORED

            
            
            db.add(
                Score(
                    application_id=item.application_id,
                    rubric_id=rubric.id,
                    overall_score=item.score.overall_score,
                    ai_confidence=item.score.ai_confidence,
                    breakdown=item.score.breakdown.model_dump(),
                    grounding_data=item.score.grounding_data,
                    scored_by="AI",
                    threshold_score=rubric.threshold_score,
                    criteria=rubric.criteria,
                    ai_model = "Gemini-2.5-Flash-lite"
                )
            )

        db.commit()

        return {
            "status": "BATCH_COMPLETED",
            "batch_id": batch_id,
            "scored_count": len(score_results)
        }


# WORKER
def extract_candidate_service(
    resume_id: str,
    candidate_info: CandidateInfoSchema | None
):
    if not candidate_info:
        raise ValueError("Candidate info is missing")

    with get_sync_db() as db:

        print(
            f"Received candidate extraction task for resume_id={resume_id} "
            f"with extracted info: {candidate_info}"
        )

        resume = db.execute(
            select(Resume).where(Resume.id == resume_id)
        ).scalar_one_or_none()

        if not resume:
            raise Exception(f"Resume with id {resume_id} not found")

        application = db.execute(
            select(Application).where(Application.id == resume.application_id)
        ).scalar_one_or_none()

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

        org_id = db.execute(
            select(Job.organization_id)
            .join(Application, Job.id == Application.job_id)
            .where(Application.id == application.id)
        ).scalar_one()

        candidate = None

        # ✅ Prefer email match
        if candidate_info.email:
            candidate = db.execute(
                select(Candidate).where(
                    and_(
                        Candidate.email == candidate_info.email,
                        Candidate.organization_id == org_id
                    )
                )
            ).scalar_one_or_none()

        # ✅ Fallback to phone match
        if not candidate and candidate_info.phone:
            candidate = db.execute(
                select(Candidate).where(
                    and_(
                        Candidate.phone == candidate_info.phone,
                        Candidate.organization_id == org_id
                    )
                )
            ).scalar_one_or_none()

        if candidate:
            application.candidate_id = candidate.id
            resume.candidate_id = candidate.id
            candidate.total_applications += 1
            db.commit()
            return

        # 🚨 Create new candidate
        new_candidate = Candidate(
            full_name=candidate_info.full_name,
            email=candidate_info.email,
            phone=candidate_info.phone,
            organization_id=org_id
            
        )

        db.add(new_candidate)
        db.flush()  

        resume.candidate_id = new_candidate.id
        application.candidate_id = new_candidate.id

        db.commit()
