import pytest

from app.domain.exceptions import InvalidStateTransitionError
from app.domain.transaction import TransactionStatus, can_transition, transition


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (TransactionStatus.PENDING, TransactionStatus.PROCESSING),
        (TransactionStatus.PENDING, TransactionStatus.FAILED),
        (TransactionStatus.PROCESSING, TransactionStatus.SUCCEEDED),
        (TransactionStatus.PROCESSING, TransactionStatus.FAILED),
        (TransactionStatus.SUCCEEDED, TransactionStatus.REFUNDED),
    ],
)
def test_allow_valid_state_transitions(
    current: TransactionStatus,
    target: TransactionStatus,
) -> None:
    assert can_transition(current, target)
    assert transition(current, target) is target


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (TransactionStatus.SUCCEEDED, TransactionStatus.PROCESSING),
        (TransactionStatus.FAILED, TransactionStatus.SUCCEEDED),
        (TransactionStatus.REFUNDED, TransactionStatus.SUCCEEDED),
        (TransactionStatus.PENDING, TransactionStatus.SUCCEEDED),
        (TransactionStatus.PROCESSING, TransactionStatus.PROCESSING),
    ],
)
def test_reject_invalid_state_transitions(
    current: TransactionStatus,
    target: TransactionStatus,
) -> None:
    with pytest.raises(
        InvalidStateTransitionError,
        match=f"{current.value} -> {target.value}",
    ):
        transition(current, target)
