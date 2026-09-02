import asyncio
import json
import logging
import mimetypes
import os

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from configs.env_config import SUPABASE_PUBLIC_URL
from configs.postgress_db import get_sync_db
from src.models import Resume, Application, BulkUploadBatches, Document, Rubric, Candidate, Score, Job
from src.models.enums import ResumeStatus, DocumentProcessingStatus, BulkUploadStatus
# LAZY IMPORT: score_resume_async / score_resume_sync are imported inside the
# functions that use them, NOT at module level.  Importing score_resumes.py
# triggers src.pipelines.models which creates ChatGoogleGenerativeAI (gRPC).
# RQ forks a child process for each job — gRPC state corrupted after fork
# causes SIGSEGV (signal 11) on macOS.  Lazy import ensures models are only
# initialised inside the already-forked child, avoiding the crash.
from src.schemas.user_schemas import ResumeDataSchema, CandidateInfoSchema
from src.services.errors.base import DomainError
from src.utils.extract_pdf import extract_text_from_file_sync
from src.utils.candidate_name import extract_candidate_full_name
from src.utils.manage_supabase_buckets import download_to_tempfile
from workers.producer import enqueue_resumes_scoring, enqueue_candidate_extraction, enqueue_pre_screen_and_score
from src.utils.pipeline_debug_log import pdlog

logger = logging.getLogger(__name__)


    
def parse_resume_service(
    *,
    storage_path: str,
    batch_id: str,
    redis_job_id: str | None = None,
):
    """
    Parse a resume from Supabase storage.

    storage_path: full path including bucket, e.g. "resumes/job_id/filename.pdf"
    File is already uploaded to Supabase at request time — no local file dependency.
    """
    file_name = os.path.basename(storage_path)
    logger.info(f"[SERVICE] parse_resume_service START: file={file_name} batch={batch_id}")

    tmp_path = None
    with get_sync_db() as db:
        try:
            logger.info(f"[SERVICE] Downloading from Supabase: {storage_path}")
            tmp_path = download_to_tempfile(storage_path)

            logger.info(f"[SERVICE] Extracting text from: {file_name}")
            parsed_text, page_count, extraction_method = extract_text_from_file_sync(tmp_path)
            logger.info(
                f"[SERVICE] Extracted: file={file_name} pages={page_count} "
                f"method={extraction_method} chars={len(parsed_text)}"
            )
            pdlog.extraction(file_name, parsed_text, extraction_method, page_count)

            logger.info(f"[SERVICE] Fetching batch {batch_id} from DB")
            batch = db.execute(
                select(BulkUploadBatches).where(BulkUploadBatches.id == batch_id)
            ).scalar_one_or_none()

            if not batch:
                raise ValueError(f"Batch {batch_id} not found in DB")

            job_id = batch.job_id
            logger.info(f"[SERVICE] Batch found: job_id={job_id} total_files={batch.total_files}")

            application = Application(job_id=job_id)
            db.add(application)
            db.flush()
            logger.info(f"[SERVICE] Application created: id={application.id}")

            resume = Resume(
                application_id=application.id,
                raw_file_url=storage_path,
                parsed_text=parsed_text,
                page_count=page_count,
                extraction_method=extraction_method,
                status=ResumeStatus.PARSED,
            )
            db.add(resume)
            db.flush()
            logger.info(f"[SERVICE] Resume created: id={resume.id}")

            mime_type, _ = mimetypes.guess_type(file_name)
            mime_type = mime_type or "application/pdf"

            document = Document(
                entity_type="resume",
                entity_id=resume.id,
                document_type="Resume",
                file_name=file_name,
                file_size_bytes=os.path.getsize(tmp_path),
                mime_type=mime_type,
                storage_provider="supabase",
                file_path=storage_path,
                file_url=f"{SUPABASE_PUBLIC_URL}/{storage_path}",
                extracted_text=parsed_text,
                parsing_status=DocumentProcessingStatus.PARSED.value,
            )
            db.add(document)

            application.current_resume_id = resume.id
            batch.success_count += 1
            batch.processed_count += 1

            results = batch.processing_results
            if not isinstance(results, dict):
                results = {}
            results[file_name] = f"parsed successfully (method={extraction_method})"
            batch.processing_results = results

            db.commit()
            logger.info(
                f"[SERVICE] DB committed: file={file_name} "
                f"batch success_count={batch.success_count}/{batch.total_files}"
            )

        except Exception as e:
            logger.error(f"[SERVICE] parse_resume_service FAILED: file={file_name} error={e!r}")
            db.rollback()
            raise

        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass


def mark_fail_job(batch_id: str, file_name: str, error_msg: str):
    logger.info(f"[SERVICE] mark_fail_job: file={file_name} batch={batch_id}")
    with get_sync_db() as db:
        result = db.execute(
            select(BulkUploadBatches).where(BulkUploadBatches.id == batch_id)
        )
        batch = result.scalar_one_or_none()

        if batch:
            batch.failed_count += 1
            batch.processed_count += 1

            results = batch.processing_results
            if not isinstance(results, dict):
                results = {}
            results[file_name] = f"failed: {error_msg}"
            batch.processing_results = results

            err = batch.error_log
            if not isinstance(err, dict):
                err = {}
            err[file_name] = error_msg
            batch.error_log = err
            db.commit()
            logger.info(
                f"[SERVICE] mark_fail_job committed: file={file_name} "
                f"batch failed_count={batch.failed_count}/{batch.total_files}"
            )
        else:
            logger.error(f"[SERVICE] mark_fail_job: batch {batch_id} not found in DB")


