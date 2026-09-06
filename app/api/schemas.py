from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator


class UserCreateRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        local, separator, domain = normalized.partition("@")
        if not separator or not local or "." not in domain:
            raise ValueError("email must have a valid address format")
        return normalized


class UserCreatedResponse(BaseModel):
    id: UUID
    email: str
    status: str
    api_key: str


class WalletResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    currency: str
    balance: Decimal
    version: int


class AmountRequest(BaseModel):
    amount: StrictStr


class TransferRequest(BaseModel):
    source_wallet_id: UUID
    destination_wallet_id: UUID
    amount: StrictStr


class FeeCalculationRequest(BaseModel):
    amount: StrictStr


class FeeCalculationResponse(BaseModel):
    amount: Decimal
    fee_amount: Decimal
    total_debit: Decimal
    currency: str
    rule_id: UUID | None
    rule_name: str | None


class ChannelCallbackRequest(BaseModel):
    event_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    transaction_id: UUID
    status: str = Field(pattern=r"^(SUCCEEDED|FAILED)$")


class ChannelCallbackResponse(BaseModel):
    event_id: str
    transaction_id: UUID
    transaction_status: str
    outcome: str
    duplicate_count: int


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    status: str
    source_wallet_id: UUID | None
    destination_wallet_id: UUID | None
    parent_transaction_id: UUID | None
    amount: Decimal
    fee_amount: Decimal
    currency: str
    trace_id: str
    failure_code: str | None
    failure_message: str | None
    created_at: datetime
    completed_at: datetime | None
