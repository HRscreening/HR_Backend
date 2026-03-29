"""add_non_negotiable_columns

Revision ID: d6f8a9b1c2e3
Revises: c5e7f8a9b0d1
Create Date: 2026-03-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "d6f8a9b1c2e3"
down_revision: Union[str, None] = "c5e7f8a9b0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new ResumeStatus enum value for non-negotiable failures
    op.execute("ALTER TYPE resume_status_enum ADD VALUE IF NOT EXISTS 'non_negotiable_failed'")

    # Add non_negotiable_results JSONB column to resumes table
    op.add_column("resumes", sa.Column("non_negotiable_results", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("resumes", "non_negotiable_results")

    # Note: PostgreSQL does not support removing values from enums.
