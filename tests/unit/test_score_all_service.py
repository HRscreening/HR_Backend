"""
Unit tests for score_all_service — enqueue scoring for all parsed resumes of a job.

Covers:
  - No parsed resumes → raises DomainError
  - No active rubric  → raises DomainError
  - Success → calls enqueue_resumes_scoring with correct resume IDs, returns batch info
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.services.resume_services import score_all_service
from src.services.errors.base import DomainError


JOB_ID = str(uuid4())
RESUME_ID_1 = str(uuid4())
RESUME_ID_2 = str(uuid4())
RUBRIC_ID = str(uuid4())


def _mock_resume(resume_id: str):
    r = MagicMock()
    r.id = resume_id
    return r


def _mock_rubric():
    rubric = MagicMock()
    rubric.id = RUBRIC_ID
    return rubric


def _make_db(resumes=None, rubric=None):
    """Build a mock AsyncSession that returns given resumes + rubric on execute."""
    db = AsyncMock()

    resume_result = MagicMock()
    resume_result.scalars.return_value.all.return_value = resumes or []

    rubric_result = MagicMock()
    rubric_result.scalar_one_or_none.return_value = rubric

    db.execute = AsyncMock(side_effect=[resume_result, rubric_result])
    return db


# ── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_score_all_raises_when_no_parsed_resumes():
    db = _make_db(resumes=[], rubric=_mock_rubric())

    with pytest.raises(DomainError, match="No parsed resumes"):
        await score_all_service(job_id=JOB_ID, db=db)


@pytest.mark.asyncio
async def test_score_all_raises_when_no_active_rubric():
    resumes = [_mock_resume(RESUME_ID_1)]
    db = _make_db(resumes=resumes, rubric=None)

    with pytest.raises(DomainError, match="No active rubric"):
        await score_all_service(job_id=JOB_ID, db=db)


@pytest.mark.asyncio
async def test_score_all_enqueues_all_parsed_resumes():
    resumes = [_mock_resume(RESUME_ID_1), _mock_resume(RESUME_ID_2)]
    db = _make_db(resumes=resumes, rubric=_mock_rubric())

    fake_batch_ids = [str(uuid4())]

    with patch(
        "src.services.resume_services.enqueue_resumes_scoring",
        return_value=fake_batch_ids,
    ) as mock_enqueue:
        result = await score_all_service(job_id=JOB_ID, db=db)

    mock_enqueue.assert_called_once_with(
        job_id=JOB_ID,
        resume_ids=[RESUME_ID_1, RESUME_ID_2],
    )
    assert result["enqueued_count"] == 2
    assert result["batch_ids"] == fake_batch_ids


@pytest.mark.asyncio
async def test_score_all_returns_correct_structure():
    resumes = [_mock_resume(RESUME_ID_1)]
    db = _make_db(resumes=resumes, rubric=_mock_rubric())

    fake_batch_ids = [str(uuid4()), str(uuid4())]

    with patch(
        "src.services.resume_services.enqueue_resumes_scoring",
        return_value=fake_batch_ids,
    ):
        result = await score_all_service(job_id=JOB_ID, db=db)

    assert "enqueued_count" in result
    assert "batch_ids" in result
    assert "message" in result
    assert result["enqueued_count"] == 1
