"""Payment application / interim valuation engine — deterministic, exact, documented. Pure functions.

Per schedule-of-values line (column letters follow the familiar G703 continuation-sheet layout; the app produces
compatible figures, it does not reproduce any licensed form):

    C  scheduled value          contract line amount, or the approved amount of a change order
    D  previous work            work completed on previous applications (their D + E)
    E  this period              work completed this period (may be negative to correct an earlier over-claim)
    F  materials stored         materials presently stored, not yet in D or E (a balance, not cumulative)
    G  completed and stored     D + E + F
       percent                  G / C x 100 (2 dp, half-up; undefined when C = 0)
    H  balance to finish        C - G
    I  retention                round2(G x retention %)

Summary (G702-compatible / UK valuation):

    1 original contract sum           executed contract lines
    2 net change by change orders     approved change orders on the contract
    3 contract sum to date            1 + 2
    4 total completed and stored      sum of G
    5 retention                       sum of I (each line rounded once, so the lines add up to the total)
    6 total earned less retention     4 - 5
    7 less previous certificates      sum of the amounts certified on earlier applications
    8 current payment due             6 - 7
    9 balance to finish incl. retention 3 - 6

Because line 7 uses what was actually certified, anything the certifier cut from an earlier application is
claimed again automatically on the next one, and nothing is ever counted twice.

Limits per line: for a positive (or zero) scheduled value, 0 <= D + E and G <= C, F >= 0. For an omission
(negative C): C <= G <= 0 and F = 0. Work can't be claimed beyond the scheduled value; extra work needs a change.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.core.money import PERCENT_PLACES, percent_of, round_money

ZERO = Decimal("0.00")
HUNDRED = Decimal(100)


@dataclass(frozen=True)
class LineResult:
    scheduled_value: Decimal
    previous_work: Decimal
    this_period: Decimal
    materials_stored: Decimal
    completed_to_date: Decimal
    percent_complete: Decimal | None
    balance_to_finish: Decimal
    retention: Decimal


@dataclass(frozen=True)
class Totals:
    original_sum: Decimal
    net_changes: Decimal
    contract_sum_to_date: Decimal
    work_to_date: Decimal
    materials_stored: Decimal
    completed_to_date: Decimal
    retention: Decimal
    earned_less_retention: Decimal
    previous_certified: Decimal
    amount_due: Decimal
    balance_to_finish: Decimal
    percent_complete: Decimal | None


def _pct(part: Decimal, whole: Decimal) -> Decimal | None:
    if whole == 0:
        return None
    return round_pct(part / whole * HUNDRED)


def round_pct(value: Decimal) -> Decimal:
    return value.quantize(PERCENT_PLACES, rounding=ROUND_HALF_UP)


def line(
    scheduled: Decimal, previous: Decimal, this_period: Decimal, stored: Decimal, retention_pct: Decimal
) -> LineResult:
    completed = previous + this_period + stored
    return LineResult(
        scheduled_value=scheduled,
        previous_work=previous,
        this_period=this_period,
        materials_stored=stored,
        completed_to_date=completed,
        percent_complete=_pct(completed, scheduled),
        balance_to_finish=scheduled - completed,
        retention=percent_of(completed, retention_pct),
    )


def line_errors(scheduled: Decimal, previous: Decimal, this_period: Decimal, stored: Decimal) -> list[str]:
    """Return the reasons a line's claim is not allowed (empty when valid)."""
    errors: list[str] = []
    work = previous + this_period
    completed = work + stored
    if scheduled >= 0:
        if stored < 0:
            errors.append("Materials stored cannot be negative")
        if work < 0:
            errors.append("Work to date cannot be negative; this period would reverse more than was claimed before")
        if completed > scheduled:
            errors.append("Completed and stored cannot exceed the scheduled value; extra work needs a change order")
    else:
        if stored != 0:
            errors.append("Materials cannot be stored against an omission")
        if work > 0 or work < scheduled:
            errors.append("An omission can only be valued between its scheduled value and zero")
    return errors


def this_period_from_percent(
    scheduled: Decimal, percent_to_date: Decimal, previous: Decimal, stored: Decimal
) -> Decimal:
    """Work this period so that (work to date + stored) is ``percent_to_date`` % of the scheduled value."""
    return percent_of(scheduled, percent_to_date) - previous - stored


def totals(
    lines: Iterable[LineResult],
    original_sum: Decimal,
    net_changes: Decimal,
    previous_certified: Decimal,
) -> Totals:
    ls = list(lines)
    work = sum((x.previous_work + x.this_period for x in ls), ZERO)
    stored = sum((x.materials_stored for x in ls), ZERO)
    completed = work + stored
    retention = sum((x.retention for x in ls), ZERO)
    earned = completed - retention
    contract_sum = original_sum + net_changes
    return Totals(
        original_sum=original_sum,
        net_changes=net_changes,
        contract_sum_to_date=contract_sum,
        work_to_date=work,
        materials_stored=stored,
        completed_to_date=completed,
        retention=retention,
        earned_less_retention=earned,
        previous_certified=previous_certified,
        amount_due=round_money(earned - previous_certified),
        balance_to_finish=contract_sum - earned,
        percent_complete=_pct(completed, contract_sum),
    )


def billing_position(billed_to_date: Decimal, earned_revenue: Decimal) -> tuple[Decimal, Decimal]:
    """Over/under billing: returns (over_billed, under_billed), at most one non-zero.

    billed_to_date is the gross amount applied for to date (line 4, before retention), earned_revenue comes from
    the approved forecast (revenue x cost-to-cost percent complete)."""
    diff = billed_to_date - earned_revenue
    return (diff, ZERO) if diff > 0 else (ZERO, -diff)


def payment_dates(due_date: date, payment_days: int | None, pay_less_days: int = 5) -> tuple[date, date]:
    """Default final date for payment (due date + contract payment period, 14 days when not stated) and the latest
    date for a pay-less notice (``pay_less_days`` before the final date; 5 matches the JCT default). Both are
    defaults the user can change to match the contract."""
    final = due_date + timedelta(days=payment_days if payment_days is not None else 14)
    return final, final - timedelta(days=pay_less_days)
