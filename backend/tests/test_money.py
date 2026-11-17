from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from app.core.money import (
    CurrencyCode,
    MoneyAmount,
    MoneyError,
    extend,
    margin_percent,
    percent_of,
    round_money,
    to_decimal,
)


class M(BaseModel):
    amount: MoneyAmount
    currency: CurrencyCode = "USD"


def test_float_inputs_are_rejected() -> None:
    with pytest.raises(MoneyError):
        to_decimal(0.1)
    with pytest.raises(ValidationError):
        M(amount=0.1)  # type: ignore[arg-type]


def test_string_and_int_inputs_are_exact() -> None:
    assert to_decimal("0.10") + to_decimal("0.20") == Decimal("0.30")
    assert to_decimal("1,250,000.10") == Decimal("1250000.10")
    assert to_decimal(5) == Decimal(5)


@pytest.mark.parametrize("bad", ["", "abc", "NaN", "Infinity", True, None, [1]])
def test_invalid_values_rejected(bad: object) -> None:
    with pytest.raises(MoneyError):
        to_decimal(bad)


def test_more_than_two_decimals_rejected_not_silently_rounded() -> None:
    with pytest.raises(ValidationError):
        M(amount="10.005")


def test_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        M(amount="100000000000000000.00")


def test_json_serialises_money_as_string() -> None:
    assert M(amount="1234.5").model_dump_json() == '{"amount":"1234.50","currency":"USD"}'


def test_currency_validation() -> None:
    assert M(amount="1", currency="usd").currency == "USD"
    with pytest.raises(ValidationError):
        M(amount="1", currency="XYZ")


@pytest.mark.parametrize(
    ("value", "expected"),
    [("2.345", "2.35"), ("2.344", "2.34"), ("-2.345", "-2.35"), ("0.005", "0.01"), ("1.995", "2.00")],
)
def test_round_half_up(value: str, expected: str) -> None:
    assert round_money(Decimal(value)) == Decimal(expected)


def test_extend_rounds_once() -> None:
    # 1,234.5678 SF x $3.456789/SF = 4267.64039... -> 4267.64
    assert extend(Decimal("1234.5678"), Decimal("3.456789")) == Decimal("4267.64")


def test_percent_of_retainage() -> None:
    assert percent_of(Decimal("123456.78"), Decimal("10")) == Decimal("12345.68")
    assert percent_of(Decimal("100.00"), Decimal("5")) == Decimal("5.00")


def test_margin_percent() -> None:
    assert margin_percent(Decimal("150000"), Decimal("1000000")) == Decimal("15.00")
    assert margin_percent(Decimal("1"), Decimal("3")) == Decimal("33.33")
    assert margin_percent(Decimal("5"), Decimal("0")) is None


def test_summing_many_cents_is_exact() -> None:
    total = sum((Decimal("0.01") for _ in range(10_000)), Decimal(0))
    assert total == Decimal("100.00")
