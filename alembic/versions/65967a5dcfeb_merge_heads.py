"""merge_heads

Revision ID: 65967a5dcfeb
Revises: 5bbe9eaae338, c9f3a2d71e45
Create Date: 2026-03-11 01:04:35.881486

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '65967a5dcfeb'
down_revision: Union[str, Sequence[str], None] = ('5bbe9eaae338', 'c9f3a2d71e45')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
