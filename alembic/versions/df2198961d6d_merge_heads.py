"""merge_heads

Revision ID: df2198961d6d
Revises: add_queued_to_enum, c62462a9368b
Create Date: 2026-04-19 16:43:06.453137

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df2198961d6d'
down_revision: Union[str, Sequence[str], None] = ('add_queued_to_enum', 'c62462a9368b')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
