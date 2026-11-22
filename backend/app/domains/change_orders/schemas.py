from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.core.money import DecimalOut, MoneyAmount, SignedQuantity, UnitRate
from app.core.schemas import ApiModel, InputModel
from app.domains.change_orders.constants import REASONS
from app.domains.cost_codes.schemas import CostCodeRef


class _Fields(InputModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    reason: str | None = None
    reference: str | None = Field(default=None, max_length=80)
    schedule_impact_days: int | None = Field(default=None, ge=-3650, le=3650)
    notified_date: date | None = None
    response_due_date: date | None = None

    @field_validator("reason")
    @classmethod
    def _reason(cls, v: str | None) -> str | None:
        if v is not None and v not in REASONS:
            raise ValueError("Unknown reason")
        return v

    @field_validator("description", "reference", mode="before")
    @classmethod
    def _blank(cls, v: object) -> object:
        return None if isinstance(v, str) and v.strip() == "" else v

    @model_validator(mode="after")
    def _dates(self):  # type: ignore[no-untyped-def]
        if self.notified_date and self.response_due_date and self.response_due_date < self.notified_date:
            raise ValueError("Response due date must be on or after the notified date")
        return self


class ChangeOrderCreate(_Fields):
    target_type: Literal["contract", "commitment"]
    target_id: uuid.UUID
    number: str | None = Field(default=None, min_length=1, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9._/\-]*$")
    title: str = Field(min_length=2, max_length=200)  # type: ignore[assignment]
    reason: str = "client_instruction"  # type: ignore[assignment]


class ChangeOrderUpdate(_Fields):
    version: int = Field(ge=1)


class LineIn(InputModel):
    cost_code_id: uuid.UUID | None = None
    description: str = Field(min_length=1, max_length=300)
    quantity: SignedQuantity | None = None
    unit: str | None = Field(default=None, max_length=20)
    unit_rate: UnitRate | None = None
    amount: MoneyAmount | None = None
    budget_amount: MoneyAmount | None = None

    @model_validator(mode="after")
    def _priced(self):  # type: ignore[no-untyped-def]
        measured = self.quantity is not None or self.unit_rate is not None
        if measured:
            if self.quantity is None or self.unit_rate is None or not (self.unit and self.unit.strip()):
                raise ValueError("Measured lines need quantity, unit and unit rate")
            if self.amount is not None:
                raise ValueError("Leave amount empty for measured lines; it is calculated as quantity x rate")
        elif self.amount is None:
            raise ValueError("Enter an amount (negative for omissions), or a quantity, unit and unit rate")
        return self


class VersionIn(InputModel):
    version: int = Field(ge=1)


class DecisionIn(InputModel):
    version: int = Field(ge=1)
    notes: str | None = Field(default=None, max_length=5000)


class TargetRef(ApiModel):
    type: Literal["contract", "commitment"]
    id: uuid.UUID
    number: str
    title: str
    counterparty: str | None
    contract_form: str


class LineOut(ApiModel):
    id: uuid.UUID
    sequence: int
    cost_code: CostCodeRef | None
    description: str
    quantity: DecimalOut | None
    unit: str | None
    unit_rate: DecimalOut | None
    amount: DecimalOut
    budget_amount: DecimalOut | None


class ChangeOrderOut(ApiModel):
    id: uuid.UUID
    project_id: uuid.UUID
    project_number: str
    project_name: str
    target: TargetRef
    label: str
    number: str
    title: str
    description: str | None
    reason: str
    reference: str | None
    status: str
    currency: str
    schedule_impact_days: int | None
    notified_date: date | None
    response_due_date: date | None
    overdue: bool
    submitted_at: datetime | None
    decided_at: datetime | None
    decision_notes: str | None
    total: DecimalOut
    budget_total: DecimalOut
    version: int
    created_at: datetime
    updated_at: datetime
    is_editable: bool
    can_approve: bool
    lines: list[LineOut]


class ChangeOrderListItem(ApiModel):
    id: uuid.UUID
    project_id: uuid.UUID
    project_number: str
    project_name: str
    target: TargetRef
    label: str
    number: str
    title: str
    status: str
    currency: str
    total: DecimalOut
    response_due_date: date | None
    overdue: bool
    updated_at: datetime


class ChangeTotals(ApiModel):
    approved: DecimalOut
    pending: DecimalOut
    approved_count: int
    pending_count: int
