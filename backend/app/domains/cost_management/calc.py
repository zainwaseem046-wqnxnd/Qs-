"""Forecasting engine — deterministic, exact, documented. Pure functions; no database access.

Definitions (per cost code, at a period end):
    cost_to_date (CTD)   = actual cost + accruals posted on or before the period end (reversals included)
    revised_budget (RB)  = approved original budget + approved budget changes
    committed (CM)       = executed commitments + approved commitment changes
    cost_to_complete     by method:
        budget_remaining     max(RB - CTD, 0)
        committed_remaining  max(CM - CTD, 0)
        greater_of (default) max(RB - CTD, CM - CTD, 0)   # never forecast below what is already committed
        manual               the value entered (>= 0)
    final_cost (FFC)     = CTD + CTC
    variance             = RB - FFC                          (negative = forecast overrun)

Project level:
    revenue              = revised contract sum + revenue adjustment
    gross_profit         = revenue - sum(FFC)
    margin %             = gross_profit / revenue x 100 (2 dp, half-up; undefined when revenue = 0)
    percent_complete     = sum(CTD) / sum(FFC) x 100 (cost-to-cost; 2 dp; undefined when FFC = 0)
    earned_revenue       = round2(revenue x sum(CTD) / sum(FFC))

No double counting: commitments are future obligations and never added to cost; invoices and accruals against a
commitment are cost to date, and the commitment only raises the forecast through `greater_of`/`committed_remaining`
to the extent it is not yet incurred.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.core.money import margin_percent, round_money

ZERO = Decimal("0.00")
METHODS = ("greater_of", "budget_remaining", "committed_remaining", "manual")


@dataclass(frozen=True)
class LineForecast:
    revised_budget: Decimal
    committed: Decimal
    cost_to_date: Decimal
    cost_to_complete: Decimal
    final_cost: Decimal
    variance: Decimal


def cost_to_complete(
    method: str, revised_budget: Decimal, committed: Decimal, ctd: Decimal, manual: Decimal | None
) -> Decimal:
    if method == "budget_remaining":
        return max(revised_budget - ctd, ZERO)
    if method == "committed_remaining":
        return max(committed - ctd, ZERO)
    if method == "greater_of":
        return max(revised_budget - ctd, committed - ctd, ZERO)
    if method == "manual":
        if manual is None or manual < 0:
            raise ValueError("Manual cost to complete must be zero or more")
        return manual
    raise ValueError(f"Unknown forecasting method: {method}")


def forecast_line(
    method: str, revised_budget: Decimal, committed: Decimal, ctd: Decimal, manual: Decimal | None = None
) -> LineForecast:
    ctc = cost_to_complete(method, revised_budget, committed, ctd, manual)
    ffc = ctd + ctc
    return LineForecast(revised_budget, committed, ctd, ctc, ffc, revised_budget - ffc)


@dataclass(frozen=True)
class ProjectForecast:
    revenue: Decimal
    revised_budget: Decimal
    committed: Decimal
    cost_to_date: Decimal
    cost_to_complete: Decimal
    final_cost: Decimal
    variance: Decimal
    gross_profit: Decimal
    margin_percent: Decimal | None
    percent_complete: Decimal | None
    earned_revenue: Decimal | None


def project_forecast(
    lines: list[LineForecast], revised_contract: Decimal, revenue_adjustment: Decimal
) -> ProjectForecast:
    def total(attr: str) -> Decimal:
        return sum((getattr(ln, attr) for ln in lines), ZERO)

    revenue = revised_contract + revenue_adjustment
    ffc, ctd = total("final_cost"), total("cost_to_date")
    gp = revenue - ffc
    pct = (ctd / ffc * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if ffc else None
    earned = round_money(revenue * ctd / ffc) if ffc else None
    return ProjectForecast(
        revenue,
        total("revised_budget"),
        total("committed"),
        ctd,
        total("cost_to_complete"),
        ffc,
        total("variance"),
        gp,
        margin_percent(gp, revenue),
        pct,
        earned,
    )
