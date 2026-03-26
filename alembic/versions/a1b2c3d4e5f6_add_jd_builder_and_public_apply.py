"""add_jd_builder_and_public_apply

Adds:
  - job_descriptions table (versioned JDs per job, mirrors rubrics pattern)
  - application_form_configs table (customisable candidate form questions per job)
  - jobs.public_slug, jobs.public_apply_enabled, jobs.active_jd_id, jobs.active_form_config_id
  - applications.source

Revision ID: a1b2c3d4e5f6
Revises: 65967a5dcfeb
Create Date: 2026-03-14 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "65967a5dcfeb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. job_descriptions ───────────────────────────────────────────────────
    op.create_table(
        "job_descriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("raw_answers", postgresql.JSONB, nullable=True),
        sa.Column("generation_method", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_job_descriptions_job_id", "job_descriptions", ["job_id"])
    op.create_index(
        "ix_job_descriptions_organization_id", "job_descriptions", ["organization_id"]
    )
    op.create_index(
        "jd_job_id_version_uq",
        "job_descriptions",
        ["job_id", "version_number"],
        unique=True,
    )
    # Partial unique index: only one active JD per job (same pattern as rubrics)
    op.create_index(
        "jd_one_active_per_job_uq",
        "job_descriptions",
        ["job_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND deleted_at IS NULL"),
    )

    # ── 2. application_form_configs ───────────────────────────────────────────
    op.create_table(
        "application_form_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("questions", postgresql.JSONB, nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_application_form_configs_job_id", "application_form_configs", ["job_id"])
    op.create_index(
        "ix_application_form_configs_organization_id",
        "application_form_configs",
        ["organization_id"],
    )
    op.create_index(
        "afc_job_id_version_uq",
        "application_form_configs",
        ["job_id", "version_number"],
        unique=True,
    )

    # ── 3. Add columns to jobs ────────────────────────────────────────────────
    op.add_column("jobs", sa.Column("public_slug", sa.String(80), nullable=True))
    op.add_column(
        "jobs",
        sa.Column(
            "public_apply_enabled",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    # Circular FKs added after both tables exist (use_alter pattern)
    op.add_column(
        "jobs",
        sa.Column("active_jd_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("active_form_config_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_jobs_active_jd_id",
        "jobs",
        "job_descriptions",
        ["active_jd_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_jobs_active_form_config_id",
        "jobs",
        "application_form_configs",
        ["active_form_config_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # Partial unique index on public_slug (ignores NULL and deleted rows)
    op.create_index(
        "uq_jobs_public_slug",
        "jobs",
        ["public_slug"],
        unique=True,
        postgresql_where=sa.text("public_slug IS NOT NULL AND deleted_at IS NULL"),
    )

    # ── 4. Add source column to applications ──────────────────────────────────
    op.add_column(
        "applications",
        sa.Column(
            "source",
            sa.String(50),
            nullable=False,
            server_default="internal",
        ),
    )


def downgrade() -> None:
    # Reverse in opposite order

    # applications.source
    op.drop_column("applications", "source")

    # jobs circular FK constraints + columns
    op.drop_constraint("fk_jobs_active_form_config_id", "jobs", type_="foreignkey")
    op.drop_constraint("fk_jobs_active_jd_id", "jobs", type_="foreignkey")
    op.drop_index("uq_jobs_public_slug", table_name="jobs")
    op.drop_column("jobs", "active_form_config_id")
    op.drop_column("jobs", "active_jd_id")
    op.drop_column("jobs", "public_apply_enabled")
    op.drop_column("jobs", "public_slug")

    # application_form_configs
    op.drop_index("afc_job_id_version_uq", table_name="application_form_configs")
    op.drop_index("ix_application_form_configs_organization_id", table_name="application_form_configs")
    op.drop_index("ix_application_form_configs_job_id", table_name="application_form_configs")
    op.drop_table("application_form_configs")

    # job_descriptions
    op.drop_index("jd_one_active_per_job_uq", table_name="job_descriptions")
    op.drop_index("jd_job_id_version_uq", table_name="job_descriptions")
    op.drop_index("ix_job_descriptions_organization_id", table_name="job_descriptions")
    op.drop_index("ix_job_descriptions_job_id", table_name="job_descriptions")
    op.drop_table("job_descriptions")
