"""baseline — schema already created by Base.metadata.create_all in bootstrap

Revision ID: 20260418_0001
Revises:
Create Date: 2026-04-18 22:30:00.000000
"""
from typing import Sequence, Union


revision: str = "20260418_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op.

    The initial schema is created idempotently by
    ``scripts/bootstrap_realms_db.py`` via ``Base.metadata.create_all``.
    Alembic is introduced here as a baseline; subsequent migrations should
    use ``op.create_table``/``op.add_column`` normally and bootstrap should
    be retired once the first real migration lands.
    """
    pass


def downgrade() -> None:
    """No-op — this migration represents existing state."""
    pass
