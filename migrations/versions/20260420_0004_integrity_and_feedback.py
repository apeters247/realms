"""Stream I (integrity) + Stream R (feedback) — additive tables + columns.

- ``ingested_entities.integrity_meta`` JSONB — per-extraction verification record.
- ``integrity_audits`` — nightly oracle sampling history.
- ``feedback_reports`` — public error-reporting submissions.

Revision ID: 20260420_0004
Revises: 20260419_0003
Create Date: 2026-04-20 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260420_0004"
down_revision: Union[str, Sequence[str], None] = "20260419_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ingested_entities",
        sa.Column("integrity_meta", postgresql.JSONB, nullable=True),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ingested_entities_integrity "
        "ON ingested_entities USING GIN (integrity_meta)"
    )

    op.create_table(
        "integrity_audits",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("audited_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("sample_size", sa.Integer, nullable=False),
        sa.Column("n_supported", sa.Integer, nullable=False, server_default="0"),
        sa.Column("n_ambiguous", sa.Integer, nullable=False, server_default="0"),
        sa.Column("n_contradicted", sa.Integer, nullable=False, server_default="0"),
        sa.Column("oracle_model", sa.String(100), nullable=False),
        sa.Column("sample_ids", postgresql.JSONB, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
    )
    op.create_index("ix_integrity_audits_at", "integrity_audits", ["audited_at"])

    op.create_table(
        "feedback_reports",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("entity_id", sa.Integer,
                  sa.ForeignKey("entities.id", ondelete="CASCADE"),
                  nullable=True),
        sa.Column("field", sa.String(100), nullable=True),
        sa.Column("issue_type", sa.String(40), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("reporter_email", sa.String(200), nullable=True),
        sa.Column("reporter_ip_hash", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), server_default=sa.text("'open'"), nullable=False),
        sa.Column("resolution", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_feedback_entity", "feedback_reports", ["entity_id"])
    op.create_index("ix_feedback_status", "feedback_reports", ["status"])
    op.create_index("ix_feedback_created", "feedback_reports", ["created_at"])
    op.create_index("ix_feedback_ip", "feedback_reports", ["reporter_ip_hash"])
    op.create_index("ix_feedback_issue", "feedback_reports", ["issue_type"])


def downgrade() -> None:
    for ix in ("ix_feedback_issue", "ix_feedback_ip", "ix_feedback_created",
               "ix_feedback_status", "ix_feedback_entity"):
        op.drop_index(ix, table_name="feedback_reports")
    op.drop_table("feedback_reports")
    op.drop_index("ix_integrity_audits_at", table_name="integrity_audits")
    op.drop_table("integrity_audits")
    op.execute("DROP INDEX IF EXISTS ix_ingested_entities_integrity")
    op.drop_column("ingested_entities", "integrity_meta")
