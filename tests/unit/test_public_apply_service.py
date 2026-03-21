"""
Unit tests for PublicApplyService — major functionality.

Covers:
  - _resolve_slug: not found, job closed, success
  - _check_duplicate: duplicate raises, non-duplicate passes
  - _find_or_create_candidate: finds existing, creates new
  - _validate_resume_file: bad extension, oversized, valid
"""

import io
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.services.public_apply_service import (
    PublicApplyService,
    PublicApplyJobNotFound,
    PublicApplyJobClosed,
    DuplicateApplication,
    InvalidResumeFile,
)
from src.schemas.public_apply_schemas import PublicApplyRequest


# ── Fixtures ────────────────────────────────────────────────────────────────────

JOB_ID = uuid4()
CANDIDATE_ID = uuid4()
APPLICATION_ID = uuid4()
ORG_ID = uuid4()
USER_ID = uuid4()


def _mock_job(status="OPEN", public_apply_enabled=True):
    job = MagicMock()
    job.id = JOB_ID
    job.organization_id = ORG_ID
    job.created_by_id = USER_ID
    job.status = status
    job.public_apply_enabled = public_apply_enabled
    job.public_slug = "test-role-abc123"
    job.title = "Software Engineer"
    job.location = "Remote"
    job.description = "A great role."
    job.organization = MagicMock(name="Acme Corp")
    return job


def _mock_candidate():
    c = MagicMock()
    c.id = CANDIDATE_ID
    return c


def _make_upload_file(filename="resume.pdf", content=b"PDF content"):
    f = AsyncMock()
    f.filename = filename
    f.read = AsyncMock(return_value=content)
    f.seek = AsyncMock()
    return f


def _make_service(
    job_repo=None,
    jd_repo=None,
    form_config_repo=None,
    candidate_repo=None,
    file_manager=None,
    db=None,
):
    return PublicApplyService(
        job_repository=job_repo or AsyncMock(),
        jd_repository=jd_repo or AsyncMock(),
        form_config_repository=form_config_repo or AsyncMock(),
        candidate_repository=candidate_repo or AsyncMock(),
        file_manager=file_manager or MagicMock(),
        db=db or AsyncMock(),
    )


def _make_form_data(**kwargs):
    defaults = {"full_name": "Jane Doe", "email": "jane@example.com"}
    return PublicApplyRequest(**{**defaults, **kwargs})


# ── _resolve_slug ──────────────────────────────────────────────────────────────

class TestResolveSlug:
    @pytest.mark.asyncio
    async def test_raises_not_found_when_no_job(self):
        db = AsyncMock()
        # scalar_one_or_none returns None → job not found
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        service = _make_service(db=db)
        with pytest.raises(PublicApplyJobNotFound):
            await service._resolve_slug("nonexistent-slug")

    @pytest.mark.asyncio
    async def test_raises_job_closed_when_status_not_open(self):
        db = AsyncMock()
        job = _mock_job(status="CLOSED")
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = job
        db.execute = AsyncMock(return_value=result_mock)

        service = _make_service(db=db)
        with pytest.raises(PublicApplyJobClosed):
            await service._resolve_slug("test-role-abc123")

    @pytest.mark.asyncio
    async def test_returns_open_job(self):
        db = AsyncMock()
        job = _mock_job(status="OPEN")
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = job
        db.execute = AsyncMock(return_value=result_mock)

        service = _make_service(db=db)
        result = await service._resolve_slug("test-role-abc123")
        assert result is job

    @pytest.mark.asyncio
    async def test_raises_closed_for_lowercase_open_variant(self):
        """Ensure only 'OPEN'/'open'/JobStatus.OPEN pass — any other string is closed."""
        db = AsyncMock()
        job = _mock_job(status="DRAFT")
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = job
        db.execute = AsyncMock(return_value=result_mock)

        service = _make_service(db=db)
        with pytest.raises(PublicApplyJobClosed):
            await service._resolve_slug("test-role-abc123")


# ── _check_duplicate ───────────────────────────────────────────────────────────

