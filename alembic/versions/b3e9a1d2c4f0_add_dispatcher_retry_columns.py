"""add dispatcher retry columns

Revision ID: b3e9a1d2c4f0
Revises: 57c7d38c29a7
Create Date: 2026-04-18 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'b3e9a1d2c4f0'
down_revision: Union[str, Sequence[str], None] = '57c7d38c29a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('reminders', sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('reminders', sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('reminders', sa.Column('error_log', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    op.add_column('notifications', sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('notifications', sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('notifications', 'next_retry_at')
    op.drop_column('notifications', 'attempt_count')

    op.drop_column('reminders', 'error_log')
    op.drop_column('reminders', 'next_retry_at')
    op.drop_column('reminders', 'attempt_count')
