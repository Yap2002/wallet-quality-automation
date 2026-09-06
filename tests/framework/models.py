from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Self
from uuid import UUID


@dataclass(frozen=True, slots=True)
class UserData:
    id: UUID
    email: str
    status: str
    api_key: str = field(repr=False)

    @classmethod
    def from_json(cls, body: dict[str, Any]) -> Self:
        return cls(
            id=UUID(body["id"]),
            email=str(body["email"]),
            status=str(body["status"]),
            api_key=str(body["api_key"]),
        )


@dataclass(frozen=True, slots=True)
class WalletData:
    id: UUID
    user_id: UUID
    currency: str
    balance: Decimal
    version: int

    @classmethod
    def from_json(cls, body: dict[str, Any]) -> Self:
        return cls(
            id=UUID(body["id"]),
            user_id=UUID(body["user_id"]),
            currency=str(body["currency"]),
            balance=Decimal(str(body["balance"])),
            version=int(body["version"]),
        )


@dataclass(frozen=True, slots=True)
class TransactionData:
    id: UUID
    type: str
    status: str
    source_wallet_id: UUID | None
    destination_wallet_id: UUID | None
    amount: Decimal
    fee_amount: Decimal
    currency: str
    trace_id: str
    completed_at: datetime | None

    @classmethod
    def from_json(cls, body: dict[str, Any]) -> Self:
        return cls(
            id=UUID(body["id"]),
            type=str(body["type"]),
            status=str(body["status"]),
            source_wallet_id=_optional_uuid(body.get("source_wallet_id")),
            destination_wallet_id=_optional_uuid(body.get("destination_wallet_id")),
            amount=Decimal(str(body["amount"])),
            fee_amount=Decimal(str(body["fee_amount"])),
            currency=str(body["currency"]),
            trace_id=str(body["trace_id"]),
            completed_at=_optional_datetime(body.get("completed_at")),
        )


@dataclass(frozen=True, slots=True)
class UserWallet:
    user: UserData
    wallet: WalletData


def _optional_uuid(value: Any) -> UUID | None:
    return None if value is None else UUID(str(value))


def _optional_datetime(value: Any) -> datetime | None:
    return None if value is None else datetime.fromisoformat(str(value))
