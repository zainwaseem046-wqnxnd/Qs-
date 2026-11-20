from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import Field, model_validator

from app.core.money import CurrencyCode, DecimalOut, MarkupPercent, Percent, Quantity, UnitRate
from app.core.schemas import ApiModel, InputModel
from app.domains.cost_codes.schemas import CostCodeRef

ESTIMATE_TYPES = {
    "conceptual": "Conceptual / order of magnitude",
    "cost_plan": "Cost plan",
    "detailed": "Detailed estimate",
    "pre_tender": "Pre-tender estimate",
    "tender": "Tender / bid",
}
LINE_TYPES = {
    "item": "Measured item",
    "allowance": "Allowance",
    "provisional_sum": "Provisional sum",
    "prime_cost_sum": "Prime cost sum",
    "daywork": "Daywork",
}
LineType = Literal["item", "allowance", "provisional_sum", "prime_cost_sum", "daywork"]


class EstimateCreate(InputModel):
    name: str = Field(min_length=2, max_length=200)
    estimate_type: Literal["conceptual", "cost_plan", "detailed", "pre_tender", "tender"] = "detailed"
    cost_code_set_id: uuid.UUID | None = None
    currency: CurrencyCode | None = None
    price_base_date: date | None = None
    label: str | None = Field(default=None, max_length=120)


class EstimateUpdate(InputModel):
    name: str = Field(min_length=2, max_length=200)


class LineFields(InputModel):
    quantity: Quantity
    labour_hours_per_unit: Quantity = Field(default="0", validate_default=True)
    labour_rate: UnitRate = Field(default="0", validate_default=True)
    material_rate: UnitRate = Field(default="0", validate_default=True)
    material_waste_percent: Percent = Field(default="0", validate_default=True)
    equipment_rate: UnitRate = Field(default="0", validate_default=True)
    subcontract_rate: UnitRate = Field(default="0", validate_default=True)
    other_rate: UnitRate = Field(default="0", validate_default=True)


class LineIn(LineFields):
    cost_code_id: uuid.UUID | None = None
    line_type: LineType = "item"
    inclusion: Literal["base", "alternate", "excluded"] = "base"
    alternate_label: str | None = Field(default=None, max_length=80)
    description: str = Field(min_length=1, max_length=500)
    unit: str = Field(min_length=1, max_length=20)
    notes: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def _alternate(self) -> LineIn:
        if self.inclusion == "alternate" and not (self.alternate_label and self.alternate_label.strip()):
            raise ValueError("Alternates need a label (e.g. 'Alt 1 — upgraded facade')")
        if self.inclusion != "alternate":
            self.alternate_label = None
        return self


class LineCalcOut(ApiModel):
    labour_unit: DecimalOut
    material_unit: DecimalOut
    equipment_unit: DecimalOut
    subcontract_unit: DecimalOut
    other_unit: DecimalOut
    unit_cost: DecimalOut
    labour_total: DecimalOut
    material_total: DecimalOut
    equipment_total: DecimalOut
    subcontract_total: DecimalOut
    other_total: DecimalOut
    total: DecimalOut
    labour_hours: DecimalOut


class LineOut(ApiModel):
    id: uuid.UUID
    sequence: int
    cost_code: CostCodeRef | None
    line_type: str
    inclusion: str
    alternate_label: str | None
    description: str
    quantity: DecimalOut
    unit: str
    labour_hours_per_unit: DecimalOut
    labour_rate: DecimalOut
    material_rate: DecimalOut
    material_waste_percent: DecimalOut
    equipment_rate: DecimalOut
    subcontract_rate: DecimalOut
    other_rate: DecimalOut
    notes: str | None
    calc: LineCalcOut


class MarkupIn(InputModel):
    name: str = Field(min_length=1, max_length=120)
    percent: MarkupPercent
    basis: Literal["direct_cost", "cumulative"] = "direct_cost"
    include_in_budget: bool = True


class MarkupsIn(InputModel):
    markups: list[MarkupIn] = Field(max_length=20)


class MarkupOut(ApiModel):
    name: str
    percent: DecimalOut
    basis: str
    include_in_budget: bool
    base_amount: DecimalOut
    amount: DecimalOut


class AlternateOut(ApiModel):
    label: str
    amount: DecimalOut


class TotalsOut(ApiModel):
    direct_cost: DecimalOut
    markup_total: DecimalOut
    total: DecimalOut
    alternates: list[AlternateOut]
    excluded_total: DecimalOut
    labour_hours: DecimalOut
    components: dict[str, DecimalOut]


class VersionSummary(ApiModel):
    id: uuid.UUID
    version_number: int
    status: str
    label: str | None
    total: DecimalOut | None
    issued_at: datetime | None
    approved_at: datetime | None
    created_at: datetime


class VersionOut(VersionSummary):
    notes: str | None
    price_base_date: date | None
    is_editable: bool
    lines: list[LineOut]
    markups: list[MarkupOut]
    totals: TotalsOut


class VersionUpdate(InputModel):
    label: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=5000)
    price_base_date: date | None = None


class EstimateOut(ApiModel):
    id: uuid.UUID
    project_id: uuid.UUID
    project_number: str
    project_name: str
    name: str
    estimate_type: str
    cost_code_set_id: uuid.UUID | None
    currency: str
    current_version_number: int
    versions: list[VersionSummary]
    can_edit: bool
    created_at: datetime
    updated_at: datetime


class CompareRow(ApiModel):
    cost_code: str | None
    title: str
    from_amount: DecimalOut
    to_amount: DecimalOut
    change: DecimalOut


class CompareOut(ApiModel):
    from_version: int
    to_version: int
    rows: list[CompareRow]
    from_total: DecimalOut
    to_total: DecimalOut
    change: DecimalOut
