"""add_current_title_and_company_to_candidates

Revision ID: 09ddf9d7dd37
Revises: 65967a5dcfeb
Create Date: 2026-03-11 01:04:54.028975

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '09ddf9d7dd37'
down_revision: Union[str, Sequence[str], None] = '65967a5dcfeb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('candidates', sa.Column('current_title', sa.String(), nullable=True))
    op.add_column('candidates', sa.Column('current_company', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('candidates', 'current_company')
    op.drop_column('candidates', 'current_title')
