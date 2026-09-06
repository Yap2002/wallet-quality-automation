from decimal import Decimal

import pytest

from app.domain.exceptions import InvalidMoneyError
from app.domain.money import Money


@pytest.mark.parametrize(
    ("raw_amount", "expected"),
    [
        ("10", Decimal("10")),
        ("10.2", Decimal("10.2")),
        ("10.25", Decimal("10.25")),
        (Decimal("0.01"), Decimal("0.01")),
    ],
)
def test_create_valid_cny_money(raw_amount: str | Decimal, expected: Decimal) -> None:
    money = Money.from_value(raw_amount)

    assert money.amount == expected
    assert money.currency == "CNY"


@pytest.mark.parametrize(
    "raw_amount",
    [
        "0",
        "-0.01",
        "10.001",
        "NaN",
        "Infinity",
        "",
        "not-a-number",
        "0.002",
        "1000000000000000000.00",
    ],
)
def test_reject_invalid_decimal_amounts(raw_amount: str) -> None:
    with pytest.raises(InvalidMoneyError):
        Money.from_value(raw_amount)


@pytest.mark.parametrize("raw_amount", [0.1, 1.0, True])
def test_reject_float_and_bool_inputs(raw_amount: object) -> None:
    with pytest.raises(InvalidMoneyError, match="float and bool"):
        Money.from_value(raw_amount)  # type: ignore[arg-type]


def test_reject_unsupported_currency() -> None:
    with pytest.raises(InvalidMoneyError, match="only CNY"):
        Money.from_value("10.00", currency="USD")


def test_convert_exact_amount_to_minor_units() -> None:
    assert Money.from_value("10.25").as_minor_units() == 1025
