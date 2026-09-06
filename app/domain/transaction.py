from enum import StrEnum

from app.domain.exceptions import InvalidStateTransitionError


class TransactionType(StrEnum):
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    TRANSFER = "TRANSFER"
    REFUND = "REFUND"


class TransactionStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


_ALLOWED_TRANSITIONS: dict[TransactionStatus, frozenset[TransactionStatus]] = {
    TransactionStatus.PENDING: frozenset({TransactionStatus.PROCESSING, TransactionStatus.FAILED}),
    TransactionStatus.PROCESSING: frozenset(
        {TransactionStatus.SUCCEEDED, TransactionStatus.FAILED}
    ),
    TransactionStatus.SUCCEEDED: frozenset({TransactionStatus.REFUNDED}),
    TransactionStatus.FAILED: frozenset(),
    TransactionStatus.REFUNDED: frozenset(),
}


def can_transition(current: TransactionStatus, target: TransactionStatus) -> bool:
    """Return whether the state machine permits a transition."""
    return target in _ALLOWED_TRANSITIONS[current]


def transition(current: TransactionStatus, target: TransactionStatus) -> TransactionStatus:
    """Validate and return the next state."""
    if not can_transition(current, target):
        raise InvalidStateTransitionError(
            f"illegal transaction state transition: {current.value} -> {target.value}"
        )
    return target
