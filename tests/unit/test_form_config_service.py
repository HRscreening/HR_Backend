"""
Unit tests for FormConfigService business logic.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.services.form_config_service import (
    FormConfigService,
    FormConfigNotFound,
    FormConfigNotEditable,
)
from src.services.errors.user_errors import JobNotFound
from src.schemas.public_apply_schemas import FormQuestionSchema


# ── Fixtures ───────────────────────────────────────────────────────────────────

JOB_ID = uuid4()
CONFIG_ID = uuid4()
USER_ID = uuid4()
ORG_ID = uuid4()


def _mock_job():
    job = MagicMock()
    job.id = JOB_ID
    job.organization_id = ORG_ID
    return job


def _mock_config(status="draft", config_id=None):
    config = MagicMock()
    config.id = config_id or CONFIG_ID
    config.job_id = JOB_ID
    config.version_number = 1
    config.status = status
    config.questions = []
    return config


def _make_service(form_config_repo=None, job_repo=None, db=None):
    form_config_repo = form_config_repo or AsyncMock()
    job_repo = job_repo or AsyncMock()
    db = db or AsyncMock()
    return FormConfigService(
        form_config_repository=form_config_repo,
        job_repository=job_repo,
        db=db,
    )


def _core_questions():
    return [
        FormQuestionSchema(id="q_full_name", key="full_name", label="Full Name", type="text", required=True, removable=False),
        FormQuestionSchema(id="q_email", key="email", label="Email", type="email", required=True, removable=False),
        FormQuestionSchema(id="q_resume", key="resume", label="Resume", type="file", required=True, removable=False),
    ]


# ── get_or_create_form_config ─────────────────────────────────────────────────

class TestGetOrCreateFormConfig:
    @pytest.mark.asyncio
    async def test_raises_job_not_found(self):
        job_repo = AsyncMock()
        job_repo.get_job_by_id.return_value = None

        service = _make_service(job_repo=job_repo)
        with pytest.raises(JobNotFound):
            await service.get_or_create_form_config(JOB_ID, USER_ID)

    @pytest.mark.asyncio
    async def test_returns_active_config_if_exists(self):
        job_repo = AsyncMock()
        job_repo.get_job_by_id.return_value = _mock_job()

        active_config = _mock_config(status="active")
        form_config_repo = AsyncMock()
        form_config_repo.get_active.return_value = active_config

        service = _make_service(form_config_repo=form_config_repo, job_repo=job_repo)

        with MagicMock() as mock_resp_cls:
            from unittest.mock import patch
            with patch("src.services.form_config_service.ApplicationFormConfigResponse") as m:
                m.model_validate.return_value = MagicMock(id=CONFIG_ID, status="active")
                result = await service.get_or_create_form_config(JOB_ID, USER_ID)

        # Should not create a new config
        form_config_repo.create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_creates_default_config_if_none_exists(self):
        job_repo = AsyncMock()
        job_repo.get_job_by_id.return_value = _mock_job()

        form_config_repo = AsyncMock()
        form_config_repo.get_active.return_value = None
        form_config_repo.get_latest.return_value = None
        new_config = _mock_config(status="draft")
        form_config_repo.create.return_value = new_config

        db = AsyncMock()
        db.refresh = AsyncMock()

        service = _make_service(form_config_repo=form_config_repo, job_repo=job_repo, db=db)

        from unittest.mock import patch
        with patch("src.services.form_config_service.ApplicationFormConfigResponse") as m:
            m.model_validate.return_value = MagicMock(id=CONFIG_ID, status="draft")
            await service.get_or_create_form_config(JOB_ID, USER_ID)

        form_config_repo.create.assert_awaited_once_with(
            job_id=JOB_ID,
            organization_id=ORG_ID,
            created_by_id=USER_ID,
        )
        db.commit.assert_awaited_once()


# ── update_form_config ────────────────────────────────────────────────────────

class TestUpdateFormConfig:
    @pytest.mark.asyncio
    async def test_raises_not_found(self):
        form_config_repo = AsyncMock()
        form_config_repo.get_by_id_and_job.return_value = None

        service = _make_service(form_config_repo=form_config_repo)
        with pytest.raises(FormConfigNotFound):
            await service.update_form_config(CONFIG_ID, JOB_ID, _core_questions())

    @pytest.mark.asyncio
    async def test_raises_not_editable_for_active_config(self):
        form_config_repo = AsyncMock()
        form_config_repo.get_by_id_and_job.return_value = _mock_config(status="active")

        service = _make_service(form_config_repo=form_config_repo)
        with pytest.raises(FormConfigNotEditable):
            await service.update_form_config(CONFIG_ID, JOB_ID, _core_questions())

    @pytest.mark.asyncio
    async def test_raises_not_editable_for_archived_config(self):
        form_config_repo = AsyncMock()
        form_config_repo.get_by_id_and_job.return_value = _mock_config(status="archived")

        service = _make_service(form_config_repo=form_config_repo)
        with pytest.raises(FormConfigNotEditable):
            await service.update_form_config(CONFIG_ID, JOB_ID, _core_questions())

    @pytest.mark.asyncio
    async def test_updates_draft_config(self):
        form_config_repo = AsyncMock()
        form_config_repo.get_by_id_and_job.return_value = _mock_config(status="draft")
        form_config_repo.get_by_id.return_value = _mock_config(status="draft")

        db = AsyncMock()
        service = _make_service(form_config_repo=form_config_repo, db=db)
        questions = _core_questions()

        from unittest.mock import patch
        with patch("src.services.form_config_service.ApplicationFormConfigResponse") as m:
            m.model_validate.return_value = MagicMock()
            await service.update_form_config(CONFIG_ID, JOB_ID, questions)

        form_config_repo.update_questions.assert_awaited_once()
        db.commit.assert_awaited_once()
        # Verify questions are serialised correctly
        call_args = form_config_repo.update_questions.call_args
        assert call_args[0][0] == CONFIG_ID


# ── activate_form_config ──────────────────────────────────────────────────────

class TestActivateFormConfig:
    @pytest.mark.asyncio
    async def test_raises_not_found(self):
        form_config_repo = AsyncMock()
        form_config_repo.get_by_id_and_job.return_value = None

        service = _make_service(form_config_repo=form_config_repo)
        with pytest.raises(FormConfigNotFound):
            await service.activate_form_config(CONFIG_ID, JOB_ID)

    @pytest.mark.asyncio
    async def test_archives_old_and_activates_new(self):
        form_config_repo = AsyncMock()
        form_config_repo.get_by_id_and_job.return_value = _mock_config(status="draft")
        form_config_repo.get_by_id.return_value = _mock_config(status="active")

        db = AsyncMock()
        service = _make_service(form_config_repo=form_config_repo, db=db)

        from unittest.mock import patch
        with patch("src.services.form_config_service.ApplicationFormConfigResponse") as m:
            m.model_validate.return_value = MagicMock(status="active")
            await service.activate_form_config(CONFIG_ID, JOB_ID)

        form_config_repo.archive_active.assert_awaited_once_with(JOB_ID)
        form_config_repo.set_status.assert_awaited_once_with(CONFIG_ID, "active")
        form_config_repo.set_active_form_config_on_job.assert_awaited_once_with(JOB_ID, CONFIG_ID)
        db.commit.assert_awaited_once()
