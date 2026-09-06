from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Self

from app.domain.exceptions import InvalidMoneyError

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class FeePolicy:
    fixed_fee: Decimal = ZERO
    percentage_rate: Decimal = ZERO
    minimum_fee: Decimal | None = None
    maximum_fee: Decimal | None = None
    is_fee_free: bool = False

    def __post_init__(self) -> None:
        values = (self.fixed_fee, self.percentage_rate, self.minimum_fee, self.maximum_fee)
        if any(value is not None and value < ZERO for value in values):
            raise InvalidMoneyError("fee values must not be negative")
        if (
            self.minimum_fee is not None
            and self.maximum_fee is not None
            and self.minimum_fee > self.maximum_fee
        ):
            raise InvalidMoneyError("minimum fee must not exceed maximum fee")

    @classmethod
    def from_values(
        cls,
        *,
        fixed_fee: Decimal,
        percentage_rate: Decimal,
        minimum_fee: Decimal | None,
        maximum_fee: Decimal | None,
        is_fee_free: bool,
    ) -> Self:
        return cls(
            fixed_fee=fixed_fee,
            percentage_rate=percentage_rate,
            minimum_fee=minimum_fee,
            maximum_fee=maximum_fee,
            is_fee_free=is_fee_free,
        )

    def calculate(self, amount: Decimal) -> Decimal:
        if amount <= ZERO:
            raise InvalidMoneyError("fee base amount must be greater than zero")
        if self.is_fee_free:
            return ZERO

        fee = self.fixed_fee + amount * self.percentage_rate
        if self.minimum_fee is not None:
            fee = max(fee, self.minimum_fee)
        if self.maximum_fee is not None:
            fee = min(fee, self.maximum_fee)
        return fee.quantize(CENT, rounding=ROUND_HALF_UP)
