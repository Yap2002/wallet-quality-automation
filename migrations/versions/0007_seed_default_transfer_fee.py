"""Seed the default CNY transfer fee.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-11
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_RULE_ID = UUID("00000000-0000-0000-0000-000000000007")
DEFAULT_RULE_NAME = "default-fixed-2-cny"


def upgrade() -> None:
    fee_rules = sa.table(
        "fee_rules",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("transaction_type", sa.String()),
        sa.column("fixed_fee", sa.Numeric(20, 2)),
        sa.column("percentage_rate", sa.Numeric(12, 8)),
        sa.column("minimum_fee", sa.Numeric(20, 2)),
        sa.column("maximum_fee", sa.Numeric(20, 2)),
        sa.column("is_fee_free", sa.Boolean()),
        sa.column("priority", sa.Integer()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        fee_rules,
        [
            {
                "id": DEFAULT_RULE_ID,
                "name": DEFAULT_RULE_NAME,
                "transaction_type": "TRANSFER",
                "fixed_fee": 2,
                "percentage_rate": 0,
                "minimum_fee": None,
                "maximum_fee": None,
                "is_fee_free": False,
                "priority": 0,
                "is_active": True,
            }
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM fee_rules WHERE id = :rule_id").bindparams(rule_id=DEFAULT_RULE_ID.hex)
    )
