from dataclasses import dataclass
from decimal import Decimal
from typing import Self

from app.domain.exceptions import InvalidMoneyError

_MINOR_UNIT = Decimal("0.01")
_MAX_AMOUNT = Decimal("999999999999999999.99")


@dataclass(frozen=True, slots=True)
class Money:
    """A positive CNY amount with at most two decimal places."""

    amount: Decimal
    currency: str = "CNY"

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise InvalidMoneyError("amount must be created from Decimal or a decimal string")
        if not self.amount.is_finite():
            raise InvalidMoneyError("amount must be finite")
        if self.amount <= 0:
            raise InvalidMoneyError("amount must be greater than zero")
        if self.amount > _MAX_AMOUNT:
            raise InvalidMoneyError("amount exceeds the supported database limit")
        exponent = self.amount.as_tuple().exponent
        if not isinstance(exponent, int):
            raise InvalidMoneyError("amount must be finite")
        if exponent < -2:
            raise InvalidMoneyError("CNY amount must have at most two decimal places")
        if self.currency != "CNY":
            raise InvalidMoneyError("only CNY is supported in the first version")

    @classmethod
    def from_value(cls, value: str | Decimal, currency: str = "CNY") -> Self:
        """Create money without accepting binary floating-point input."""
        if isinstance(value, (bool, float)):
            raise InvalidMoneyError("float and bool inputs are forbidden for money")
        if not isinstance(value, (str, Decimal)):
            raise InvalidMoneyError("amount must be a decimal string or Decimal")
        try:
            amount = Decimal(value)
        except Exception as error:
            raise InvalidMoneyError("amount must be a valid decimal number") from error
        return cls(amount=amount, currency=currency)

    def as_minor_units(self) -> int:
        """Return the exact amount in fen for persistence and assertions."""
        return int(self.amount / _MINOR_UNIT)
