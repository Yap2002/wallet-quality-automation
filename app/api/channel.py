from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Request, status

from app.api.dependencies import CurrentUser, DatabaseSession, IdempotencyKey
from app.api.schemas import (
    AmountRequest,
    ChannelCallbackRequest,
    ChannelCallbackResponse,
    TransactionResponse,
)
from app.application.channel_service import process_channel_callback
from app.application.exceptions import AuthenticationError, PermissionDeniedError
from app.application.idempotency import execute_idempotently
from app.application.wallet_service import create_channel_deposit
from app.config import settings
from app.infrastructure.cache import record_transaction_status

router = APIRouter(prefix="/api/v1", tags=["channel simulation"])


@router.post(
    "/wallets/{wallet_id}/channel-deposits",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_channel_deposit(
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
        operation="CHANNEL_DEPOSIT",
        payload={"wallet_id": str(wallet_id), "amount": payload.amount},
        action=lambda: create_channel_deposit(
            session,
            wallet_id,
            current_user.id,
            payload.amount,
            request.state.trace_id,
        ),
    )
    return TransactionResponse.model_validate(transaction)


@router.post("/callbacks/channel", response_model=ChannelCallbackResponse)
def receive_channel_callback(
    payload: ChannelCallbackRequest,
    session: DatabaseSession,
    channel_token: Annotated[str | None, Header(alias="X-Channel-Token")] = None,
    fault_point: Annotated[str | None, Header(alias="X-Test-Fault")] = None,
) -> ChannelCallbackResponse:
    if channel_token is None:
        raise AuthenticationError
    if channel_token != settings.channel_callback_token:
        raise PermissionDeniedError
    inject_failure = fault_point == "BEFORE_LOCAL_UPDATE"
    if inject_failure and settings.app_env not in {"local", "test"}:
        raise PermissionDeniedError
    result = process_channel_callback(
        session,
        event_id=payload.event_id,
        transaction_id=payload.transaction_id,
        received_status=payload.status,
        inject_failure=inject_failure,
    )
    record_transaction_status(result.transaction_id, result.transaction_status)
    return ChannelCallbackResponse(
        event_id=result.event_id,
        transaction_id=result.transaction_id,
        transaction_status=result.transaction_status,
        outcome=result.outcome,
        duplicate_count=result.duplicate_count,
    )