def finalize_batch_parsed(batch_id: str):
    """
    Finalize a parsing batch: enqueue scoring for all successfully parsed resumes.
    Uses DB counts exclusively — Redis counters are unreliable due to stale retries.
    Safe to call after every job; the FOR UPDATE lock ensures only one winner.
    """
    logger.info(f"[FINALIZE_DB] finalize_batch_parsed START: batch={batch_id}")

    with get_sync_db() as db:
        batch = db.execute(
            select(BulkUploadBatches)
            .where(BulkUploadBatches.id == batch_id)
            .with_for_update()
        ).scalar_one_or_none()

        if not batch:
            logger.error(f"[FINALIZE_DB] batch {batch_id} not found in DB — cannot finalize")
            return

        logger.info(
            f"[FINALIZE_DB] DB state: total_files={batch.total_files} "
            f"success_count={batch.success_count} failed_count={batch.failed_count} "
            f"status={batch.status}"
        )

        # Idempotency guard
        if batch.status == BulkUploadStatus.COMPLETED:
            logger.info(f"[FINALIZE_DB] batch {batch_id} already completed — skipping")
            return

        # Check DB counts only — no Redis dependency.
        # Use >= instead of == to handle edge cases where counts may be slightly
        # over-incremented (e.g., success on retry after a previous failure was counted).
        processed = batch.success_count + batch.failed_count
        if processed < batch.total_files:
            logger.info(
                f"[FINALIZE_DB] batch {batch_id} still incomplete: "
                f"total={batch.total_files} success={batch.success_count} failed={batch.failed_count} "
                f"processed={processed} — waiting"
            )
            return

        if processed > batch.total_files:
            logger.warning(
                f"[FINALIZE_DB] batch {batch_id} over-counted: "
                f"total={batch.total_files} success={batch.success_count} failed={batch.failed_count} "
                f"processed={processed} — proceeding with finalization anyway"
            )

        job_id = batch.job_id
        logger.info(f"[FINALIZE_DB] All {batch.total_files} files done. Fetching parsed resumes for job {job_id}")

        resumes = db.execute(
            select(Resume)
            .join(Application, Resume.application_id == Application.id)
            .where(
                Application.job_id == job_id,
                Resume.status == ResumeStatus.PARSED
            )
            .with_for_update()
        ).scalars().all()

        resume_ids = [str(r.id) for r in resumes]
        logger.info(f"[FINALIZE_DB] Found {len(resume_ids)} resumes to score")

        for resume in resumes:
            resume.status = ResumeStatus.QUEUED_FOR_SCORING

        if resume_ids:
            enqueue_pre_screen_and_score(
                job_id=str(job_id),
                resume_ids=resume_ids,
                upload_batch_id=str(batch.id),
            )
            batch.scoring_total = len(resume_ids)
            batch.scoring_status = BulkUploadStatus.PROCESSING
            logger.info(f"[FINALIZE_DB] Enqueued pre-screen + scoring for {len(resume_ids)} resumes")
        else:
            logger.warning(f"[FINALIZE_DB] No resumes to score — all failed parsing?")

        batch.status = BulkUploadStatus.COMPLETED
        db.commit()
        logger.info(f"[FINALIZE_DB] batch {batch_id} finalized and committed")


async def score_all_service(job_id: str, db: AsyncSession) -> dict:
    """
    Enqueue scoring for all PARSED resumes of a job via the RQ worker.

    Returns a dict with enqueued_count, batch_ids, and a message.
    Raises DomainError if no parsed resumes exist or no active rubric found.
    """
    resume_result = await db.execute(
        select(Resume)
        .join(Application, Resume.application_id == Application.id)
        .where(
            Application.job_id == job_id,
            Resume.status == ResumeStatus.PARSED,
        )
    )
    resumes = resume_result.scalars().all()

    if not resumes:
        raise DomainError(f"No parsed resumes found for job {job_id}")

    rubric_result = await db.execute(
        select(Rubric).where(Rubric.job_id == job_id, Rubric.is_active.is_(True))
    )
    rubric = rubric_result.scalar_one_or_none()

    if not rubric:
        raise DomainError(f"No active rubric found for job {job_id}")

    resume_ids = [str(r.id) for r in resumes]
    batch_id = enqueue_pre_screen_and_score(job_id=job_id, resume_ids=resume_ids)

    return {
        "enqueued_count": len(resume_ids),
        "batch_ids": [batch_id],
        "message": f"Scoring enqueued for {len(resume_ids)} resume(s)",
    }


# Should be for worker but now testing as an API
# TODO: For workers we will be passing batch_id only
async def score_resumes_service(job_id: str, db: AsyncSession):
    from src.pipelines.score_resumes import score_resume_async
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

        # Extract candidate info first
        from src.pipelines.extract_candidate_info import extract_candidate_info_async
        candidate_infos = {}
        for r in resumes:
            try:
                ci = await extract_candidate_info_async(r.parsed_text or "")
                candidate_infos[str(r.id)] = ci
            except Exception:
                candidate_infos[str(r.id)] = CandidateInfoSchema()

        resumes = [ResumeDataSchema(application_id=r.application_id, resume_id=r.id, resume_text=r.parsed_text) for r in resumes]

        res = await score_resume_async(
            resumes=resumes,
            criteria=rubric.criteria,
            candidate_infos=candidate_infos,
        )
        
        
        return res


    except Exception as e:
        raise DomainError(
            f"Error scoring resumes for job {job_id}"
        ) from e


# ─── Pipeline v2: Pre-screen + Score (3-stage) ────────────────────────

