"""make_form_config_org_id_nullable

Revision ID: b4d30d347632
Revises: 344d7bcf3d66
Create Date: 2026-03-14 22:02:16.439477

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b4d30d347632'
down_revision: Union[str, Sequence[str], None] = '344d7bcf3d66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('application_form_configs', 'organization_id',
               existing_type=sa.UUID(),
               nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('application_form_configs', 'organization_id',
               existing_type=sa.UUID(),
               nullable=False)
