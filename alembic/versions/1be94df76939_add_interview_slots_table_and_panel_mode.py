"""add_interview_slots_table_and_panel_mode

Revision ID: 1be94df76939
Revises: 0cca96e48ddd
Create Date: 2026-03-02 19:46:36.037495

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1be94df76939'
down_revision: Union[str, Sequence[str], None] = '0cca96e48ddd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create panel_mode enum type
    panel_mode_enum = sa.Enum('PANEL', 'SEQUENTIAL', name='panel_mode_enum')
    panel_mode_enum.create(op.get_bind(), checkfirst=True)

    # Create interview_slots table
    op.create_table('interview_slots',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('round_config_id', sa.UUID(), nullable=False),
    sa.Column('panelist_email', sa.String(), nullable=True),
    sa.Column('slot_start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('slot_end', sa.DateTime(timezone=True), nullable=False),
    sa.Column('is_booked', sa.Boolean(), nullable=False),
    sa.Column('booked_interview_id', sa.UUID(), nullable=True),
    sa.Column('booked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['booked_interview_id'], ['interviews.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['round_config_id'], ['interview_round_configs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_interview_slots_id'), 'interview_slots', ['id'], unique=False)
    op.create_index(op.f('ix_interview_slots_panelist_email'), 'interview_slots', ['panelist_email'], unique=False)
    op.create_index(op.f('ix_interview_slots_round_config_id'), 'interview_slots', ['round_config_id'], unique=False)
    # Partial index for quick available-slot lookups
    op.create_index('idx_slots_available', 'interview_slots', ['round_config_id', 'is_booked'], postgresql_where=sa.text('is_booked = FALSE'))
    # Partial index for booked interview lookups
    op.create_index('idx_slots_booked_iv', 'interview_slots', ['booked_interview_id'], postgresql_where=sa.text('booked_interview_id IS NOT NULL'))

    # Add panel_mode column to interview_round_configs (default PANEL)
    op.add_column('interview_round_configs', sa.Column('panel_mode', sa.Enum('PANEL', 'SEQUENTIAL', name='panel_mode_enum'), nullable=False, server_default='PANEL'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('interview_round_configs', 'panel_mode')
    op.drop_index('idx_slots_booked_iv', table_name='interview_slots')
    op.drop_index('idx_slots_available', table_name='interview_slots')
    op.drop_index(op.f('ix_interview_slots_round_config_id'), table_name='interview_slots')
    op.drop_index(op.f('ix_interview_slots_panelist_email'), table_name='interview_slots')
    op.drop_index(op.f('ix_interview_slots_id'), table_name='interview_slots')
    op.drop_table('interview_slots')
    sa.Enum(name='panel_mode_enum').drop(op.get_bind(), checkfirst=True)
