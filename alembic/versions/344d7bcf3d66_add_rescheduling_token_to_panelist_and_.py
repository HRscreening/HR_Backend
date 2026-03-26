"""add_rescheduling_token_to_panelist_and_interviews

Revision ID: 344d7bcf3d66
Revises: 3af6a0c27637
Create Date: 2026-03-14 20:25:18.657010

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '344d7bcf3d66'
down_revision: Union[str, Sequence[str], None] = '3af6a0c27637'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('panelist', sa.Column('rescheduling_token', sa.TEXT(), nullable=True))
    op.add_column('panelist', sa.Column('rescheduling_token_expires_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('panelist', 'rescheduling_token_expires_at')
    op.drop_column('panelist', 'rescheduling_token')
