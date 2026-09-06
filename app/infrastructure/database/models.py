from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class LedgerAccountType(StrEnum):
    USER_WALLET = "USER_WALLET"
    CHANNEL_CLEARING = "CHANNEL_CLEARING"
    PLATFORM_FEE = "PLATFORM_FEE"


class LedgerDirection(StrEnum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class IdempotencyStatus(StrEnum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CallbackOutcome(StrEnum):
    APPLIED = "APPLIED"
    IGNORED_TERMINAL = "IGNORED_TERMINAL"


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'DISABLED')",
            name="status",
        ),
        UniqueConstraint("email", name="uq_users_email"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=UserStatus.ACTIVE.value,
    )
    api_key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    wallets: Mapped[list["WalletModel"]] = relationship(
        back_populates="user",
        passive_deletes=True,
    )


class WalletModel(Base):
    __tablename__ = "wallets"
    __table_args__ = (
        CheckConstraint("balance >= 0", name="balance_non_negative"),
        CheckConstraint("currency = 'CNY'", name="currency_cny"),
        UniqueConstraint(
            "user_id",
            "currency",
            name="uq_wallets_user_currency",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    balance: Mapped[Decimal] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    user: Mapped[UserModel] = relationship(back_populates="wallets")
    ledger_account: Mapped["LedgerAccountModel | None"] = relationship(
        back_populates="wallet",
        uselist=False,
    )


class TransactionModel(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint(
            "type IN ('DEPOSIT', 'WITHDRAWAL', 'TRANSFER', 'REFUND')",
            name="type",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'SUCCEEDED', 'FAILED', 'REFUNDED')",
            name="status",
        ),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("fee_amount >= 0", name="fee_non_negative"),
        CheckConstraint("currency = 'CNY'", name="currency_cny"),
        CheckConstraint(
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
        Index("ix_transactions_source_wallet_id", "source_wallet_id"),
        Index("ix_transactions_destination_wallet_id", "destination_wallet_id"),
        Index("ix_transactions_parent_transaction_id", "parent_transaction_id"),
        Index("ix_transactions_trace_id", "trace_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    source_wallet_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("wallets.id", ondelete="RESTRICT"),
        nullable=True,
    )
    destination_wallet_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("wallets.id", ondelete="RESTRICT"),
        nullable=True,
    )
    parent_transaction_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    fee_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    entries: Mapped[list["LedgerEntryModel"]] = relationship(
        back_populates="transaction",
    )


class FeeRuleModel(Base):
    __tablename__ = "fee_rules"
    __table_args__ = (
        CheckConstraint("transaction_type = 'TRANSFER'", name="transaction_type"),
        CheckConstraint("fixed_fee >= 0", name="fixed_fee_non_negative"),
        CheckConstraint("percentage_rate >= 0", name="percentage_rate_non_negative"),
        CheckConstraint("minimum_fee IS NULL OR minimum_fee >= 0", name="minimum_non_negative"),
        CheckConstraint("maximum_fee IS NULL OR maximum_fee >= 0", name="maximum_non_negative"),
        CheckConstraint(
            "minimum_fee IS NULL OR maximum_fee IS NULL OR minimum_fee <= maximum_fee",
            name="minimum_not_above_maximum",
        ),
        Index(
            "ix_fee_rules_selection",
            "transaction_type",
            "is_active",
            "priority",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(16), nullable=False, default="TRANSFER")
    fixed_fee: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False, default=Decimal("0.00"), server_default="0.00"
    )
    percentage_rate: Mapped[Decimal] = mapped_column(
        Numeric(12, 8), nullable=False, default=Decimal("0"), server_default="0"
    )
    minimum_fee: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    maximum_fee: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    is_fee_free: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class IdempotencyRecordModel(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        CheckConstraint("status IN ('PROCESSING', 'COMPLETED', 'FAILED')", name="status"),
        UniqueConstraint("user_id", "idempotency_key", name="uq_idempotency_user_key"),
        Index("ix_idempotency_records_transaction_id", "transaction_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=IdempotencyStatus.PROCESSING.value
    )
    transaction_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=True
    )
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ChannelCallbackModel(Base):
    __tablename__ = "channel_callbacks"
    __table_args__ = (
        CheckConstraint("received_status IN ('SUCCEEDED', 'FAILED')", name="received_status"),
        CheckConstraint("outcome IN ('APPLIED', 'IGNORED_TERMINAL')", name="outcome"),
        UniqueConstraint("event_id", name="uq_channel_callbacks_event_id"),
        Index("ix_channel_callbacks_transaction_id", "transaction_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    transaction_id: Mapped[UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=False
    )
    received_status: Mapped[str] = mapped_column(String(16), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    duplicate_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class LedgerAccountModel(Base):
    __tablename__ = "ledger_accounts"
    __table_args__ = (
        CheckConstraint(
            "account_type IN ('USER_WALLET', 'CHANNEL_CLEARING', 'PLATFORM_FEE')",
            name="account_type",
        ),
        CheckConstraint("currency = 'CNY'", name="currency_cny"),
        CheckConstraint(
            "(account_type = 'USER_WALLET' AND wallet_id IS NOT NULL) "
            "OR (account_type IN ('CHANNEL_CLEARING', 'PLATFORM_FEE') AND wallet_id IS NULL)",
            name="wallet_link",
        ),
        UniqueConstraint("account_key", name="uq_ledger_accounts_account_key"),
        UniqueConstraint("wallet_id", name="uq_ledger_accounts_wallet_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_type: Mapped[str] = mapped_column(String(32), nullable=False)
    account_key: Mapped[str] = mapped_column(String(64), nullable=False)
    wallet_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("wallets.id", ondelete="RESTRICT"),
        nullable=True,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    wallet: Mapped[WalletModel | None] = relationship(back_populates="ledger_account")
    entries: Mapped[list["LedgerEntryModel"]] = relationship(back_populates="account")


class LedgerEntryModel(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint("direction IN ('DEBIT', 'CREDIT')", name="direction"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("currency = 'CNY'", name="currency_cny"),
        Index("ix_ledger_entries_transaction_id", "transaction_id"),
        Index("ix_ledger_entries_account_id", "account_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    transaction_id: Mapped[UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("ledger_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    transaction: Mapped[TransactionModel] = relationship(back_populates="entries")
    account: Mapped[LedgerAccountModel] = relationship(back_populates="entries")
