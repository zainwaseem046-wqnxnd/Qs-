"""Golden-value tests for the estimating calculation engine. Expected values are worked by hand."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal as D

import pytest

from app.domains.estimating.calc import PricedLine, apply_markups, calculate_line, version_totals


@dataclass
class L:
    quantity: D = D("0")
    labour_hours_per_unit: D = D("0")
    labour_rate: D = D("0")
    material_rate: D = D("0")
    material_waste_percent: D = D("0")
    equipment_rate: D = D("0")
    subcontract_rate: D = D("0")
    other_rate: D = D("0")


@dataclass
class M:
    name: str
    percent: D
    basis: str = "direct_cost"
    include_in_budget: bool = True


def test_concrete_slab_build_up() -> None:
    # 125.5 CY of slab: 0.85 hr/CY at $62.40/hr, ready-mix $148.00/CY + 5% waste, pump $18.25/CY
    r = calculate_line(L(quantity=D("125.5"), labour_hours_per_unit=D("0.85"), labour_rate=D("62.40"),
                         material_rate=D("148.00"), material_waste_percent=D("5"), equipment_rate=D("18.25")))
    assert r.labour_unit == D("53.040000")        # 0.85 x 62.40
    assert r.material_unit == D("155.400000")     # 148.00 x 1.05
    assert r.unit_cost == D("226.690000")
    assert r.labour_total == D("6656.52")         # 125.5 x 53.04
    assert r.material_total == D("19502.70")      # 125.5 x 155.40
    assert r.equipment_total == D("2290.38")      # 125.5 x 18.25 = 2290.375 -> half-up
    assert r.total == D("28449.60")
    assert r.total == r.labour_total + r.material_total + r.equipment_total + r.subcontract_total + r.other_total
    assert r.labour_hours == D("106.6750")


def test_uk_blockwork_metric_build_up() -> None:
    # 342.75 m2 blockwork: 1.15 hr/m2 at £28.50/hr, blocks+mortar £21.30/m2 + 7.5% waste
    r = calculate_line(L(quantity=D("342.75"), labour_hours_per_unit=D("1.15"), labour_rate=D("28.50"),
                         material_rate=D("21.30"), material_waste_percent=D("7.5")))
    assert r.labour_unit == D("32.775000")
    assert r.material_unit == D("22.897500")
    assert r.labour_total == D("11233.63")        # 342.75 x 32.775 = 11233.63125
    assert r.material_total == D("7848.12")       # 342.75 x 22.8975 = 7848.118125
    assert r.total == D("19081.75")


def test_unit_rate_rounding_to_six_places() -> None:
    r = calculate_line(L(quantity=D("3"), labour_hours_per_unit=D("0.3333"), labour_rate=D("47.123456")))
    assert r.labour_unit == D("15.706248")        # 15.7062478848 -> 6dp half-up
    assert r.labour_total == D("47.12")


def test_lump_sum_allowance_and_zero_quantity() -> None:
    assert calculate_line(L(quantity=D("1"), other_rate=D("25000"))).total == D("25000.00")
    assert calculate_line(L(quantity=D("0"), material_rate=D("99.99"))).total == D("0.00")


def test_markups_direct_and_cumulative() -> None:
    marks = apply_markups(D("100000.00"), [
        M("Preliminaries", D("12.5")),
        M("Contingency", D("5"), "cumulative"),
        M("Overheads & profit", D("7.25"), "cumulative", include_in_budget=False),
    ])
    # 100,000 x 12.5% = 12,500; 112,500 x 5% = 5,625; 118,125 x 7.25% = 8,564.0625 -> 8,564.06
    assert [m.amount for m in marks] == [D("12500.00"), D("5625.00"), D("8564.06")]
    assert marks[1].base_amount == D("112500.00")
    assert marks[2].base_amount == D("118125.00")


def test_version_totals_with_alternates_and_exclusions() -> None:
    base1 = calculate_line(L(quantity=D("10"), subcontract_rate=D("1000.005")))   # 10000.05
    base2 = calculate_line(L(quantity=D("1"), other_rate=D("0.10")))
    alt = calculate_line(L(quantity=D("2"), material_rate=D("500")))
    excl = calculate_line(L(quantity=D("1"), other_rate=D("999")))
    t = version_totals(
        [PricedLine("base", None, base1), PricedLine("base", None, base2),
         PricedLine("alternate", "Alt 1 — upgraded finishes", alt), PricedLine("excluded", None, excl)],
        [M("Contingency", D("10"))],
    )
    assert t.direct_cost == D("10000.15")
    assert t.markups[0].amount == D("1000.02")    # 1000.015 -> half-up
    assert t.total == D("11000.17")
    assert t.alternates == {"Alt 1 — upgraded finishes": D("1000.00")}
    assert t.excluded_total == D("999.00")
    assert t.components["subcontract"] == D("10000.05")


def test_unknown_basis_rejected() -> None:
    with pytest.raises(ValueError):
        apply_markups(D("1"), [M("X", D("1"), "compound")])


def test_many_small_lines_sum_exactly() -> None:
    lines = [PricedLine("base", None, calculate_line(L(quantity=D("1"), other_rate=D("0.01")))) for _ in range(5000)]
    assert version_totals(lines, []).total == D("50.00")
