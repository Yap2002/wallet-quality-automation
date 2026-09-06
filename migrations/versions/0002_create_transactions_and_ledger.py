"""Create transactions and minimal double-entry ledger.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("source_wallet_id", sa.Uuid(), nullable=True),
        sa.Column("destination_wallet_id", sa.Uuid(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column(
            "fee_amount",
            sa.Numeric(precision=20, scale=2),
            server_default="0.00",
            nullable=False,
        ),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_message", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "type IN ('DEPOSIT', 'WITHDRAWAL', 'TRANSFER', 'REFUND')",
            name="type",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'SUCCEEDED', 'FAILED', 'REFUNDED')",
            name="status",
        ),
        sa.CheckConstraint("amount > 0", name="amount_positive"),
        sa.CheckConstraint("fee_amount >= 0", name="fee_non_negative"),
        sa.CheckConstraint("currency = 'CNY'", name="currency_cny"),
        sa.CheckConstraint(
            "(type = 'DEPOSIT' AND source_wallet_id IS NULL "
            "AND destination_wallet_id IS NOT NULL) "
            "OR (type = 'WITHDRAWAL' AND source_wallet_id IS NOT NULL "
            "AND destination_wallet_id IS NULL) "
            "OR (type = 'TRANSFER' AND source_wallet_id IS NOT NULL "
            "AND destination_wallet_id IS NOT NULL "
            "AND source_wallet_id <> destination_wallet_id) "
            "OR type = 'REFUND'",
            name="wallet_shape",
        ),
        sa.ForeignKeyConstraint(
            ["source_wallet_id"],
            ["wallets.id"],
            name="fk_transactions_source_wallet_id_wallets",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["destination_wallet_id"],
            ["wallets.id"],
            name="fk_transactions_destination_wallet_id_wallets",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_transactions"),
    )
    op.create_index(
        "ix_transactions_source_wallet_id",
        "transactions",
        ["source_wallet_id"],
    )
    op.create_index(
        "ix_transactions_destination_wallet_id",
        "transactions",
        ["destination_wallet_id"],
    )
    op.create_index("ix_transactions_trace_id", "transactions", ["trace_id"])

    op.create_table(
        "ledger_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_type", sa.String(length=32), nullable=False),
        sa.Column("account_key", sa.String(length=64), nullable=False),
        sa.Column("wallet_id", sa.Uuid(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "account_type IN ('USER_WALLET', 'CHANNEL_CLEARING')",
            name="account_type",
        ),
        sa.CheckConstraint("currency = 'CNY'", name="currency_cny"),
        sa.CheckConstraint(
            "(account_type = 'USER_WALLET' AND wallet_id IS NOT NULL) "
            "OR (account_type = 'CHANNEL_CLEARING' AND wallet_id IS NULL)",
            name="wallet_link",
        ),
        sa.ForeignKeyConstraint(
            ["wallet_id"],
            ["wallets.id"],
            name="fk_ledger_accounts_wallet_id_wallets",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ledger_accounts"),
        sa.UniqueConstraint("account_key", name="uq_ledger_accounts_account_key"),
        sa.UniqueConstraint("wallet_id", name="uq_ledger_accounts_wallet_id"),
    )

    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "direction IN ('DEBIT', 'CREDIT')",
            name="direction",
        ),
        sa.CheckConstraint("amount > 0", name="amount_positive"),
        sa.CheckConstraint("currency = 'CNY'", name="currency_cny"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["ledger_accounts.id"],
            name="fk_ledger_entries_account_id_ledger_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name="fk_ledger_entries_transaction_id_transactions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ledger_entries"),
    )
    op.create_index(
        "ix_ledger_entries_transaction_id",
        "ledger_entries",
        ["transaction_id"],
    )
    op.create_index(
        "ix_ledger_entries_account_id",
        "ledger_entries",
        ["account_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ledger_entries_account_id", table_name="ledger_entries")
    op.drop_index("ix_ledger_entries_transaction_id", table_name="ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_table("ledger_accounts")
    op.drop_index("ix_transactions_trace_id", table_name="transactions")
    op.drop_index(
        "ix_transactions_destination_wallet_id",
        table_name="transactions",
    )
    op.drop_index("ix_transactions_source_wallet_id", table_name="transactions")
    op.drop_table("transactions")
