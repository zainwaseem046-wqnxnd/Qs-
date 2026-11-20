"""Estimate calculation engine — deterministic, exact, documented.

All arithmetic is ``Decimal``. No database access; every function is pure and unit-tested.

Line build-up (per unit of measure)
-----------------------------------
    labour_unit       = round6(labour_hours_per_unit x labour_rate)
    material_unit     = round6(material_rate x (1 + material_waste_percent / 100))
    equipment_unit    = equipment_rate          (plant in UK usage)
    subcontract_unit  = subcontract_rate
    other_unit        = other_rate
    unit_cost         = sum of the five unit components (display only)

Extended amounts (rounded once per component, ROUND_HALF_UP to cents/pence)
---------------------------------------------------------------------------
    component_total   = round2(quantity x component_unit)
    line_total        = sum of the five rounded component totals
    labour_hours      = round4(quantity x labour_hours_per_unit)

Because the line total is the sum of already-rounded components, the displayed build-up always adds up
exactly to the line total.

Version totals
--------------
    direct_cost       = sum(line_total) for lines with inclusion = "base"
    alternates        = sum(line_total) per alternate_label for lines with inclusion = "alternate"
                        (shown separately, never added to the total)
    excluded lines    = priced for information, never totalled
    markups, applied in sequence order:
        basis "direct_cost": amount = round2(direct_cost x percent / 100)
        basis "cumulative" : amount = round2((direct_cost + markups so far) x percent / 100)
    markup_total      = sum(markup amounts)
    total             = direct_cost + markup_total
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

from app.core.money import round_money, round_quantity, round_rate

ZERO = Decimal("0")
HUNDRED = Decimal("100")
COMPONENTS = ("labour", "material", "equipment", "subcontract", "other")


class LineInput(Protocol):
    quantity: Decimal
    labour_hours_per_unit: Decimal
    labour_rate: Decimal
    material_rate: Decimal
    material_waste_percent: Decimal
    equipment_rate: Decimal
    subcontract_rate: Decimal
    other_rate: Decimal


class MarkupInput(Protocol):
    name: str
    percent: Decimal
    basis: str
    include_in_budget: bool


@dataclass(frozen=True)
class LineResult:
    labour_unit: Decimal
    material_unit: Decimal
    equipment_unit: Decimal
    subcontract_unit: Decimal
    other_unit: Decimal
    unit_cost: Decimal
    labour_total: Decimal
    material_total: Decimal
    equipment_total: Decimal
    subcontract_total: Decimal
    other_total: Decimal
    total: Decimal
    labour_hours: Decimal


@dataclass(frozen=True)
class MarkupResult:
    name: str
    percent: Decimal
    basis: str
    include_in_budget: bool
    base_amount: Decimal
    amount: Decimal


@dataclass(frozen=True)
class VersionTotals:
    direct_cost: Decimal
    markups: list[MarkupResult]
    markup_total: Decimal
    total: Decimal
    alternates: dict[str, Decimal] = field(default_factory=dict)
    excluded_total: Decimal = ZERO
    labour_hours: Decimal = ZERO
    components: dict[str, Decimal] = field(default_factory=dict)


def calculate_line(line: LineInput) -> LineResult:
    qty = line.quantity
    labour_unit = round_rate(line.labour_hours_per_unit * line.labour_rate)
    material_unit = round_rate(line.material_rate * (1 + line.material_waste_percent / HUNDRED))
    equipment_unit = round_rate(line.equipment_rate)
    subcontract_unit = round_rate(line.subcontract_rate)
    other_unit = round_rate(line.other_rate)
    totals = [round_money(qty * u) for u in (labour_unit, material_unit, equipment_unit, subcontract_unit, other_unit)]
    return LineResult(
        labour_unit=labour_unit,
        material_unit=material_unit,
        equipment_unit=equipment_unit,
        subcontract_unit=subcontract_unit,
        other_unit=other_unit,
        unit_cost=labour_unit + material_unit + equipment_unit + subcontract_unit + other_unit,
        labour_total=totals[0],
        material_total=totals[1],
        equipment_total=totals[2],
        subcontract_total=totals[3],
        other_total=totals[4],
        total=sum(totals, ZERO),
        labour_hours=round_quantity(qty * line.labour_hours_per_unit),
    )


def apply_markups(direct_cost: Decimal, markups: Iterable[MarkupInput]) -> list[MarkupResult]:
    results: list[MarkupResult] = []
    running = direct_cost
    for m in markups:
        if m.basis == "direct_cost":
            base = direct_cost
        elif m.basis == "cumulative":
            base = running
        else:
            raise ValueError(f"Unknown markup basis: {m.basis}")
        amount = (base * m.percent / HUNDRED).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        results.append(MarkupResult(m.name, m.percent, m.basis, m.include_in_budget, base, amount))
        running += amount
    return results


@dataclass(frozen=True)
class PricedLine:
    inclusion: str
    alternate_label: str | None
    result: LineResult


def version_totals(lines: Iterable[PricedLine], markups: Iterable[MarkupInput]) -> VersionTotals:
    direct = ZERO
    excluded = ZERO
    hours = ZERO
    alternates: dict[str, Decimal] = {}
    components = dict.fromkeys(COMPONENTS, ZERO)
    for line in lines:
        r = line.result
        if line.inclusion == "base":
            direct += r.total
            hours += r.labour_hours
            for c in COMPONENTS:
                components[c] += getattr(r, f"{c}_total")
        elif line.inclusion == "alternate":
            key = line.alternate_label or "Alternate"
            alternates[key] = alternates.get(key, ZERO) + r.total
        else:
            excluded += r.total
    marked = apply_markups(direct, markups)
    markup_total = sum((m.amount for m in marked), ZERO)
    return VersionTotals(direct, marked, markup_total, direct + markup_total, alternates, excluded, hours, components)
