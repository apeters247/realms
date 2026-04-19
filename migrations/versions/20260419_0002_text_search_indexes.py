"""text search indexes — pg_trgm + GIN on entity.name / description

Revision ID: 20260419_0002
Revises: 20260418_0001
Create Date: 2026-04-19 03:10:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260419_0002"
down_revision: Union[str, Sequence[str], None] = "20260418_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enable pg_trgm and create GIN indexes for substring / similarity search."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_entities_name_trgm "
        "ON entities USING GIN (name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_entities_description_trgm "
        "ON entities USING GIN (description gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_entities_cultural_associations_gin "
        "ON entities USING GIN (cultural_associations jsonb_path_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_entities_geographical_associations_gin "
        "ON entities USING GIN (geographical_associations jsonb_path_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_entities_name_trgm")
    op.execute("DROP INDEX IF EXISTS idx_entities_description_trgm")
    op.execute("DROP INDEX IF EXISTS idx_entities_cultural_associations_gin")
    op.execute("DROP INDEX IF EXISTS idx_entities_geographical_associations_gin")
