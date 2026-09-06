"""Create channel callback audit records.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "channel_callbacks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("received_status", sa.String(length=16), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), server_default="0", nullable=False),
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
        sa.CheckConstraint("received_status IN ('SUCCEEDED', 'FAILED')", name="received_status"),
        sa.CheckConstraint("outcome IN ('APPLIED', 'IGNORED_TERMINAL')", name="outcome"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_channel_callbacks"),
        sa.UniqueConstraint("event_id", name="uq_channel_callbacks_event_id"),
    )
    op.create_index(
        "ix_channel_callbacks_transaction_id",
        "channel_callbacks",
        ["transaction_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_channel_callbacks_transaction_id", table_name="channel_callbacks")
    op.drop_table("channel_callbacks")
