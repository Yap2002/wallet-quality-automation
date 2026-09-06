from decimal import Decimal

import pytest

from app.domain.exceptions import InvalidMoneyError
from app.domain.fee import FeePolicy


@pytest.mark.parametrize(
    ("policy", "amount", "expected"),
    [
        (FeePolicy(fixed_fee=Decimal("2.00")), Decimal("100.00"), Decimal("2.00")),
        (
            FeePolicy(percentage_rate=Decimal("0.015")),
            Decimal("100.00"),
            Decimal("1.50"),
        ),
        (
            FeePolicy(fixed_fee=Decimal("1.00"), percentage_rate=Decimal("0.02")),
            Decimal("100.00"),
            Decimal("3.00"),
        ),
        (
            FeePolicy(percentage_rate=Decimal("0.001"), minimum_fee=Decimal("0.50")),
            Decimal("100.00"),
            Decimal("0.50"),
        ),
        (
            FeePolicy(percentage_rate=Decimal("0.10"), maximum_fee=Decimal("5.00")),
            Decimal("100.00"),
            Decimal("5.00"),
        ),
        (
            FeePolicy(fixed_fee=Decimal("9.00"), is_fee_free=True),
            Decimal("100.00"),
            Decimal("0.00"),
        ),
        (
            FeePolicy(percentage_rate=Decimal("0.005")),
            Decimal("1.00"),
            Decimal("0.01"),
        ),
    ],
)
def test_calculate_fee(policy: FeePolicy, amount: Decimal, expected: Decimal) -> None:
    assert policy.calculate(amount) == expected


def test_round_fee_half_up_to_cent() -> None:
    policy = FeePolicy(percentage_rate=Decimal("0.005"))

    assert policy.calculate(Decimal("3.00")) == Decimal("0.02")


@pytest.mark.parametrize(
    "policy",
    [
        FeePolicy(fixed_fee=Decimal("0.00")),
    ],
)
def test_reject_non_positive_fee_base(policy: FeePolicy) -> None:
    with pytest.raises(InvalidMoneyError, match="greater than zero"):
        policy.calculate(Decimal("0.00"))


def test_reject_invalid_fee_bounds() -> None:
    with pytest.raises(InvalidMoneyError, match="minimum fee"):
        FeePolicy(minimum_fee=Decimal("2.00"), maximum_fee=Decimal("1.00"))
