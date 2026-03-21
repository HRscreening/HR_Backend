"""
Unit tests for JDService business logic.

Uses unittest.mock to isolate service from DB/repositories.
Tests focus on the state-machine rules and orchestration logic.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.services.jd_service import (
    JDService,
    JDNotFound,
    JDNotEditable,
    JDCannotDeleteActive,
    PublicLinkMissingActiveJD,
    PublicLinkMissingFormConfig,
    PublicSlugAlreadyTaken,
    _generate_slug,
)
from src.services.errors.user_errors import JobNotFound


# ── Fixtures ───────────────────────────────────────────────────────────────────

JOB_ID = uuid4()
JD_ID = uuid4()
USER_ID = uuid4()
ORG_ID = uuid4()
CONFIG_ID = uuid4()


def _mock_jd(status="draft", version=1, jd_id=None):
    jd = MagicMock()
    jd.id = jd_id or JD_ID
    jd.job_id = JOB_ID
    jd.version_number = version
    jd.status = status
    jd.title = "Backend Engineer"
    jd.content = "## Role\nWe are looking..."
    jd.generation_method = "manual"
    jd.raw_answers = None
    jd.created_by_id = USER_ID
    return jd


def _mock_job(active_jd_id=None, public_slug=None, public_apply_enabled=False, title="Backend Engineer"):
    job = MagicMock()
    job.id = JOB_ID
    job.organization_id = ORG_ID
    job.title = title
    job.active_jd_id = active_jd_id
    job.public_slug = public_slug
    job.public_apply_enabled = public_apply_enabled
    return job


def _mock_form_config(status="active"):
    config = MagicMock()
    config.id = CONFIG_ID
    config.job_id = JOB_ID
    config.status = status
    return config


def _make_service(jd_repo=None, form_config_repo=None, job_repo=None, db=None):
    jd_repo = jd_repo or AsyncMock()
    form_config_repo = form_config_repo or AsyncMock()
    job_repo = job_repo or AsyncMock()
    db = db or AsyncMock()
    return JDService(
        jd_repository=jd_repo,
        form_config_repository=form_config_repo,
        job_repository=job_repo,
        db=db,
    )


# ── _generate_slug ─────────────────────────────────────────────────────────────

class TestGenerateSlug:
    def test_contains_title_words(self):
        slug = _generate_slug("Senior Backend Engineer")
        assert "senior" in slug
        assert "backend" in slug
        assert "engineer" in slug

    def test_ends_with_6_char_suffix(self):
        slug = _generate_slug("Engineer")
        parts = slug.rsplit("-", 1)
        assert len(parts) == 2
        assert len(parts[1]) == 6

    def test_lowercase_only(self):
        slug = _generate_slug("SENIOR BACKEND ENGINEER")
        assert slug == slug.lower()

    def test_no_spaces(self):
        slug = _generate_slug("Senior Backend Engineer")
        assert " " not in slug

    def test_special_chars_replaced(self):
        slug = _generate_slug("C++ / Python Developer")
        assert "/" not in slug
        assert "+" not in slug

    def test_different_calls_produce_different_slugs(self):
        slugs = {_generate_slug("Backend Engineer") for _ in range(20)}
        # 6-char random suffix → statistically almost impossible to collide 20 times
        assert len(slugs) > 1


# ── create_jd ─────────────────────────────────────────────────────────────────

class TestCreateJD:
    @pytest.mark.asyncio
    async def test_raises_job_not_found_if_job_missing(self):
        job_repo = AsyncMock()
        job_repo.get_job_by_id.return_value = None

        service = _make_service(job_repo=job_repo)
        with pytest.raises(JobNotFound):
            await service.create_jd(JOB_ID, "Title", "Content", USER_ID, ORG_ID)

    @pytest.mark.asyncio
    async def test_creates_jd_and_returns_response(self):
        job_repo = AsyncMock()
        job_repo.get_job_by_id.return_value = _mock_job()

        jd_repo = AsyncMock()
        jd = _mock_jd()
        jd_repo.create.return_value = jd

        db = AsyncMock()
        db.refresh = AsyncMock()

        service = _make_service(jd_repo=jd_repo, job_repo=job_repo, db=db)

        with patch("src.services.jd_service.JDVersionResponse") as mock_resp:
            mock_resp.model_validate.return_value = MagicMock(id=JD_ID)
            result = await service.create_jd(JOB_ID, "Title", "Content", USER_ID, ORG_ID)

        jd_repo.create.assert_awaited_once()
        db.commit.assert_awaited_once()


# ── activate_jd ───────────────────────────────────────────────────────────────

class TestActivateJD:
    @pytest.mark.asyncio
    async def test_raises_jd_not_found(self):
        jd_repo = AsyncMock()
        jd_repo.get_by_id_and_job.return_value = None

        service = _make_service(jd_repo=jd_repo)
        with pytest.raises(JDNotFound):
            await service.activate_jd(JD_ID, JOB_ID)

    @pytest.mark.asyncio
    async def test_archives_old_and_activates_new(self):
        jd_repo = AsyncMock()
        jd = _mock_jd(status="draft")
        jd_repo.get_by_id_and_job.return_value = jd

        db = AsyncMock()
        service = _make_service(jd_repo=jd_repo, db=db)

        result = await service.activate_jd(JD_ID, JOB_ID)

        jd_repo.archive_active.assert_awaited_once_with(JOB_ID)
        jd_repo.set_status.assert_awaited_once_with(JD_ID, "active")
        jd_repo.set_active_jd_on_job.assert_awaited_once_with(JOB_ID, JD_ID)
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_correct_version_number(self):
        jd_repo = AsyncMock()
        jd = _mock_jd(status="draft", version=3)
        jd_repo.get_by_id_and_job.return_value = jd

        service = _make_service(jd_repo=jd_repo, db=AsyncMock())
        result = await service.activate_jd(JD_ID, JOB_ID)

        assert result.version_number == 3
        assert result.activated_jd_id == JD_ID


# ── update_jd ─────────────────────────────────────────────────────────────────

class TestUpdateJD:
    @pytest.mark.asyncio
    async def test_raises_jd_not_found(self):
        jd_repo = AsyncMock()
        jd_repo.get_by_id_and_job.return_value = None

        service = _make_service(jd_repo=jd_repo)
        with pytest.raises(JDNotFound):
            await service.update_jd(JD_ID, JOB_ID, title="New")

    @pytest.mark.asyncio
    async def test_raises_not_editable_for_active_jd(self):
        jd_repo = AsyncMock()
        jd_repo.get_by_id_and_job.return_value = _mock_jd(status="active")

        service = _make_service(jd_repo=jd_repo)
        with pytest.raises(JDNotEditable):
            await service.update_jd(JD_ID, JOB_ID, title="New Title")

    @pytest.mark.asyncio
    async def test_raises_not_editable_for_archived_jd(self):
        jd_repo = AsyncMock()
        jd_repo.get_by_id_and_job.return_value = _mock_jd(status="archived")

        service = _make_service(jd_repo=jd_repo)
        with pytest.raises(JDNotEditable):
            await service.update_jd(JD_ID, JOB_ID, content="New content")

    @pytest.mark.asyncio
    async def test_draft_jd_is_updated(self):
        jd_repo = AsyncMock()
        jd_repo.get_by_id_and_job.return_value = _mock_jd(status="draft")
        updated_jd = _mock_jd(status="draft")
        jd_repo.get_by_id.return_value = updated_jd

        db = AsyncMock()
        service = _make_service(jd_repo=jd_repo, db=db)

        with patch("src.services.jd_service.JDVersionResponse") as mock_resp:
            mock_resp.model_validate.return_value = MagicMock()
            await service.update_jd(JD_ID, JOB_ID, title="Updated Title", content="New content")

        jd_repo.update.assert_awaited_once_with(JD_ID, title="Updated Title", content="New content")
        db.commit.assert_awaited_once()


# ── delete_jd ─────────────────────────────────────────────────────────────────

class TestDeleteJD:
    @pytest.mark.asyncio
    async def test_raises_jd_not_found(self):
        jd_repo = AsyncMock()
        jd_repo.get_by_id_and_job.return_value = None

        service = _make_service(jd_repo=jd_repo)
        with pytest.raises(JDNotFound):
            await service.delete_jd(JD_ID, JOB_ID)

    @pytest.mark.asyncio
    async def test_raises_cannot_delete_active(self):
        jd_repo = AsyncMock()
        jd_repo.get_by_id_and_job.return_value = _mock_jd(status="active")

        service = _make_service(jd_repo=jd_repo)
        with pytest.raises(JDCannotDeleteActive):
            await service.delete_jd(JD_ID, JOB_ID)

    @pytest.mark.asyncio
    async def test_soft_deletes_draft(self):
        jd_repo = AsyncMock()
        jd_repo.get_by_id_and_job.return_value = _mock_jd(status="draft")

        db = AsyncMock()
        service = _make_service(jd_repo=jd_repo, db=db)
        await service.delete_jd(JD_ID, JOB_ID)

        jd_repo.soft_delete.assert_awaited_once_with(JD_ID)
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_soft_deletes_archived(self):
        jd_repo = AsyncMock()
        jd_repo.get_by_id_and_job.return_value = _mock_jd(status="archived")

        db = AsyncMock()
        service = _make_service(jd_repo=jd_repo, db=db)
        await service.delete_jd(JD_ID, JOB_ID)

        jd_repo.soft_delete.assert_awaited_once_with(JD_ID)


# ── generate_public_link ──────────────────────────────────────────────────────

class TestGeneratePublicLink:
    @pytest.mark.asyncio
    async def test_raises_job_not_found(self):
        job_repo = AsyncMock()
        job_repo.get_job_by_id.return_value = None

        service = _make_service(job_repo=job_repo)
        with pytest.raises(JobNotFound):
            await service.generate_public_link(JOB_ID)

    @pytest.mark.asyncio
    async def test_raises_missing_active_jd(self):
        job_repo = AsyncMock()
        job_repo.get_job_by_id.return_value = _mock_job()

        jd_repo = AsyncMock()
        jd_repo.get_active.return_value = None  # no active JD

        service = _make_service(jd_repo=jd_repo, job_repo=job_repo)
        with pytest.raises(PublicLinkMissingActiveJD):
            await service.generate_public_link(JOB_ID)

    @pytest.mark.asyncio
    async def test_raises_missing_form_config(self):
        job_repo = AsyncMock()
        job_repo.get_job_by_id.return_value = _mock_job()

        jd_repo = AsyncMock()
        jd_repo.get_active.return_value = _mock_jd(status="active")

        form_config_repo = AsyncMock()
        form_config_repo.get_active.return_value = None  # no active form config

        service = _make_service(jd_repo=jd_repo, form_config_repo=form_config_repo, job_repo=job_repo)
        with pytest.raises(PublicLinkMissingFormConfig):
            await service.generate_public_link(JOB_ID)

    @pytest.mark.asyncio
    async def test_raises_slug_taken_for_custom_slug(self):
        job_repo = AsyncMock()
        job_repo.get_job_by_id.return_value = _mock_job()

        jd_repo = AsyncMock()
        jd_repo.get_active.return_value = _mock_jd(status="active")

        form_config_repo = AsyncMock()
        form_config_repo.get_active.return_value = _mock_form_config()

        service = _make_service(jd_repo=jd_repo, form_config_repo=form_config_repo, job_repo=job_repo)

        # Simulate slug already taken by another job
        async def slug_exists(slug, exclude_job_id=None):
            return True
        service._slug_exists = slug_exists

        with pytest.raises(PublicSlugAlreadyTaken):
            await service.generate_public_link(JOB_ID, custom_slug="my-custom-slug")

    @pytest.mark.asyncio
    async def test_generates_link_with_auto_slug(self):
        job_repo = AsyncMock()
        job_repo.get_job_by_id.return_value = _mock_job(title="Backend Engineer")

        jd_repo = AsyncMock()
        active_jd = _mock_jd(status="active")
        jd_repo.get_active.return_value = active_jd

        form_config_repo = AsyncMock()
        active_config = _mock_form_config()
        form_config_repo.get_active.return_value = active_config

        db = AsyncMock()
        service = _make_service(jd_repo=jd_repo, form_config_repo=form_config_repo, job_repo=job_repo, db=db)

        async def slug_exists(slug, exclude_job_id=None):
            return False
        service._slug_exists = slug_exists

        with patch("src.services.jd_service.FRONTEND_URL", "https://app.example.com"):
            result = await service.generate_public_link(JOB_ID)

        assert result.public_apply_enabled is True
        assert result.public_slug is not None
        assert "backend" in result.public_slug
        assert result.public_url.startswith("https://app.example.com/apply/")
        form_config_repo.set_public_link.assert_awaited_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_generates_link_with_custom_slug(self):
        job_repo = AsyncMock()
        job_repo.get_job_by_id.return_value = _mock_job()

        jd_repo = AsyncMock()
        jd_repo.get_active.return_value = _mock_jd(status="active")

        form_config_repo = AsyncMock()
        form_config_repo.get_active.return_value = _mock_form_config()

        db = AsyncMock()
        service = _make_service(jd_repo=jd_repo, form_config_repo=form_config_repo, job_repo=job_repo, db=db)

        async def slug_exists(slug, exclude_job_id=None):
            return False
        service._slug_exists = slug_exists

        with patch("src.services.jd_service.FRONTEND_URL", "https://app.example.com"):
            result = await service.generate_public_link(JOB_ID, custom_slug="my-custom-role-2026")

        assert result.public_slug == "my-custom-role-2026"
        form_config_repo.set_public_link.assert_awaited_once_with(JOB_ID, "my-custom-role-2026", enabled=True)


# ── disable_public_link ───────────────────────────────────────────────────────

class TestDisablePublicLink:
    @pytest.mark.asyncio
    async def test_raises_job_not_found(self):
        job_repo = AsyncMock()
        job_repo.get_job_by_id.return_value = None

        service = _make_service(job_repo=job_repo)
        with pytest.raises(JobNotFound):
            await service.disable_public_link(JOB_ID)

    @pytest.mark.asyncio
    async def test_sets_enabled_false(self):
        job_repo = AsyncMock()
        job_repo.get_job_by_id.return_value = _mock_job(public_apply_enabled=True)

        form_config_repo = AsyncMock()
        db = AsyncMock()
        service = _make_service(form_config_repo=form_config_repo, job_repo=job_repo, db=db)

        await service.disable_public_link(JOB_ID)

        form_config_repo.set_public_apply_enabled.assert_awaited_once_with(JOB_ID, enabled=False)
        db.commit.assert_awaited_once()
