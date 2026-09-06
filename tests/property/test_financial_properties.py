from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from app.domain.fee import FeePolicy
from app.domain.money import Money


@given(minor_units=st.integers(min_value=1, max_value=100_000_000_00))
def test_any_valid_cent_amount_round_trips_without_precision_loss(
    minor_units: int,
) -> None:
    amount = Decimal(minor_units) / Decimal(100)

    money = Money.from_value(str(amount))

    assert money.as_minor_units() == minor_units
    assert money.amount >= Decimal("0.01")


@given(
    amount_minor=st.integers(min_value=1, max_value=10_000_000),
    fixed_minor=st.integers(min_value=0, max_value=100_000),
    rate_millionths=st.integers(min_value=0, max_value=100_000),
)
def test_fee_is_non_negative_and_always_rounded_to_cents(
    amount_minor: int,
    fixed_minor: int,
    rate_millionths: int,
) -> None:
    amount = Decimal(amount_minor) / Decimal(100)
    policy = FeePolicy(
        fixed_fee=Decimal(fixed_minor) / Decimal(100),
        percentage_rate=Decimal(rate_millionths) / Decimal(1_000_000),
    )

    fee = policy.calculate(amount)

    assert fee >= Decimal("0.00")
    assert fee.as_tuple().exponent == -2


@given(
    amount_minor=st.integers(min_value=1, max_value=10_000_000),
    minimum_minor=st.integers(min_value=0, max_value=10_000),
    extra_minor=st.integers(min_value=0, max_value=10_000),
)
def test_fee_respects_valid_minimum_and_maximum_bounds(
    amount_minor: int,
    minimum_minor: int,
    extra_minor: int,
) -> None:
    minimum = Decimal(minimum_minor) / Decimal(100)
    maximum = Decimal(minimum_minor + extra_minor) / Decimal(100)
    policy = FeePolicy(
        percentage_rate=Decimal("0.025"),
        minimum_fee=minimum,
        maximum_fee=maximum,
    )

    fee = policy.calculate(Decimal(amount_minor) / Decimal(100))

    assert minimum <= fee <= maximum
