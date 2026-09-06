from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.exceptions import ConflictError, ResourceNotFoundError
from app.application.wallet_service import apply_channel_deposit_success
from app.domain.transaction import TransactionStatus, TransactionType, transition
from app.infrastructure.database.models import (
    CallbackOutcome,
    ChannelCallbackModel,
    TransactionModel,
)


@dataclass(frozen=True, slots=True)
class CallbackResult:
    event_id: str
    transaction_id: UUID
    transaction_status: str
    outcome: str
    duplicate_count: int


def process_channel_callback(
    session: Session,
    *,
    event_id: str,
    transaction_id: UUID,
    received_status: str,
    inject_failure: bool,
) -> CallbackResult:
    existing = session.scalar(
        select(ChannelCallbackModel)
        .where(ChannelCallbackModel.event_id == event_id)
        .with_for_update()
    )
    if existing is not None:
        if existing.transaction_id != transaction_id or existing.received_status != received_status:
            raise ConflictError(
                code="CALLBACK_EVENT_CONFLICT",
                message="the callback event id was reused with different data",
            )
        existing.duplicate_count += 1
        transaction = session.get(TransactionModel, existing.transaction_id)
        if transaction is None:
            raise RuntimeError("callback references a missing transaction")
        session.flush()
        return _result(existing, transaction, "DUPLICATE")

    try:
        with session.begin_nested():
            transaction = session.scalar(
                select(TransactionModel)
                .where(TransactionModel.id == transaction_id)
                .with_for_update()
            )
            if transaction is None:
                raise ResourceNotFoundError("transaction")
            if transaction.type != TransactionType.DEPOSIT.value:
                raise ConflictError(
                    code="CALLBACK_TRANSACTION_TYPE_INVALID",
                    message="channel callbacks only support channel deposit transactions",
                )

            if transaction.status != TransactionStatus.PROCESSING.value:
                callback = ChannelCallbackModel(
                    event_id=event_id,
                    transaction_id=transaction.id,
                    received_status=received_status,
                    outcome=CallbackOutcome.IGNORED_TERMINAL.value,
                )
                session.add(callback)
                session.flush()
                return _result(callback, transaction, callback.outcome)

            if inject_failure:
                raise RuntimeError("injected failure before local channel update")

            if received_status == TransactionStatus.SUCCEEDED.value:
                apply_channel_deposit_success(session, transaction)
            else:
                transaction.status = transition(
                    TransactionStatus(transaction.status),
                    TransactionStatus.FAILED,
                ).value
                transaction.failure_code = "CHANNEL_REPORTED_FAILURE"
                transaction.failure_message = "the simulated channel reported failure"

            callback = ChannelCallbackModel(
                event_id=event_id,
                transaction_id=transaction.id,
                received_status=received_status,
                outcome=CallbackOutcome.APPLIED.value,
            )
            session.add(callback)
            session.flush()
            return _result(callback, transaction, callback.outcome)
    except IntegrityError as error:
        raise ConflictError(
            code="CALLBACK_EVENT_CONFLICT",
            message="the callback event is being processed concurrently",
        ) from error


def _result(
    callback: ChannelCallbackModel,
    transaction: TransactionModel,
    outcome: str,
) -> CallbackResult:
    return CallbackResult(
        event_id=callback.event_id,
        transaction_id=transaction.id,
        transaction_status=transaction.status,
        outcome=outcome,
        duplicate_count=callback.duplicate_count,
    )