def pre_screen_and_score_service_sync(
    *,
    db_job_id: str,
    resume_ids: list[str],
    batch_id: str,
    redis_job_id: str | None = None,
):
    """
    Pipeline v2: Quality Gate → Cross-Encoder → LLM Scoring.

    Runs all 3 stages in a single worker task. Updates each resume's
    status in DB after each stage so the UI can show real-time progress.
    """
    from src.pipelines.quality_gate import run_quality_gate
    from src.pipelines.relevance_scorer import score_relevance_batch
    from src.pipelines.non_negotiable_screener import screen_non_negotiables_sync
    from src.pipelines.score_resumes import score_resume_sync

    if not resume_ids:
        raise DomainError("Empty resume batch received")

    with get_sync_db() as db:
        logger.info(
            "[PIPELINE_V2] ══════════════════════════════════════════════════"
        )
        logger.info(
            "[PIPELINE_V2] START  job=%s  batch=%s  resumes=%d",
            db_job_id, batch_id, len(resume_ids),
        )
        logger.info(
            "[PIPELINE_V2] Stages: Quality Gate → Cross-Encoder (BERT) → Non-Negotiable Screen → LLM Scoring"
        )
        logger.info(
            "[PIPELINE_V2] ══════════════════════════════════════════════════"
        )

        # ── Fetch job + rubric ──────────────────────────────────────
        job = db.execute(
            select(Job).where(Job.id == db_job_id)
        ).scalar_one_or_none()
        if not job:
            raise DomainError(f"Job {db_job_id} not found")

        rubric = db.execute(
            select(Rubric).where(
                Rubric.job_id == db_job_id,
                Rubric.is_active.is_(True),
            )
        ).scalar_one_or_none()
        if not rubric:
            raise DomainError(f"No active rubric for job {db_job_id}")

        # ── Fetch resumes ───────────────────────────────────────────
        resumes = db.execute(
            select(Resume)
            .join(Application, Resume.application_id == Application.id)
            .where(
                Application.job_id == db_job_id,
                Resume.id.in_(resume_ids),
                Resume.status == ResumeStatus.QUEUED_FOR_SCORING,
            )
        ).scalars().all()

        if not resumes:
            raise DomainError(f"No resumes to process in batch {batch_id}")

        # Map by both UUID and string key for flexible lookup
        resume_map: dict = {}
        for r in resumes:
            resume_map[r.id] = r
            resume_map[str(r.id)] = r

        # ── Dedup: skip already-scored ──────────────────────────────
        existing_scores = db.execute(
            select(Score.application_id).where(
                Score.rubric_id == rubric.id,
                Score.application_id.in_({r.application_id for r in resumes}),
                Score.is_active.is_(True),
            )
        ).scalars().all()
        already_scored = set(existing_scores)
        resumes_to_process = [
            r for r in resumes if r.application_id not in already_scored
        ]

        if not resumes_to_process:
            logger.info("All resumes already scored — skipping batch %s", batch_id)
            return {
                "status": "BATCH_SKIPPED",
                "batch_id": batch_id,
                "scored_count": 0,
                "failed_count": 0,
                "pre_screened_count": 0,
                "quality_gate_failed_count": 0,
                "non_negotiable_failed_count": 0,
            }

        # ── STAGE 1: Quality Gate ───────────────────────────────────
        logger.info("[PIPELINE_V2] Stage 1: Quality Gate on %d resumes", len(resumes_to_process))
        gate_input = [
            {
                "resume_id": str(r.id),
                "parsed_text": r.parsed_text or "",
                "status": r.status.value if r.status else "",
            }
            for r in resumes_to_process
        ]

        gate_passed, gate_rejected = run_quality_gate(gate_input)

        # Update DB for rejected resumes
        for result in gate_rejected:
            resume = resume_map.get(result.resume_id)
            if resume:
                resume.status = ResumeStatus.QUALITY_GATE_FAILED
                resume.rejection_reason = result.rejection_reason
        db.flush()
        logger.info(
            "[PIPELINE_V2] Quality Gate: %d passed, %d rejected",
            len(gate_passed), len(gate_rejected),
        )

        if not gate_passed:
            db.commit()
            return {
                "status": "BATCH_COMPLETED",
                "batch_id": batch_id,
                "scored_count": 0,
                "failed_count": 0,
                "pre_screened_count": 0,
                "quality_gate_failed_count": len(gate_rejected),
                "non_negotiable_failed_count": 0,
            }

        # ── STAGE 2: Cross-Encoder Relevance Scoring ────────────────
        jd_text = job.raw_jd_text or ""
        if not jd_text:
            # Fallback: build JD text from rubric criteria
            sections = rubric.criteria.get("sections", [])
            parts = []
            for sec in sections:
                for c in sec.get("criteria", []):
                    display = c.get("display_name", c.get("name", ""))
                    val = c.get("value", "")
                    parts.append(f"{display}: {val}" if val else display)
            jd_text = "\n".join(parts)

        logger.info(
            "[PIPELINE_V2] ── Stage 2: Cross-Encoder (BERT) on %d resumes ──",
            len(gate_passed),
        )
        selected, pre_screened = score_relevance_batch(
            resumes=gate_passed,
            jd_text=jd_text,
        )

        # Update DB for pre-screened (rejected by cross-encoder) resumes
        for result in pre_screened:
            resume = resume_map.get(result.resume_id)
            if resume:
                resume.status = ResumeStatus.PRE_SCREENED
                resume.pre_screen_rank = result.rank
                resume.relevance_score = result.relevance_score
                resume.rejection_reason = result.rejection_reason
        db.flush()
        logger.info(
            "[PIPELINE_V2] Stage 2 DONE: %d → LLM scoring | %d → pre-screened",
            len(selected), len(pre_screened),
        )
        # Log per-resume scores written to DB so results are visible
        for s in selected:
            logger.info(
                "[PIPELINE_V2]   SELECTED  rank=%-2s score=%.4f resume=%s",
                s.get("rank", "?"), s.get("relevance_score") or 0.0, s["resume_id"],
            )
        for r in pre_screened:
            logger.info(
                "[PIPELINE_V2]   SKIPPED   rank=%-2s score=%.4f resume=%s",
                r.rank, r.relevance_score, r.resume_id,
            )

        if not selected:
            db.commit()
            return {
                "status": "BATCH_COMPLETED",
                "batch_id": batch_id,
                "scored_count": 0,
                "failed_count": 0,
                "pre_screened_count": len(pre_screened),
                "quality_gate_failed_count": len(gate_rejected),
                "non_negotiable_failed_count": 0,
            }

        # Update selected resumes with rank + relevance score
        for s in selected:
            resume = resume_map.get(s["resume_id"])
            if resume:
                if s.get("rank"):
                    resume.pre_screen_rank = s["rank"]
                if s.get("relevance_score") is not None:
                    resume.relevance_score = s["relevance_score"]
        db.flush()

        # ── STAGE 2.5: Non-Negotiable Screening ─────────────────────
        non_negotiables = rubric.criteria.get("non_negotiables", [])
        nn_failed_count = 0

        if non_negotiables:
            logger.info(
                "[PIPELINE_V2] ── Stage 2.5: Non-Negotiable Screening (%d criteria) on %d resumes ──",
                len(non_negotiables), len(selected),
            )
            nn_input = [
                {
                    "resume_id": s["resume_id"],
                    "parsed_text": (resume_map.get(s["resume_id"]) or resume_map.get(str(s["resume_id"]), None)),
                }
                for s in selected
            ]
            # Build proper input with parsed_text from resume objects
            nn_input = []
            for s in selected:
                r = resume_map.get(s["resume_id"])
                if r:
                    nn_input.append({
                        "resume_id": str(r.id),
                        "parsed_text": r.parsed_text or "",
                    })

            nn_passed, nn_rejected = screen_non_negotiables_sync(
                resumes=nn_input,
                non_negotiables=non_negotiables,
            )

            # Update DB for non-negotiable failures
            for result in nn_rejected:
                resume = resume_map.get(result.resume_id)
                if resume:
                    resume.status = ResumeStatus.NON_NEGOTIABLE_FAILED
                    resume.rejection_reason = (
                        f"Failed non-negotiable criteria: {', '.join(result.failed_criteria)}"
                    )
                    resume.non_negotiable_results = result.details
            db.flush()

            nn_failed_count = len(nn_rejected)
            logger.info(
                "[PIPELINE_V2] Stage 2.5 DONE: %d passed | %d failed non-negotiables",
                len(nn_passed), nn_failed_count,
            )

            # Filter selected to only those that passed non-negotiables
            nn_passed_ids = {r["resume_id"] for r in nn_passed}
            selected = [s for s in selected if s["resume_id"] in nn_passed_ids]

            if not selected:
                db.commit()
                return {
                    "status": "BATCH_COMPLETED",
                    "batch_id": batch_id,
                    "scored_count": 0,
                    "failed_count": 0,
                    "pre_screened_count": len(pre_screened),
                    "quality_gate_failed_count": len(gate_rejected),
                    "non_negotiable_failed_count": nn_failed_count,
                }
        else:
            logger.info("[PIPELINE_V2] No non-negotiables defined — skipping Stage 2.5")

        # Mark remaining selected resumes as scoring in progress
        for s in selected:
            resume = resume_map.get(s["resume_id"])
            if resume:
                resume.status = ResumeStatus.SCORING_IN_PROGRESS
        db.flush()

        # ── STAGE 3: LLM Scoring ───────────────────────────────────
        logger.info(
            "[PIPELINE_V2] ── Stage 3: LLM Scoring on %d resumes ──", len(selected)
        )

        # Build resume objects for scoring
        selected_resume_objs = []
        for s in selected:
            resume = resume_map.get(s["resume_id"])
            if resume:
                selected_resume_objs.append(resume)

        # Extract candidate info
        from src.pipelines.extract_candidate_info import extract_candidate_info_sync
        candidate_infos: dict[str, CandidateInfoSchema] = {}
        # !Sequential candidate info extraction — one blocking Gemini call per resume in a for-loop
        for r in selected_resume_objs:
            try:
                ci = extract_candidate_info_sync(r.parsed_text or "")
                candidate_infos[str(r.id)] = ci
                pdlog.candidate_info(str(r.id), ci.full_name, ci.email, ci.phone, source="llm+heuristic")
            except Exception as e:
                logger.warning("[CANDIDATE_EXTRACT] Failed for resume=%s: %s", r.id, e)
                candidate_infos[str(r.id)] = CandidateInfoSchema()

        # Build LLM input (coerce UUIDs to str, guard None text)
        resume_payload = [
            ResumeDataSchema(
                application_id=str(r.application_id),
                resume_id=str(r.id),
                resume_text=r.parsed_text or "",
            )
            for r in selected_resume_objs
        ]

        score_results = score_resume_sync(
            resumes=resume_payload,
            criteria=rubric.criteria,
            candidate_infos=candidate_infos,
        )

        # Fetch applications
        applications = {
            a.id: a
            for a in db.execute(
                select(Application).where(
                    Application.id.in_({r.application_id for r in selected_resume_objs})
                )
            ).scalars()
        }

        # ── Persist scores ──────────────────────────────────────────
        for item in score_results:
            appl = applications.get(item.application_id)
            if appl:
                appl.ai_analysis = item.score.ai_analysis

            resume = resume_map.get(item.resume_id)
            if resume:
                resume.status = ResumeStatus.SCORED

            candidate_info = candidate_infos.get(str(item.resume_id), CandidateInfoSchema())

            if not candidate_info.full_name:
                inferred = extract_candidate_full_name((resume.parsed_text if resume else "") or "")
                if inferred:
                    candidate_info.full_name = inferred

            if candidate_info and (candidate_info.full_name or candidate_info.email or candidate_info.phone):
                enqueue_candidate_extraction(
                    resume_id=item.resume_id,
                    batch_id=batch_id,
                    candidate=candidate_info,
                )

            breakdown_data = item.score.breakdown
            if hasattr(breakdown_data, "model_dump"):
                breakdown_data = breakdown_data.model_dump()

            grounding_data = item.score.grounding_data
            if hasattr(grounding_data, "model_dump"):
                grounding_data = grounding_data.model_dump()
            if not isinstance(grounding_data, dict):
                grounding_data = {}

            if hasattr(item.score, "distinguishing_factors") and item.score.distinguishing_factors:
                grounding_data["distinguishing_factors"] = item.score.distinguishing_factors

            if candidate_info:
                grounding_data["candidate_info"] = {
                    "full_name": getattr(candidate_info, "full_name", None),
                    "email": getattr(candidate_info, "email", None),
                    "phone": getattr(candidate_info, "phone", None),
                }

            db.add(
                Score(
                    application_id=item.application_id,
                    rubric_id=rubric.id,
                    overall_score=item.score.overall_score,
                    raw_overall_score=item.score.raw_overall_score,
                    ai_confidence=item.score.ai_confidence,
                    breakdown=breakdown_data,
                    grounding_data=grounding_data,
                    scored_by="AI",
                    threshold_score=rubric.threshold_score,
                    criteria=rubric.criteria,
                    ai_model=os.environ.get("SCORING_MODEL", "Gemini-2.5-Flash"),
                    scoring_method=item.score.scoring_method,
                )
            )

            pdlog.scoring_final(
                resume_id=str(item.resume_id),
                overall_score=item.score.overall_score,
                section_scores=item.score.breakdown if isinstance(item.score.breakdown, dict) else {},
            )

        # Mark resumes that were selected but NOT scored (LLM failure) as ERROR
        scored_resume_ids = {str(item.resume_id) for item in score_results}
        for r in selected_resume_objs:
            if str(r.id) not in scored_resume_ids:
                r.status = ResumeStatus.ERROR
                r.rejection_reason = "LLM scoring failed"

        db.commit()

        scored_count = len(score_results)
        failed_count = len(selected_resume_objs) - scored_count

        logger.info(
            "[PIPELINE_V2] ══════════════════════════════════════════════════"
        )
        logger.info(
            "[PIPELINE_V2] COMPLETE  batch=%s  scored=%d  failed=%d  "
            "pre_screened=%d  gate_rejected=%d  nn_failed=%d",
            batch_id, scored_count, failed_count,
            len(pre_screened), len(gate_rejected), nn_failed_count,
        )
        logger.info(
            "[PIPELINE_V2] ══════════════════════════════════════════════════"
        )

        return {
            "status": "BATCH_COMPLETED",
            "batch_id": batch_id,
            "scored_count": scored_count,
            "failed_count": failed_count,
            "pre_screened_count": len(pre_screened),
            "quality_gate_failed_count": len(gate_rejected),
            "non_negotiable_failed_count": nn_failed_count,
        }


