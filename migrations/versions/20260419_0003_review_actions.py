"""review_actions audit table + external_ids + temporal columns

Phases 4 (review audit), 5 (temporal), 6 (external_ids) are all additive,
so they ship as a single migration to avoid chaining short migrations.

Revision ID: 20260419_0003
Revises: 20260419_0002
Create Date: 2026-04-19 13:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260419_0003"
down_revision: Union[str, Sequence[str], None] = "20260419_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Phase 4 — review_actions audit trail
    op.create_table(
        "review_actions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("entity_id", sa.Integer,
                  sa.ForeignKey("entities.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("reviewer", sa.String(200), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("field", sa.String(100), nullable=True),
        sa.Column("old_value", postgresql.JSONB, nullable=True),
        sa.Column("new_value", postgresql.JSONB, nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_review_actions_created",
                    "review_actions", ["created_at"])

    # Phase 5 — temporal columns on entities
    op.add_column("entities",
                  sa.Column("first_documented_year", sa.Integer, nullable=True))
    op.add_column("entities",
                  sa.Column("evidence_period_start", sa.Integer, nullable=True))
    op.add_column("entities",
                  sa.Column("evidence_period_end", sa.Integer, nullable=True))
    op.add_column("entities",
                  sa.Column("historical_notes", sa.Text, nullable=True))
    op.create_index("ix_entities_first_documented",
                    "entities", ["first_documented_year"])

    # Phase 6 — external_ids JSONB
    op.add_column(
        "entities",
        sa.Column("external_ids", postgresql.JSONB,
                  server_default=sa.text("'{}'::jsonb"),
                  nullable=False),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_entities_external_ids "
        "ON entities USING GIN (external_ids)"
    )

    # Phase 4 / 6 — status column on entities for soft-delete / approve / reject
    op.add_column(
        "entities",
        sa.Column("review_status", sa.String(20),
                  server_default=sa.text("'unreviewed'"),
                  nullable=False),
    )
    op.create_index("ix_entities_review_status", "entities", ["review_status"])


def downgrade() -> None:
    op.drop_index("ix_entities_review_status", table_name="entities")
    op.drop_column("entities", "review_status")
    op.execute("DROP INDEX IF EXISTS ix_entities_external_ids")
    op.drop_column("entities", "external_ids")
    op.drop_index("ix_entities_first_documented", table_name="entities")
    op.drop_column("entities", "historical_notes")
    op.drop_column("entities", "evidence_period_end")
    op.drop_column("entities", "evidence_period_start")
    op.drop_column("entities", "first_documented_year")
    op.drop_index("ix_review_actions_created", table_name="review_actions")
    op.drop_table("review_actions")
