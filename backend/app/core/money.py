"""Deterministic money and quantity arithmetic.

Rules (see docs/DECISION_LOG.md ADR-006):

* Monetary values are ``decimal.Decimal`` in Python and ``NUMERIC`` in PostgreSQL. Floats are rejected.
* Stored currency amounts use 2 decimal places (``NUMERIC(19,2)``) for USD. Unit rates use 6 places
  (``NUMERIC(19,6)``) and quantities 4 places (``NUMERIC(19,4)``) so that unit-rate build-ups do not
  lose precision before the final extended amount is rounded.
* Rounding is ROUND_HALF_UP (the convention used on US commercial documents and pay applications),
  applied once at the defined rounding point, never implicitly.
* Amounts in different currencies are never added together.
* JSON serialisation uses strings ("1234.50") so no client parses money as a binary float.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Annotated, Any

from pydantic import BeforeValidator, PlainSerializer

MONEY_PLACES = Decimal("0.01")
RATE_PLACES = Decimal("0.000001")
QUANTITY_PLACES = Decimal("0.0001")
PERCENT_PLACES = Decimal("0.01")

MAX_MONEY = Decimal("99999999999999999.99")  # fits NUMERIC(19,2)

# ISO 4217 currencies currently enabled. USD is the default; others are accepted for future expansion.
SUPPORTED_CURRENCIES = frozenset({"USD", "CAD", "GBP", "EUR", "AUD", "MXN"})


class MoneyError(ValueError):
    pass


def to_decimal(value: Any) -> Decimal:
    """Convert an input to Decimal without ever passing through binary floating point."""
    if isinstance(value, bool):
        raise MoneyError("Boolean is not a valid monetary value")
    if isinstance(value, float):
        raise MoneyError("Floating-point values are not accepted for monetary amounts; send a string")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int):
        result = Decimal(value)
    elif isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if not cleaned:
            raise MoneyError("Empty monetary value")
        try:
            result = Decimal(cleaned)
        except InvalidOperation as exc:
            raise MoneyError(f"Invalid decimal value: {value!r}") from exc
    else:
        raise MoneyError(f"Unsupported monetary type: {type(value).__name__}")
    if not result.is_finite():
        raise MoneyError("Monetary values must be finite")
    return result


def round_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def round_rate(value: Decimal) -> Decimal:
    return value.quantize(RATE_PLACES, rounding=ROUND_HALF_UP)


def round_quantity(value: Decimal) -> Decimal:
    return value.quantize(QUANTITY_PLACES, rounding=ROUND_HALF_UP)


def extend(quantity: Decimal, unit_rate: Decimal) -> Decimal:
    """Extended amount = quantity x unit rate, rounded once to cents."""
    return round_money(quantity * unit_rate)


def percent_of(amount: Decimal, percent: Decimal) -> Decimal:
    """Return ``percent`` % of ``amount`` rounded to cents (e.g. retainage, markup)."""
    return round_money(amount * percent / Decimal(100))


def margin_percent(profit: Decimal, revenue: Decimal) -> Decimal | None:
    """Gross margin % = profit / revenue x 100. Undefined (None) when revenue is zero."""
    if revenue == 0:
        return None
    return (profit / revenue * Decimal(100)).quantize(PERCENT_PLACES, rounding=ROUND_HALF_UP)


def _validate_money(value: Any) -> Decimal:
    result = round_money_strict(to_decimal(value))
    return result


def round_money_strict(value: Decimal) -> Decimal:
    """Reject (rather than silently round) amounts with more than 2 decimal places."""
    if value != value.quantize(MONEY_PLACES):
        raise MoneyError("Monetary amounts may have at most 2 decimal places")
    if abs(value) > MAX_MONEY:
        raise MoneyError("Monetary amount out of range")
    return value.quantize(MONEY_PLACES)


def _validate_currency(value: Any) -> str:
    if not isinstance(value, str) or value.upper() not in SUPPORTED_CURRENCIES:
        raise MoneyError(f"Unsupported currency; expected one of {sorted(SUPPORTED_CURRENCIES)}")
    return value.upper()


# Pydantic field types --------------------------------------------------------------------------
MoneyAmount = Annotated[
    Decimal,
    BeforeValidator(_validate_money),
    PlainSerializer(lambda v: format(v, "f"), return_type=str, when_used="json"),
]
CurrencyCode = Annotated[str, BeforeValidator(_validate_currency)]


def _fixed(places: Decimal, label: str, minimum: Decimal | None = None, maximum: Decimal | None = None):  # type: ignore[no-untyped-def]
    """Validator factory for non-money decimals (quantities, unit rates, percentages)."""

    def check(value: Any) -> Decimal:
        result = to_decimal(value)
        if result != result.quantize(places):
            raise MoneyError(f"{label} may have at most {abs(places.as_tuple().exponent)} decimal places")
        if minimum is not None and result < minimum:
            raise MoneyError(f"{label} must be at least {minimum}")
        if maximum is not None and result > maximum:
            raise MoneyError(f"{label} must be at most {maximum}")
        return result.quantize(places)

    return check


_SERIALIZE = PlainSerializer(lambda v: format(v, "f"), return_type=str, when_used="json")
Quantity = Annotated[
    Decimal, BeforeValidator(_fixed(QUANTITY_PLACES, "Quantity", Decimal(0), Decimal("999999999999999"))), _SERIALIZE
]
UnitRate = Annotated[
    Decimal, BeforeValidator(_fixed(RATE_PLACES, "Rate", Decimal(0), Decimal("9999999999999"))), _SERIALIZE
]
Percent = Annotated[
    Decimal, BeforeValidator(_fixed(PERCENT_PLACES, "Percentage", Decimal(0), Decimal(100))), _SERIALIZE
]
MarkupPercent = Annotated[
    Decimal, BeforeValidator(_fixed(Decimal("0.0001"), "Percentage", Decimal(0), Decimal(1000))), _SERIALIZE
]
DecimalOut = Annotated[Decimal, _SERIALIZE]
SignedQuantity = Annotated[Decimal, BeforeValidator(_fixed(QUANTITY_PLACES, "Quantity", Decimal("-999999999999999"),
                                                           Decimal("999999999999999"))), _SERIALIZE]