# WORKER TASKS BELOW - NOT API SERVICES
def score_resumes_service_sync(
    *,
    db_job_id: str,
    resume_ids: list[str],
    batch_id: str,
    redis_job_id: str | None = None
):
    from src.pipelines.score_resumes import score_resume_sync
    if not resume_ids:
        raise DomainError("Empty resume batch received")

    with get_sync_db() as db:
        
        logger.info(f"[SCORING] start: db_job_id={db_job_id} batch_id={batch_id} resume_count={len(resume_ids)}")

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
            
        

        # 3️⃣ Dedup: skip resumes that already have a score for this rubric
        already_scored = set()
        existing_scores = db.execute(
            select(Score.application_id).where(
                Score.rubric_id == rubric.id,
                Score.application_id.in_({r.application_id for r in resumes}),
                Score.is_active.is_(True),
            )
        ).scalars().all()
        already_scored = set(existing_scores)

        resumes_to_score = [r for r in resumes if r.application_id not in already_scored]

        if not resumes_to_score:
            logger.info(f"All resumes already scored for rubric {rubric.id}, skipping")
            return {
                "status": "BATCH_SKIPPED",
                "batch_id": batch_id,
                "scored_count": 0,
                "skipped_count": len(resumes),
            }

        # 4️⃣ Extract candidate info separately (Step 1 of 2-step pipeline)
        # Uses LLM with native structured output for name/email/phone.
        # Lazy import to avoid gRPC fork issues (same as score_resume_sync).
        from src.pipelines.extract_candidate_info import extract_candidate_info_sync

        resume_map = {r.id: r for r in resumes_to_score}
        candidate_infos: dict[str, CandidateInfoSchema] = {}

        for r in resumes_to_score:
            try:
                ci = extract_candidate_info_sync(r.parsed_text or "")
                candidate_infos[str(r.id)] = ci
                logger.info(
                    f"[CANDIDATE_EXTRACT] resume={r.id} name={ci.full_name!r} "
                    f"email={ci.email!r} phone={ci.phone!r}"
                )
                pdlog.candidate_info(str(r.id), ci.full_name, ci.email, ci.phone, source="llm+heuristic")
            except Exception as e:
                logger.warning(f"[CANDIDATE_EXTRACT] Failed for resume={r.id}: {e}")
                pdlog.error("candidate_extraction", str(r.id), str(e))
                candidate_infos[str(r.id)] = CandidateInfoSchema()

        # 5️⃣ Prepare LLM input for scoring (Step 2 of 2-step pipeline)
        resume_payload = [
            ResumeDataSchema(
                application_id=str(r.application_id),
                resume_id=str(r.id),
                resume_text=r.parsed_text or "",
            )
            for r in resumes_to_score
        ]

        # 6️⃣ ONE batch LLM scoring call (uses with_structured_output — native JSON mode)
        score_results = score_resume_sync(
            resumes=resume_payload,
            criteria=rubric.criteria,
            candidate_infos=candidate_infos,
        )

        applications = {
            a.id: a
            for a in db.execute(
                select(Application).where(
                    Application.id.in_(
                        {r.application_id for r in resumes_to_score}
                    )
                )
            ).scalars()
        }

        # Log final scores to debug file
        rubric_section_keys = [s.get("key", "") for s in (rubric.criteria.get("sections") or [])]
        for item in score_results:
            pdlog.scoring_final(
                resume_id=str(item.resume_id),
                overall_score=item.score.overall_score,
                section_scores=item.score.breakdown if isinstance(item.score.breakdown, dict) else {},
            )

        # 7️⃣ Persist results
        for item in score_results:
            appl = applications.get(item.application_id)
            if appl:
                appl.ai_analysis = item.score.ai_analysis

            resume = resume_map.get(item.resume_id)

            if resume:
                resume.status = ResumeStatus.SCORED

            # Use candidate info from Step 1 extraction
            candidate_info = candidate_infos.get(str(item.resume_id), CandidateInfoSchema())

            # Fallback to old heuristic if LLM extraction found nothing
            if not candidate_info.full_name:
                inferred = extract_candidate_full_name((resume.parsed_text if resume else "") or "")
                if inferred:
                    candidate_info.full_name = inferred

            if candidate_info and (candidate_info.full_name or candidate_info.email or candidate_info.phone):
                enqueue_candidate_extraction(
                    resume_id=item.resume_id,
                    batch_id=batch_id,
                    candidate=candidate_info,
                )

            # breakdown is already a dict (section_scores from post-processor)
            breakdown_data = item.score.breakdown
            if hasattr(breakdown_data, 'model_dump'):
                breakdown_data = breakdown_data.model_dump()

            grounding_data = item.score.grounding_data
            if hasattr(grounding_data, 'model_dump'):
                grounding_data = grounding_data.model_dump()
            if not isinstance(grounding_data, dict):
                grounding_data = {}

            # Store distinguishing_factors inside grounding_data for API access
            if hasattr(item.score, 'distinguishing_factors') and item.score.distinguishing_factors:
                grounding_data["distinguishing_factors"] = item.score.distinguishing_factors

            # Store extracted candidate_info so UI can show name/email/phone
            # even before candidate_extraction worker runs
            if candidate_info:
                grounding_data["candidate_info"] = {
                    "full_name": getattr(candidate_info, "full_name", None),
                    "email": getattr(candidate_info, "email", None),
                    "phone": getattr(candidate_info, "phone", None),
                }

            db.add(
                Score(
                    application_id=item.application_id,
                    rubric_id=rubric.id,
                    overall_score=item.score.overall_score,
                    raw_overall_score=item.score.raw_overall_score,
                    ai_confidence=item.score.ai_confidence,
                    breakdown=breakdown_data,
                    grounding_data=grounding_data,
                    scored_by="AI",
                    threshold_score=rubric.threshold_score,
                    criteria=rubric.criteria,
                    ai_model=os.environ.get("SCORING_MODEL", "Gemini-2.5-Flash"),
                    scoring_method=item.score.scoring_method,
                )
            )

        db.commit()

        scored_count = len(score_results)
        failed_count = len(resumes_to_score) - scored_count

        if failed_count > 0:
            logger.warning(
                f"[SCORING] batch={batch_id}: {failed_count}/{len(resumes_to_score)} "
                f"resumes failed LLM scoring (silently skipped)"
            )

        return {
            "status": "BATCH_COMPLETED",
            "batch_id": batch_id,
            "scored_count": scored_count,
            "failed_count": failed_count,
            "total_in_batch": len(resumes_to_score),
        }


