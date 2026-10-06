"""add user-owned research analyses

Revision ID: b3c8e1a94d20
Revises: a7e2c9d14f80
Create Date: 2026-09-25 00:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "b3c8e1a94d20"
down_revision: Union[str, Sequence[str], None] = "a7e2c9d14f80"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stock_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("analysis_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("explanation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("score", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("scoring_version", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('complete', 'partial', 'insufficient_data', 'ai_unavailable')",
            name="ck_research_analyses_status",
        ),
    )
    op.create_index("ix_research_analyses_user_created", "research_analyses", ["user_id", "created_at"])
    op.create_index("ix_research_analyses_user_stock_created", "research_analyses", ["user_id", "stock_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_research_analyses_user_stock_created", table_name="research_analyses")
    op.drop_index("ix_research_analyses_user_created", table_name="research_analyses")
    op.drop_table("research_analyses")
