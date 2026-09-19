"""Seed system ledger accounts before the first money transaction.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHANNEL_ACCOUNT_ID = "00000000000000000000000000000008"
PLATFORM_FEE_ACCOUNT_ID = "00000000000000000000000000000009"


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT IGNORE INTO ledger_accounts "
            "(id, account_type, account_key, wallet_id, currency) VALUES "
            "(:channel_id, 'CHANNEL_CLEARING', 'SYSTEM:CHANNEL_CLEARING:CNY', NULL, 'CNY'), "
            "(:fee_id, 'PLATFORM_FEE', 'SYSTEM:PLATFORM_FEE:CNY', NULL, 'CNY')"
        ).bindparams(
            channel_id=CHANNEL_ACCOUNT_ID,
            fee_id=PLATFORM_FEE_ACCOUNT_ID,
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE account FROM ledger_accounts AS account "
            "LEFT JOIN ledger_entries AS entry ON entry.account_id = account.id "
            "WHERE account.id IN (:channel_id, :fee_id) AND entry.id IS NULL"
        ).bindparams(
            channel_id=CHANNEL_ACCOUNT_ID,
            fee_id=PLATFORM_FEE_ACCOUNT_ID,
        )
    )
