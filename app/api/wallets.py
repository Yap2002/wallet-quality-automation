from uuid import UUID

from fastapi import APIRouter, Request, status

from app.api.dependencies import CurrentUser, DatabaseSession, IdempotencyKey
from app.api.schemas import AmountRequest, TransactionResponse, WalletResponse
from app.application.idempotency import execute_idempotently
from app.application.wallet_service import (
    deposit,
    get_wallet_for_user,
    withdraw,
)

router = APIRouter(prefix="/api/v1/wallets", tags=["wallets"])


@router.get("/{wallet_id}", response_model=WalletResponse)
def get_wallet(
    wallet_id: UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> WalletResponse:
    wallet = get_wallet_for_user(session, wallet_id, current_user.id)
    return WalletResponse.model_validate(wallet)


@router.post(
    "/{wallet_id}/deposits",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_deposit(
    wallet_id: UUID,
    payload: AmountRequest,
    request: Request,
    session: DatabaseSession,
    current_user: CurrentUser,
    idempotency_key: IdempotencyKey,
) -> TransactionResponse:
    transaction = execute_idempotently(
        session,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        operation="DEPOSIT",
        payload={"wallet_id": str(wallet_id), "amount": payload.amount},
        action=lambda: deposit(
            session,
            wallet_id,
            current_user.id,
            payload.amount,
            request.state.trace_id,
        ),
    )
    return TransactionResponse.model_validate(transaction)


@router.post(
    "/{wallet_id}/withdrawals",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_withdrawal(
    wallet_id: UUID,
    payload: AmountRequest,
    request: Request,
    session: DatabaseSession,
    current_user: CurrentUser,
    idempotency_key: IdempotencyKey,
) -> TransactionResponse:
    transaction = execute_idempotently(
        session,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        operation="WITHDRAWAL",
        payload={"wallet_id": str(wallet_id), "amount": payload.amount},
        action=lambda: withdraw(
            session,
            wallet_id,
            current_user.id,
            payload.amount,
            request.state.trace_id,
        ),
    )
    return TransactionResponse.model_validate(transaction)
