"""Add refund parent relationship.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("parent_transaction_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_transactions_parent_transaction_id_transactions",
        "transactions",
        "transactions",
        ["parent_transaction_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_transactions_parent_transaction_id",
        "transactions",
        ["parent_transaction_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_parent_transaction_id", table_name="transactions")
    op.drop_constraint(
        "fk_transactions_parent_transaction_id_transactions",
        "transactions",
        type_="foreignkey",
    )
    op.drop_column("transactions", "parent_transaction_id")
