"""add_pipeline_v2_prescreening_columns

Revision ID: c5e7f8a9b0d1
Revises: b4d30d347632
Create Date: 2026-03-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c5e7f8a9b0d1"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new ResumeStatus enum values
    op.execute("ALTER TYPE resume_status_enum ADD VALUE IF NOT EXISTS 'quality_gate_failed'")
    op.execute("ALTER TYPE resume_status_enum ADD VALUE IF NOT EXISTS 'pre_screened'")

    # Add pre-screening columns to resumes table
    op.add_column("resumes", sa.Column("pre_screen_rank", sa.Integer(), nullable=True))
    op.add_column("resumes", sa.Column("relevance_score", sa.Numeric(7, 4), nullable=True))
    op.add_column("resumes", sa.Column("rejection_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("resumes", "rejection_reason")
    op.drop_column("resumes", "relevance_score")
    op.drop_column("resumes", "pre_screen_rank")

    # Note: PostgreSQL does not support removing values from enums.
    # To fully downgrade, you would need to recreate the enum type.