# WORKER
def extract_candidate_service(
    resume_id: str,
    candidate_info: CandidateInfoSchema | None
):
    if not candidate_info:
        raise ValueError("Candidate info is missing")

    with get_sync_db() as db:

        logger.info(f"[CANDIDATE] extract for resume_id={resume_id}")

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


# =============================================================================
# Async Worker Service — used by ARQ async_workers
# =============================================================================

class ResumeService_ForWorker:
    """
    Async resume service for ARQ workers.
    Provides async versions of parse/score operations using the async DB session.
    """

    def __init__(
        self,
        db: AsyncSession,
        resume_repository,
        score_repository,
        job_producer,
        application_repository,
        batch_repository,
        document_repository,
        job_repository,
    ):
        self.db = db
        self.resume_repository = resume_repository
        self.score_repository = score_repository
        self.job_producer = job_producer
        self.application_repository = application_repository
        self.batch_repository = batch_repository
        self.document_repository = document_repository
        self.job_repository = job_repository

    async def parse_resume(self, file_path: str, batch_id: str):
        """
        Parse a resume from Supabase storage (async version).
        file_path: storage path e.g. "resumes/job_id/filename.pdf"
        """
        file_name = os.path.basename(file_path)
        logger.info(f"[SERVICE] parse_resume START: file={file_name} batch={batch_id}")

        tmp_path = None
        try:
            # Download from Supabase (sync I/O -> thread)
            logger.info(f"[SERVICE] Downloading from Supabase: {file_path}")
            tmp_path = await asyncio.to_thread(download_to_tempfile, file_path)

            # Extract text (sync I/O -> thread)
            logger.info(f"[SERVICE] Extracting text from: {file_name}")
            parsed_text, page_count, extraction_method = await asyncio.to_thread(
                extract_text_from_file_sync, tmp_path
            )
            logger.info(
                f"[SERVICE] Extracted: file={file_name} pages={page_count} "
                f"method={extraction_method} chars={len(parsed_text)}"
            )

            # Fetch batch
            batch_result = await self.db.execute(
                select(BulkUploadBatches).where(BulkUploadBatches.id == batch_id)
            )
            batch = batch_result.scalar_one_or_none()

            if not batch:
                raise ValueError(f"Batch {batch_id} not found in DB")

            job_id = batch.job_id
            logger.info(f"[SERVICE] Batch found: job_id={job_id} total_files={batch.total_files}")

            # Create Application
            application = Application(job_id=job_id)
            self.db.add(application)
            await self.db.flush()
            logger.info(f"[SERVICE] Application created: id={application.id}")

            # Create Resume
            resume = Resume(
                application_id=application.id,
                raw_file_url=file_path,
                parsed_text=parsed_text,
                page_count=page_count,
                extraction_method=extraction_method,
                status=ResumeStatus.PARSED,
            )
            self.db.add(resume)
            await self.db.flush()
            logger.info(f"[SERVICE] Resume created: id={resume.id}")

            # Create Document
            mime_type, _ = mimetypes.guess_type(file_name)
            mime_type = mime_type or "application/pdf"
            file_size = await asyncio.to_thread(os.path.getsize, tmp_path)

            document = Document(
                entity_type="resume",
                entity_id=resume.id,
                document_type="Resume",
                file_name=file_name,
                file_size_bytes=file_size,
                mime_type=mime_type,
                storage_provider="supabase",
                file_path=file_path,
                file_url=f"{SUPABASE_PUBLIC_URL}/{file_path}",
                extracted_text=parsed_text,
                parsing_status=DocumentProcessingStatus.PARSED.value,
            )
            self.db.add(document)

            # Update application and batch
            application.current_resume_id = resume.id
            batch.success_count += 1

            results = batch.processing_results or {}
            results[file_name] = f"parsed successfully (method={extraction_method})"
            batch.processing_results = results

            await self.db.commit()
            logger.info(
                f"[SERVICE] DB committed: file={file_name} "
                f"batch success_count={batch.success_count}/{batch.total_files}"
            )

        except Exception as e:
            logger.error(f"[SERVICE] parse_resume FAILED: file={file_name} error={e!r}")
            await self.db.rollback()
            raise

        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    async def score_parsed_text_resumes(
        self,
        db_job_id: str,
        resume_ids: list[str],
        batch_id: str,
    ):
        """Score resumes that have parsed text (async version for ARQ workers)."""
        from src.pipelines.score_resumes import score_resume_async
        if not resume_ids:
            raise DomainError("Empty resume batch received")

        try:
            logger.info(
                f"[SCORING] start: db_job_id={db_job_id} batch_id={batch_id} "
                f"resume_count={len(resume_ids)}"
            )

            # Fetch job
            job_result = await self.db.execute(
                select(Job).where(Job.id == db_job_id)
            )
            job = job_result.scalar_one_or_none()
            if not job:
                raise DomainError(f"Job {db_job_id} not found or not active")

            # Fetch resumes in this batch
            result = await self.db.execute(
                select(Resume)
                .join(Application, Resume.application_id == Application.id)
                .where(
                    Application.job_id == db_job_id,
                    Resume.id.in_(resume_ids),
                    Resume.status == ResumeStatus.QUEUED_FOR_SCORING,
                )
            )
            resumes = result.scalars().all()

            if not resumes:
                raise DomainError(f"No parsed resumes found for batch {batch_id}")

            # Fetch active rubric
            rubric_result = await self.db.execute(
                select(Rubric).where(
                    Rubric.job_id == db_job_id,
                    Rubric.is_active.is_(True),
                )
            )
            rubric = rubric_result.scalar_one_or_none()
            if not rubric:
                raise DomainError(f"No active rubric found for job {db_job_id}")

            # Dedup: skip resumes already scored for this rubric
            existing_scores_result = await self.db.execute(
                select(Score.application_id).where(
                    Score.rubric_id == rubric.id,
                    Score.application_id.in_({r.application_id for r in resumes}),
                    Score.is_active.is_(True),
                )
            )
            already_scored = set(existing_scores_result.scalars().all())

            resumes_to_score = [
                r for r in resumes if r.application_id not in already_scored
            ]

            if not resumes_to_score:
                logger.info(f"All resumes already scored for rubric {rubric.id}, skipping")
                return

            # Step 1: Extract candidate info separately
            from src.pipelines.extract_candidate_info import extract_candidate_info_async

            resume_map = {r.id: r for r in resumes_to_score}
            candidate_infos: dict[str, CandidateInfoSchema] = {}

            for r in resumes_to_score:
                try:
                    ci = await extract_candidate_info_async(r.parsed_text or "")
                    candidate_infos[str(r.id)] = ci
                except Exception as e:
                    logger.warning(f"[CANDIDATE_EXTRACT] Failed for resume={r.id}: {e}")
                    candidate_infos[str(r.id)] = CandidateInfoSchema()

            # Step 2: Prepare LLM input for scoring
            resume_payload = [
                ResumeDataSchema(
                    application_id=r.application_id,
                    resume_id=r.id,
                    resume_text=r.parsed_text,
                )
                for r in resumes_to_score
            ]

            # Step 3: Async LLM scoring (uses with_structured_output — native JSON mode)
            score_results = await score_resume_async(
                resumes=resume_payload,
                criteria=rubric.criteria,
                candidate_infos=candidate_infos,
            )

            # Fetch applications for updating ai_analysis
            app_result = await self.db.execute(
                select(Application).where(
                    Application.id.in_(
                        {r.application_id for r in resumes_to_score}
                    )
                )
            )
            applications = {a.id: a for a in app_result.scalars()}

            # Persist results
            for item in score_results:
                # score_resume_async returns dicts
                if isinstance(item, dict) and "error" in item:
                    logger.error(
                        f"Scoring failed for resume_id={item.get('resume_id')}: "
                        f"{item['error']}"
                    )
                    continue

                app_id = item["application_id"]
                resume_id = item["resume_id"]
                score_output = item["score"]

                appl = applications.get(app_id)
                if appl:
                    appl.ai_analysis = score_output.ai_analysis

                # Use candidate info from Step 1
                candidate_info = candidate_infos.get(str(resume_id), CandidateInfoSchema())

                # Fallback to heuristic if LLM extraction found nothing
                if not candidate_info.full_name:
                    resume_obj = resume_map.get(resume_id)
                    inferred = extract_candidate_full_name((resume_obj.parsed_text if resume_obj else "") or "")
                    if inferred:
                        candidate_info.full_name = inferred

                if candidate_info and (candidate_info.full_name or candidate_info.email or candidate_info.phone):
                    await self.job_producer.enqueue_candidate_extraction(
                        resume_id=str(resume_id),
                        candidate=candidate_info,
                        batch_id=batch_id,
                    )

                resume = resume_map.get(resume_id)
                if resume:
                    resume.status = ResumeStatus.SCORED

                breakdown_data = score_output.breakdown
                if hasattr(breakdown_data, 'model_dump'):
                    breakdown_data = breakdown_data.model_dump()

                grounding_data = score_output.grounding_data
                if hasattr(grounding_data, 'model_dump'):
                    grounding_data = grounding_data.model_dump()
                if not isinstance(grounding_data, dict):
                    grounding_data = {}

                if hasattr(score_output, 'distinguishing_factors') and score_output.distinguishing_factors:
                    grounding_data["distinguishing_factors"] = score_output.distinguishing_factors

                if candidate_info:
                    grounding_data["candidate_info"] = {
                        "full_name": getattr(candidate_info, "full_name", None),
                        "email": getattr(candidate_info, "email", None),
                        "phone": getattr(candidate_info, "phone", None),
                    }

                self.db.add(
                    Score(
                        application_id=app_id,
                        rubric_id=rubric.id,
                        overall_score=score_output.overall_score,
                        raw_overall_score=getattr(score_output, 'raw_overall_score', None),
                        ai_confidence=score_output.ai_confidence,
                        breakdown=breakdown_data,
                        grounding_data=grounding_data,
                        scored_by="AI",
                        threshold_score=rubric.threshold_score,
                        criteria=rubric.criteria,
                        ai_model=os.environ.get("SCORING_MODEL", "Gemini-2.5-Flash"),
                        scoring_method=getattr(score_output, 'scoring_method', "weighted_v2"),
                    )
                )

            await self.db.commit()

            scored_count = sum(
                1 for item in score_results
                if not (isinstance(item, dict) and "error" in item)
            )
            failed_count = len(resumes_to_score) - scored_count

            if failed_count > 0:
                logger.warning(
                    f"[SCORING] batch={batch_id}: {failed_count}/{len(resumes_to_score)} "
                    f"resumes failed LLM scoring (silently skipped)"
                )

            logger.info(f"[SCORING] batch={batch_id} completed: scored={scored_count}")

        except Exception:
            await self.db.rollback()
            raise

    async def score_url_resumes(
        self,
        db_job_id: str,
        resume_ids: list[str],
        batch_id: str,
    ):
        """
        Score resumes that don't have parsed text yet.
        Downloads from URL, extracts text, then scores.
        """
        if not resume_ids:
            raise DomainError("Empty resume batch received")

        try:
            # Fetch resumes
            result = await self.db.execute(
                select(Resume)
                .join(Application, Resume.application_id == Application.id)
                .where(
                    Application.job_id == db_job_id,
                    Resume.id.in_(resume_ids),
                    Resume.status == ResumeStatus.QUEUED_FOR_SCORING,
                )
            )
            resumes = result.scalars().all()

            if not resumes:
                raise DomainError(f"No resumes found for batch {batch_id}")

            # Download and extract text for resumes that don't have it
            for resume in resumes:
                if resume.parsed_text and resume.parsed_text.strip():
                    continue

                if not resume.raw_file_url:
                    logger.warning(f"Resume {resume.id} has no URL or text, skipping")
                    continue

                tmp_path = await asyncio.to_thread(
                    download_to_tempfile, resume.raw_file_url
                )
                try:
                    parsed_text, page_count, extraction_method = await asyncio.to_thread(
                        extract_text_from_file_sync, tmp_path
                    )
                    resume.parsed_text = parsed_text
                    resume.page_count = page_count
                    resume.extraction_method = extraction_method
                finally:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

            await self.db.flush()

            # Now score using the same method as text resumes
            await self.score_parsed_text_resumes(
                db_job_id=db_job_id,
                resume_ids=resume_ids,
                batch_id=batch_id,
            )

        except DomainError:
            raise
        except Exception:
            await self.db.rollback()
            raise
