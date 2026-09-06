import hashlib
import json
from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.exceptions import ApplicationError, ConflictError
from app.infrastructure.database.models import (
    IdempotencyRecordModel,
    IdempotencyStatus,
    TransactionModel,
)


def execute_idempotently(
    session: Session,
    *,
    user_id: UUID,
    idempotency_key: str,
    operation: str,
    payload: dict[str, Any],
    action: Callable[[], TransactionModel],
) -> TransactionModel:
    request_hash = _request_hash(operation, payload)
    record, created = _claim_record(
        session,
        user_id=user_id,
        idempotency_key=idempotency_key,
        operation=operation,
        request_hash=request_hash,
    )
    if not created:
        return _replay(session, record, request_hash)

    try:
        with session.begin_nested():
            transaction = action()
    except ApplicationError as error:
        record.status = IdempotencyStatus.FAILED.value
        record.response_status = error.status_code
        record.error_code = error.code
        record.error_message = error.message
        session.commit()
        raise

    record.status = IdempotencyStatus.COMPLETED.value
    record.response_status = 201
    record.transaction_id = transaction.id
    session.flush()
    return transaction


def _claim_record(
    session: Session,
    *,
    user_id: UUID,
    idempotency_key: str,
    operation: str,
    request_hash: str,
) -> tuple[IdempotencyRecordModel, bool]:
    record = IdempotencyRecordModel(
        user_id=user_id,
        idempotency_key=idempotency_key,
        operation=operation,
        request_hash=request_hash,
        status=IdempotencyStatus.PROCESSING.value,
    )
    try:
        with session.begin_nested():
            session.add(record)
            session.flush()
        return record, True
    except IntegrityError:
        existing = session.scalar(
            select(IdempotencyRecordModel)
            .where(
                IdempotencyRecordModel.user_id == user_id,
                IdempotencyRecordModel.idempotency_key == idempotency_key,
            )
            .with_for_update()
        )
        if existing is None:
            raise
        return existing, False


def _replay(
    session: Session,
    record: IdempotencyRecordModel,
    request_hash: str,
) -> TransactionModel:
    if record.request_hash != request_hash:
        raise ConflictError(
            code="IDEMPOTENCY_KEY_CONFLICT",
            message="the idempotency key was already used with different request data",
        )
    if record.status == IdempotencyStatus.FAILED.value:
        raise ApplicationError(
            code=record.error_code or "IDEMPOTENT_REQUEST_FAILED",
            message=record.error_message or "the original request failed",
            status_code=record.response_status or 409,
        )
    if record.status != IdempotencyStatus.COMPLETED.value or record.transaction_id is None:
        raise ConflictError(
            code="IDEMPOTENCY_REQUEST_IN_PROGRESS",
            message="the original request is still processing",
        )
    transaction = session.get(TransactionModel, record.transaction_id)
    if transaction is None:
        raise RuntimeError("idempotency record references a missing transaction")
    return transaction


def _request_hash(operation: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        {"operation": operation, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
