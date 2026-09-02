"""Add Queued to reminder_status_enum

Revision ID: add_queued_to_enum
Revises: 33a913cf7610
Create Date: 2026-04-19 16:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_queued_to_enum'
down_revision: Union[str, Sequence[str], None] = '33a913cf7610'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Use transactional DDL if possible, but some DBs don't support it for enums
    # Postgres 12+ supports ALTER TYPE ... ADD VALUE IF NOT EXISTS
    # However, it cannot be run inside a transaction block in some versions/scenarios.
    # We'll use a safer approach for Supabase/Postgres.
    op.execute("COMMIT")
    op.execute("ALTER TYPE reminder_status_enum ADD VALUE IF NOT EXISTS 'Queued' AFTER 'Pending'")

def downgrade() -> None:
    # Downgrading enums in Postgres is complex (requires recreating the type). 
    # Usually skipping is safer for production data. 
    pass
