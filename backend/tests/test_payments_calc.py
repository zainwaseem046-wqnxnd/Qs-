"""Golden values for the payment application / valuation engine (pure functions, no database)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

from app.domains.payments import calc


def _app1() -> list[calc.LineResult]:
    # SOV: two contract lines, an approved addition and an approved omission; retention 5%.
    return [
        calc.line(D("100000.00"), D("0.00"), D("40000.00"), D("0.00"), D("5")),
        calc.line(D("50000.00"), D("0.00"), D("0.00"), D("7500.00"), D("5")),  # materials on site only
        calc.line(D("12500.00"), D("0.00"), D("0.00"), D("0.00"), D("5")),
        calc.line(D("-4000.00"), D("0.00"), D("-1000.00"), D("0.00"), D("5")),
    ]


def test_first_application_golden_values() -> None:
    lines = _app1()
    assert [x.completed_to_date for x in lines] == [D("40000.00"), D("7500.00"), D("0.00"), D("-1000.00")]
    assert [x.retention for x in lines] == [D("2000.00"), D("375.00"), D("0.00"), D("-50.00")]
    assert lines[0].percent_complete == D("40.00") and lines[0].balance_to_finish == D("60000.00")
    assert lines[3].percent_complete == D("25.00")
    t = calc.totals(lines, D("150000.00"), D("8500.00"), D("0.00"))
    assert t.contract_sum_to_date == D("158500.00")
    assert (t.work_to_date, t.materials_stored, t.completed_to_date) == (D("39000.00"), D("7500.00"), D("46500.00"))
    assert t.retention == D("2325.00") and t.earned_less_retention == D("44175.00")
    assert t.amount_due == D("44175.00")
    assert t.balance_to_finish == D("114325.00")  # contract sum - earned less retention
    assert t.percent_complete == D("29.34")  # 46,500 / 158,500 = 29.337...


def test_second_application_reclaims_what_the_certifier_cut() -> None:
    # App 1 applied for 44,175.00 but only 40,000.00 was certified. On app 2 the stored materials are installed,
    # the addition is complete and the omission is fully taken.
    lines = [
        calc.line(D("100000.00"), D("40000.00"), D("10000.00"), D("0.00"), D("5")),
        calc.line(D("50000.00"), D("0.00"), D("7500.00"), D("0.00"), D("5")),
        calc.line(D("12500.00"), D("0.00"), D("12500.00"), D("0.00"), D("5")),
        calc.line(D("-4000.00"), D("-1000.00"), D("-3000.00"), D("0.00"), D("5")),
    ]
    t = calc.totals(lines, D("150000.00"), D("8500.00"), D("40000.00"))
    assert t.completed_to_date == D("66000.00") and t.materials_stored == D("0.00")
    assert t.retention == D("3300.00") and t.earned_less_retention == D("62700.00")
    assert t.amount_due == D("22700.00")  # = 18,525.00 new value earned + 4,175.00 previously cut


def test_rounding_is_half_up_once_per_line() -> None:
    x = calc.line(D("333.33"), D("0.00"), calc.this_period_from_percent(D("333.33"), D("33.33"), D("0"), D("0")),
                  D("0.00"), D("5"))
    assert x.this_period == D("111.10")  # 333.33 x 33.33% = 111.0989
    assert x.retention == D("5.56")  # 5.555 -> 5.56
    neg = calc.line(D("-20.20"), D("0.00"), D("-10.10"), D("0.00"), D("5"))
    assert neg.retention == D("-0.51")  # -0.505 rounds away from zero
    # percent to date is applied to work + stored, net of previous work
    assert calc.this_period_from_percent(D("1000.00"), D("60"), D("300.00"), D("100.00")) == D("200.00")


def test_line_limits() -> None:
    assert calc.line_errors(D("100.00"), D("90.00"), D("10.00"), D("0.00")) == []
    assert "exceed" in calc.line_errors(D("100.00"), D("90.00"), D("20.00"), D("0.00"))[0]
    assert "negative" in calc.line_errors(D("100.00"), D("50.00"), D("-60.00"), D("0.00"))[0]
    assert calc.line_errors(D("100.00"), D("50.00"), D("-20.00"), D("0.00")) == []  # correcting an over-claim
    assert "negative" in calc.line_errors(D("100.00"), D("0.00"), D("0.00"), D("-1.00"))[0]
    assert calc.line_errors(D("-4000.00"), D("-1000.00"), D("-3000.00"), D("0.00")) == []
    assert calc.line_errors(D("-4000.00"), D("0.00"), D("-5000.00"), D("0.00"))
    assert calc.line_errors(D("-4000.00"), D("0.00"), D("1.00"), D("0.00"))
    assert calc.line_errors(D("-4000.00"), D("0.00"), D("0.00"), D("10.00"))


def test_billing_position_and_payment_dates() -> None:
    assert calc.billing_position(D("100.00"), D("80.00")) == (D("20.00"), D("0.00"))
    assert calc.billing_position(D("80.00"), D("100.00")) == (D("0.00"), D("20.00"))
    assert calc.billing_position(D("80.00"), D("80.00")) == (D("0.00"), D("0.00"))
    assert calc.payment_dates(date(2026, 11, 7), 14) == (date(2026, 11, 21), date(2026, 11, 16))
    assert calc.payment_dates(date(2026, 11, 7), None) == (date(2026, 11, 21), date(2026, 11, 16))
    assert calc.payment_dates(date(2026, 11, 7), 30, pay_less_days=7) == (date(2026, 12, 7), date(2026, 11, 30))


def test_zero_scheduled_value_has_no_percent() -> None:
    x = calc.line(D("0.00"), D("0.00"), D("0.00"), D("0.00"), D("10"))
    assert x.percent_complete is None and x.retention == D("0.00")
    t = calc.totals([x], D("0.00"), D("0.00"), D("0.00"))
    assert t.percent_complete is None and t.amount_due == D("0.00")
