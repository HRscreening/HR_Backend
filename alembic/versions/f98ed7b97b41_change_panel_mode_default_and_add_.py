"""change_panel_mode_default_and_add_timezone_column

Revision ID: f98ed7b97b41
Revises: 1be94df76939
Create Date: 2026-03-02 21:07:18.954888

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f98ed7b97b41'
down_revision: Union[str, Sequence[str], None] = '1be94df76939'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Add timezone column to interview_round_configs
    op.add_column('interview_round_configs', sa.Column('timezone', sa.String(), nullable=True))

    # 2. Change panel_mode server_default from PANEL to SEQUENTIAL
    op.alter_column(
        'interview_round_configs',
        'panel_mode',
        server_default='SEQUENTIAL',
        existing_type=sa.Enum('PANEL', 'SEQUENTIAL', name='panel_mode_enum'),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Revert panel_mode default back to PANEL
    op.alter_column(
        'interview_round_configs',
        'panel_mode',
        server_default='PANEL',
        existing_type=sa.Enum('PANEL', 'SEQUENTIAL', name='panel_mode_enum'),
        existing_nullable=False,
    )

    # Drop timezone column
    op.drop_column('interview_round_configs', 'timezone')
