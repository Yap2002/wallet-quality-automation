"""Create transfer fee rules and platform fee ledger account type.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_ledger_accounts_account_type"), "ledger_accounts", type_="check")
    op.drop_constraint(op.f("ck_ledger_accounts_wallet_link"), "ledger_accounts", type_="check")
    op.create_check_constraint(
        "account_type",
        "ledger_accounts",
        "account_type IN ('USER_WALLET', 'CHANNEL_CLEARING', 'PLATFORM_FEE')",
    )
    op.create_check_constraint(
        "wallet_link",
        "ledger_accounts",
        "(account_type = 'USER_WALLET' AND wallet_id IS NOT NULL) OR "
        "(account_type IN ('CHANNEL_CLEARING', 'PLATFORM_FEE') AND wallet_id IS NULL)",
    )
    op.create_table(
        "fee_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("transaction_type", sa.String(length=16), nullable=False),
        sa.Column("fixed_fee", sa.Numeric(20, 2), server_default="0.00", nullable=False),
        sa.Column("percentage_rate", sa.Numeric(12, 8), server_default="0", nullable=False),
        sa.Column("minimum_fee", sa.Numeric(20, 2), nullable=True),
        sa.Column("maximum_fee", sa.Numeric(20, 2), nullable=True),
        sa.Column("is_fee_free", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("transaction_type = 'TRANSFER'", name="transaction_type"),
        sa.CheckConstraint("fixed_fee >= 0", name="fixed_fee_non_negative"),
        sa.CheckConstraint("percentage_rate >= 0", name="percentage_rate_non_negative"),
        sa.CheckConstraint("minimum_fee IS NULL OR minimum_fee >= 0", name="minimum_non_negative"),
        sa.CheckConstraint("maximum_fee IS NULL OR maximum_fee >= 0", name="maximum_non_negative"),
        sa.CheckConstraint(
            "minimum_fee IS NULL OR maximum_fee IS NULL OR minimum_fee <= maximum_fee",
            name="minimum_not_above_maximum",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_fee_rules"),
    )
    op.create_index(
        "ix_fee_rules_selection",
        "fee_rules",
        ["transaction_type", "is_active", "priority", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_fee_rules_selection", table_name="fee_rules")
    op.drop_table("fee_rules")
    op.drop_constraint(op.f("ck_ledger_accounts_wallet_link"), "ledger_accounts", type_="check")
    op.drop_constraint(op.f("ck_ledger_accounts_account_type"), "ledger_accounts", type_="check")
    op.create_check_constraint(
        "account_type",
        "ledger_accounts",
        "account_type IN ('USER_WALLET', 'CHANNEL_CLEARING')",
    )
    op.create_check_constraint(
        "wallet_link",
        "ledger_accounts",
        "(account_type = 'USER_WALLET' AND wallet_id IS NOT NULL) OR "
        "(account_type = 'CHANNEL_CLEARING' AND wallet_id IS NULL)",
    )
