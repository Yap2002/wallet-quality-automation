from uuid import UUID

from fastapi import APIRouter, Request, status

from app.api.dependencies import CurrentUser, DatabaseSession, IdempotencyKey
from app.api.schemas import AmountRequest, TransactionResponse
from app.application.idempotency import execute_idempotently
from app.application.wallet_service import get_transaction_for_user, refund_transfer
from app.infrastructure.cache import record_transaction_status

router = APIRouter(prefix="/api/v1/transactions", tags=["transactions"])


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> TransactionResponse:
    transaction = get_transaction_for_user(
        session,
        transaction_id,
        current_user.id,
    )
    record_transaction_status(transaction.id, transaction.status)
    return TransactionResponse.model_validate(transaction)


@router.post(
    "/{transaction_id}/refunds",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_refund(
    transaction_id: UUID,
    payload: AmountRequest,
    request: Request,
    session: DatabaseSession,
    current_user: CurrentUser,
    idempotency_key: IdempotencyKey,
) -> TransactionResponse:
    refund = execute_idempotently(
        session,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        operation="REFUND",
        payload={"transaction_id": str(transaction_id), "amount": payload.amount},
        action=lambda: refund_transfer(
            session,
            transaction_id,
            current_user.id,
            payload.amount,
            request.state.trace_id,
        ),
    )
    return TransactionResponse.model_validate(refund)
