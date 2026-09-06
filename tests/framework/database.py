from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Engine, delete, or_, select

from app.infrastructure.database.models import (
    ChannelCallbackModel,
    IdempotencyRecordModel,
    LedgerAccountModel,
    LedgerEntryModel,
    TransactionModel,
    UserModel,
    WalletModel,
)


@dataclass(frozen=True, slots=True)
class WalletSnapshot:
    id: UUID
    user_id: UUID
    balance: Decimal
    version: int


@dataclass(frozen=True, slots=True)
class LedgerEntrySnapshot:
    transaction_id: UUID
    account_id: UUID
    direction: str
    amount: Decimal


class DatabaseClient:
    """Read test evidence and remove only data created by the current test."""

    def __init__(self, engine: Engine) -> None:
        database_name = engine.url.database or ""
        if not database_name.endswith("_test"):
            raise ValueError(
                "DatabaseClient cleanup is allowed only for a database ending in '_test'"
            )
        self._engine = engine

    def get_wallet(self, wallet_id: UUID) -> WalletSnapshot:
        with self._engine.connect() as connection:
            row = connection.execute(
                select(
                    WalletModel.id,
                    WalletModel.user_id,
                    WalletModel.balance,
                    WalletModel.version,
                ).where(WalletModel.id == wallet_id)
            ).one()
        return WalletSnapshot(
            id=row.id,
            user_id=row.user_id,
            balance=row.balance,
            version=row.version,
        )

    def get_entries(self, transaction_id: UUID) -> list[LedgerEntrySnapshot]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                select(
                    LedgerEntryModel.transaction_id,
                    LedgerEntryModel.account_id,
                    LedgerEntryModel.direction,
                    LedgerEntryModel.amount,
                ).where(LedgerEntryModel.transaction_id == transaction_id)
            ).all()
        return [
            LedgerEntrySnapshot(
                transaction_id=row.transaction_id,
                account_id=row.account_id,
                direction=row.direction,
                amount=row.amount,
            )
            for row in rows
        ]

    def count_transactions_for_wallet(self, wallet_id: UUID) -> int:
        return len(self.get_transaction_ids_for_wallet(wallet_id))

    def get_transaction_ids_for_wallet(self, wallet_id: UUID) -> list[UUID]:
        with self._engine.connect() as connection:
            return list(
                connection.scalars(
                    select(TransactionModel.id).where(
                        or_(
                            TransactionModel.source_wallet_id == wallet_id,
                            TransactionModel.destination_wallet_id == wallet_id,
                        )
                    )
                ).all()
            )

    def cleanup_emails(self, emails: set[str]) -> None:
        if not emails:
            return
        with self._engine.begin() as connection:
            user_ids = set(
                connection.scalars(select(UserModel.id).where(UserModel.email.in_(emails))).all()
            )
            if not user_ids:
                return
            connection.execute(
                delete(IdempotencyRecordModel).where(IdempotencyRecordModel.user_id.in_(user_ids))
            )
            wallet_ids = set(
                connection.scalars(
                    select(WalletModel.id).where(WalletModel.user_id.in_(user_ids))
                ).all()
            )
            transaction_ids: set[UUID] = set()
            if wallet_ids:
                transaction_ids = set(
                    connection.scalars(
                        select(TransactionModel.id).where(
                            or_(
                                TransactionModel.source_wallet_id.in_(wallet_ids),
                                TransactionModel.destination_wallet_id.in_(wallet_ids),
                            )
                        )
                    ).all()
                )
            if transaction_ids:
                connection.execute(
                    delete(ChannelCallbackModel).where(
                        ChannelCallbackModel.transaction_id.in_(transaction_ids)
                    )
                )
                connection.execute(
                    delete(LedgerEntryModel).where(
                        LedgerEntryModel.transaction_id.in_(transaction_ids)
                    )
                )
                connection.execute(
                    delete(TransactionModel).where(TransactionModel.id.in_(transaction_ids))
                )
            if wallet_ids:
                connection.execute(
                    delete(LedgerAccountModel).where(LedgerAccountModel.wallet_id.in_(wallet_ids))
                )
                connection.execute(delete(WalletModel).where(WalletModel.id.in_(wallet_ids)))
            connection.execute(delete(UserModel).where(UserModel.id.in_(user_ids)))