class TestCheckDuplicate:
    @pytest.mark.asyncio
    async def test_raises_on_existing_application(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = APPLICATION_ID  # found
        db.execute = AsyncMock(return_value=result_mock)

        service = _make_service(db=db)
        with pytest.raises(DuplicateApplication):
            await service._check_duplicate(email="jane@example.com", job_id=JOB_ID)

    @pytest.mark.asyncio
    async def test_passes_when_no_existing_application(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None  # not found
        db.execute = AsyncMock(return_value=result_mock)

        service = _make_service(db=db)
        # Should not raise
        await service._check_duplicate(email="new@example.com", job_id=JOB_ID)


# ── _find_or_create_candidate ─────────────────────────────────────────────────

class TestFindOrCreateCandidate:
    @pytest.mark.asyncio
    async def test_returns_existing_candidate(self):
        candidate_repo = AsyncMock()
        existing = _mock_candidate()
        candidate_repo.get_candidate_by_email.return_value = existing

        service = _make_service(candidate_repo=candidate_repo)
        form_data = _make_form_data()
        result = await service._find_or_create_candidate(form_data, org_id=ORG_ID)

        assert result is existing
        candidate_repo.create_candidate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_creates_new_candidate_when_not_found(self):
        candidate_repo = AsyncMock()
        candidate_repo.get_candidate_by_email.return_value = None
        new_candidate = _mock_candidate()
        candidate_repo.create_candidate.return_value = new_candidate

        service = _make_service(candidate_repo=candidate_repo)
        form_data = _make_form_data()
        result = await service._find_or_create_candidate(form_data, org_id=ORG_ID)

        assert result is new_candidate
        candidate_repo.create_candidate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_passes_none_org_id_correctly(self):
        candidate_repo = AsyncMock()
        candidate_repo.get_candidate_by_email.return_value = None
        candidate_repo.create_candidate.return_value = _mock_candidate()

        service = _make_service(candidate_repo=candidate_repo)
        form_data = _make_form_data()
        await service._find_or_create_candidate(form_data, org_id=None)

        # org_id=None should be passed as None (not as string "None")
        call_kwargs = candidate_repo.create_candidate.call_args[1]
        assert call_kwargs["org_id"] is None


# ── _validate_resume_file ─────────────────────────────────────────────────────

class TestValidateResumeFile:
    @pytest.mark.asyncio
    async def test_raises_for_unsupported_extension(self):
        f = _make_upload_file(filename="resume.txt")
        service = _make_service()
        with pytest.raises(InvalidResumeFile):
            await service._validate_resume_file(f)

    @pytest.mark.asyncio
    async def test_raises_for_missing_filename(self):
        f = _make_upload_file(filename="")
        f.filename = ""
        service = _make_service()
        with pytest.raises(InvalidResumeFile):
            await service._validate_resume_file(f)

    @pytest.mark.asyncio
    async def test_raises_for_oversized_file(self):
        # 6 MB — over the 5 MB limit
        big_content = b"x" * (6 * 1024 * 1024)
        f = _make_upload_file(filename="resume.pdf", content=big_content)
        service = _make_service()
        with pytest.raises(InvalidResumeFile):
            await service._validate_resume_file(f)

    @pytest.mark.asyncio
    async def test_accepts_pdf(self):
        f = _make_upload_file(filename="resume.pdf", content=b"small pdf")
        service = _make_service()
        await service._validate_resume_file(f)  # should not raise

    @pytest.mark.asyncio
    async def test_accepts_docx(self):
        f = _make_upload_file(filename="cv.docx", content=b"docx bytes")
        service = _make_service()
        await service._validate_resume_file(f)  # should not raise

    @pytest.mark.asyncio
    async def test_accepts_doc(self):
        f = _make_upload_file(filename="resume.doc", content=b"doc bytes")
        service = _make_service()
        await service._validate_resume_file(f)  # should not raise

    @pytest.mark.asyncio
    async def test_extension_check_is_case_insensitive(self):
        f = _make_upload_file(filename="Resume.PDF", content=b"pdf bytes")
        service = _make_service()
        await service._validate_resume_file(f)  # .PDF should be allowed
