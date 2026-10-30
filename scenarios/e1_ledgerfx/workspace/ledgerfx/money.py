"""Money values and rounding to each currency's minor units."""
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

# Decimal places of each currency's minor unit (ISO 4217).
MINOR_UNITS = {
    "EUR": 2,
    "USD": 2,
    "GBP": 2,
    "CHF": 2,
    "SEK": 2,
    "HUF": 2,
    "RON": 2,
    "JPY": 0,
}


class UnknownCurrency(KeyError):
    """A currency code that ledgerfx, or a rate table, doesn't know."""

    def __str__(self):
        return f"unknown currency: {self.args[0]}"


def minor_units(currency: str) -> int:
    try:
        return MINOR_UNITS[currency]
    except KeyError:
        raise UnknownCurrency(currency) from None


def quantize(amount, currency: str) -> Decimal:
    """Round to the currency's minor units, half to even (banker's rounding), as the ledger does."""
    step = Decimal(1).scaleb(-minor_units(currency))
    return Decimal(str(amount)).quantize(step, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self):
        object.__setattr__(self, "amount", Decimal(str(self.amount)))
        minor_units(self.currency)  # raises UnknownCurrency

    def rounded(self) -> "Money":
        return Money(quantize(self.amount, self.currency), self.currency)

    def __add__(self, other: "Money") -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        if other.currency != self.currency:
            raise ValueError(f"cannot add {self.currency} and {other.currency}")
        return Money(self.amount + other.amount, self.currency)

    def __str__(self):
        return f"{self.rounded().amount} {self.currency}"
