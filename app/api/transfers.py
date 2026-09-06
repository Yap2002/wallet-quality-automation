from fastapi import APIRouter, Request, status

from app.api.dependencies import CurrentUser, DatabaseSession, IdempotencyKey
from app.api.schemas import TransactionResponse, TransferRequest
from app.application.idempotency import execute_idempotently
from app.application.wallet_service import transfer

router = APIRouter(prefix="/api/v1/transfers", tags=["transfers"])


@router.post(
    "",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_transfer(
    payload: TransferRequest,
    request: Request,
    session: DatabaseSession,
    current_user: CurrentUser,
    idempotency_key: IdempotencyKey,
) -> TransactionResponse:
    transaction = execute_idempotently(
        session,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        operation="TRANSFER",
        payload={
            "source_wallet_id": str(payload.source_wallet_id),
            "destination_wallet_id": str(payload.destination_wallet_id),
            "amount": payload.amount,
        },
        action=lambda: transfer(
            session,
            payload.source_wallet_id,
            payload.destination_wallet_id,
            current_user.id,
            payload.amount,
            request.state.trace_id,
        ),
    )
    return TransactionResponse.model_validate(transaction)
