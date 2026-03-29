"""initial

Revision ID: 59299f438cdd
Revises: 
Create Date: 2026-03-22 17:26:54.522696

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '59299f438cdd'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    pass

def downgrade():
    pass