"""add weighted scoring columns

Revision ID: c9f3a2d71e45
Revises: b8371e7e607d
Create Date: 2026-02-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9f3a2d71e45'
down_revision: Union[str, Sequence[str], None] = 'b8371e7e607d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('scores', sa.Column('raw_overall_score', sa.Numeric(5, 2), nullable=True))
    op.add_column('scores', sa.Column('scoring_method', sa.VARCHAR(50), nullable=True))
    op.add_column('resumes', sa.Column('extraction_method', sa.VARCHAR(20), nullable=True))


def downgrade() -> None:
    op.drop_column('resumes', 'extraction_method')
    op.drop_column('scores', 'scoring_method')
    op.drop_column('scores', 'raw_overall_score')
