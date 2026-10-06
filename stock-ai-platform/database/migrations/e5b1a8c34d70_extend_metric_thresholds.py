"""extend metric thresholds for user overrides and ranges

Revision ID: e5b1a8c34d70
Revises: d4a7c1e83b20
Create Date: 2026-09-24 19:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5b1a8c34d70"
down_revision: Union[str, Sequence[str], None] = "d4a7c1e83b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE alert_operator ADD VALUE IF NOT EXISTS 'between'")
        op.execute("ALTER TYPE alert_operator ADD VALUE IF NOT EXISTS 'outside_range'")
        op.execute("ALTER TYPE metric_scope ADD VALUE IF NOT EXISTS 'user'")
    op.add_column("metric_thresholds", sa.Column("user_id", sa.Uuid(), nullable=True))
    op.add_column("metric_thresholds", sa.Column("stock_id", sa.Uuid(), nullable=True))
    op.add_column("metric_thresholds", sa.Column("basis", sa.String(length=32), server_default=sa.text("'absolute'"), nullable=False))
    op.add_column("metric_thresholds", sa.Column("threshold_high", sa.Numeric(precision=20, scale=6), nullable=True))
    op.add_column("metric_thresholds", sa.Column("definition_version", sa.String(length=32), server_default=sa.text("'thresholds-1'"), nullable=False))
    op.add_column("metric_thresholds", sa.Column("effective_from", sa.Date(), nullable=True))
    op.add_column("metric_thresholds", sa.Column("effective_to", sa.Date(), nullable=True))
    op.alter_column("metric_thresholds", "threshold_value", existing_type=sa.Numeric(precision=20, scale=6), nullable=True)
    op.create_foreign_key("fk_metric_thresholds_user_id_users", "metric_thresholds", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_metric_thresholds_stock_id_stocks", "metric_thresholds", "stocks", ["stock_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_metric_thresholds_user_id", "metric_thresholds", ["user_id"])
    op.create_index("ix_metric_thresholds_metric_active", "metric_thresholds", ["metric_name", "is_active"])
    op.execute("ALTER TABLE metric_thresholds DROP CONSTRAINT IF EXISTS ck_metric_thresholds_scope_fields")
    op.execute("ALTER TABLE metric_thresholds DROP CONSTRAINT IF EXISTS uq_metric_thresholds_identity")
    op.execute(
        "ALTER TABLE metric_thresholds ADD CONSTRAINT ck_metric_thresholds_scope_fields CHECK ("
        "(scope = 'global' AND sector IS NULL AND country IS NULL AND user_id IS NULL AND stock_id IS NULL) OR "
        "(scope = 'country' AND country IS NOT NULL AND sector IS NULL AND user_id IS NULL AND stock_id IS NULL) OR "
        "(scope = 'sector' AND sector IS NOT NULL AND user_id IS NULL AND stock_id IS NULL) OR "
        "(scope = 'user' AND user_id IS NOT NULL AND sector IS NULL AND country IS NULL))"
    )
    op.execute(
        "ALTER TABLE metric_thresholds ADD CONSTRAINT ck_metric_thresholds_effective_range CHECK "
        "(effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from)"
    )
    op.execute(
        "ALTER TABLE metric_thresholds ADD CONSTRAINT ck_metric_thresholds_basis_values CHECK "
        "(basis IN ('absolute', 'sector_benchmark'))"
    )
    op.execute(
        "ALTER TABLE metric_thresholds ADD CONSTRAINT ck_metric_thresholds_condition_shape CHECK ("
        "(basis = 'absolute' AND operator IN ('>', '<', '>=', '<=', '=') AND threshold_value IS NOT NULL AND threshold_high IS NULL) OR "
        "(basis = 'absolute' AND operator IN ('between', 'outside_range') AND threshold_value IS NOT NULL AND threshold_high IS NOT NULL AND threshold_high > threshold_value) OR "
        "(basis = 'absolute' AND operator IN ('crosses_above', 'crosses_below') AND threshold_high IS NULL) OR "
        "(basis = 'sector_benchmark' AND operator IN ('>', '<', '>=', '<=') AND threshold_value IS NULL AND threshold_high IS NULL))"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_metric_thresholds_active ON metric_thresholds "
        "(metric_name, scope, sector, country, user_id, stock_id) NULLS NOT DISTINCT WHERE is_active"
    )
    op.execute(
        """
        INSERT INTO metric_thresholds (
            metric_name, scope, sector, country, operator, basis, threshold_value, threshold_high,
            description, definition_version, is_active
        ) VALUES
        ('current_ratio', 'global', NULL, NULL, '>=', 'absolute', 1, NULL,
         'Platform default. A screening band, not a trade instruction.', 'thresholds-1', true),
        ('debt_to_equity', 'global', NULL, NULL, '<=', 'absolute', 2, NULL,
         'Platform default. A screening band, not a trade instruction.', 'thresholds-1', true),
        ('rsi_14', 'global', NULL, NULL, 'between', 'absolute', 30, 70,
         'Platform default. A screening band, not a trade instruction.', 'thresholds-1', true),
        ('pe_ratio', 'country', NULL, 'IN', '<=', 'absolute', 40, NULL,
         'India market default. A screening band, not a trade instruction.', 'thresholds-1', true),
        ('pe_ratio', 'sector', 'Information Technology', 'IN', '<=', 'absolute', 35, NULL,
         'India information-technology default. A screening band, not a trade instruction.', 'thresholds-1', true)
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM metric_thresholds WHERE scope = 'user'")
    op.execute(
        "DELETE FROM metric_thresholds WHERE description LIKE '%screening band, not a trade instruction.%'"
    )
    op.execute("DROP INDEX IF EXISTS uq_metric_thresholds_active")
    op.execute("ALTER TABLE metric_thresholds DROP CONSTRAINT IF EXISTS ck_metric_thresholds_condition_shape")
    op.execute("ALTER TABLE metric_thresholds DROP CONSTRAINT IF EXISTS ck_metric_thresholds_basis_values")
    op.execute("ALTER TABLE metric_thresholds DROP CONSTRAINT IF EXISTS ck_metric_thresholds_effective_range")
    op.execute("ALTER TABLE metric_thresholds DROP CONSTRAINT IF EXISTS ck_metric_thresholds_scope_fields")
    op.create_unique_constraint(
        "uq_metric_thresholds_identity",
        "metric_thresholds",
        ["metric_name", "scope", "sector", "country", "operator"],
        postgresql_nulls_not_distinct=True,
    )
    op.create_check_constraint(
        "ck_metric_thresholds_scope_fields",
        "metric_thresholds",
        "(scope = 'global' AND sector IS NULL AND country IS NULL) OR "
        "(scope = 'country' AND country IS NOT NULL AND sector IS NULL) OR "
        "(scope = 'sector' AND sector IS NOT NULL)",
    )
    op.drop_index("ix_metric_thresholds_metric_active", table_name="metric_thresholds")
    op.drop_index("ix_metric_thresholds_user_id", table_name="metric_thresholds")
    op.drop_constraint("fk_metric_thresholds_stock_id_stocks", "metric_thresholds", type_="foreignkey")
    op.drop_constraint("fk_metric_thresholds_user_id_users", "metric_thresholds", type_="foreignkey")
    op.drop_column("metric_thresholds", "effective_to")
    op.drop_column("metric_thresholds", "effective_from")
    op.drop_column("metric_thresholds", "definition_version")
    op.drop_column("metric_thresholds", "threshold_high")
    op.drop_column("metric_thresholds", "basis")
    op.drop_column("metric_thresholds", "stock_id")
    op.drop_column("metric_thresholds", "user_id")
    op.alter_column("metric_thresholds", "threshold_value", existing_type=sa.Numeric(precision=20, scale=6), nullable=False)
