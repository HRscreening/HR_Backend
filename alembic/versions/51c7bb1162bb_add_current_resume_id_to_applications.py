"""add current_resume_id to applications

Revision ID: 51c7bb1162bb
Revises: f80248cedfb0
Create Date: 2026-02-06 00:56:48.827683

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '51c7bb1162bb'
down_revision: Union[str, Sequence[str], None] = 'f80248cedfb0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        "applications",
        sa.Column("current_resume_id", sa.UUID(), nullable=True)
    )

    op.create_foreign_key(
        "fk_applications_current_resume",
        "applications",
        "resumes",
        ["current_resume_id"],
        ["id"],
        ondelete="SET NULL"
    )


def downgrade():
    op.drop_constraint(
        "fk_applications_current_resume",
        "applications",
        type_="foreignkey"
    )

    op.drop_column("applications", "current_resume_id")

