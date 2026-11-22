from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator

from app.core.money import DecimalOut, MoneyAmount
from app.core.schemas import ApiModel, InputModel
from app.domains.cost_codes.schemas import CostCodeRef


class TransactionIn(InputModel):
    transaction_type: Literal["actual", "accrual"] = "actual"
    transaction_date: date
    description: str = Field(min_length=1, max_length=300)
    amount: MoneyAmount
    reference: str | None = Field(default=None, max_length=80)
    cost_code_id: uuid.UUID | None = None
    commitment_id: uuid.UUID | None = None
    vendor_company_id: uuid.UUID | None = None

    @field_validator("amount")
    @classmethod
    def _non_zero(cls, v):  # type: ignore[no-untyped-def]
        if v == 0:
            raise ValueError("Amount cannot be zero")
        return v


class ReverseIn(InputModel):
    reason: str = Field(min_length=3, max_length=200)


class TransactionOut(ApiModel):
    id: uuid.UUID
    transaction_type: str
    transaction_date: date
    description: str
    reference: str | None
    amount: DecimalOut
    cost_code: CostCodeRef | None
    commitment_number: str | None
    vendor_name: str | None
    reverses_id: uuid.UUID | None
    reversed: bool
    imported: bool
    created_at: datetime


class TransactionPage(ApiModel):
    items: list[TransactionOut]
    total: int
    amount_total: DecimalOut
    limit: int
    offset: int


class ImportOut(ApiModel):
    created: int
    total: DecimalOut
    errors: list[dict[str, object]]


class ForecastCreate(InputModel):
    period: date


class ForecastUpdate(InputModel):
    version: int = Field(ge=1)
    revenue_adjustment: MoneyAmount | None = None
    revenue_adjustment_note: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=5000)


class ForecastLineIn(InputModel):
    method: Literal["greater_of", "budget_remaining", "committed_remaining", "manual"]
    manual_ctc: MoneyAmount | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("manual_ctc")
    @classmethod
    def _non_negative(cls, v):  # type: ignore[no-untyped-def]
        if v is not None and v < 0:
            raise ValueError("Cost to complete cannot be negative")
        return v


class VersionIn(InputModel):
    version: int = Field(ge=1)


class ForecastLineOut(ApiModel):
    id: uuid.UUID
    cost_code: CostCodeRef | None
    method: str
    manual_ctc: DecimalOut | None
    notes: str | None
    revised_budget: DecimalOut
    committed: DecimalOut
    cost_to_date: DecimalOut
    cost_to_complete: DecimalOut
    final_cost: DecimalOut
    variance: DecimalOut


class ForecastSummary(ApiModel):
    id: uuid.UUID
    period: date
    status: str
    currency: str
    revenue: DecimalOut | None
    final_cost: DecimalOut | None
    gross_profit: DecimalOut | None
    margin_percent: DecimalOut | None
    approved_at: datetime | None


class ForecastOut(ApiModel):
    id: uuid.UUID
    project_id: uuid.UUID
    period: date
    period_end: date
    status: str
    currency: str
    revenue_adjustment: DecimalOut
    revenue_adjustment_note: str | None
    notes: str | None
    version: int
    approved_at: datetime | None
    is_editable: bool
    can_approve: bool
    revised_contract: DecimalOut
    revenue: DecimalOut
    revised_budget: DecimalOut
    committed: DecimalOut
    cost_to_date: DecimalOut
    cost_to_complete: DecimalOut
    final_cost: DecimalOut
    variance: DecimalOut
    gross_profit: DecimalOut
    margin_percent: DecimalOut | None
    percent_complete: DecimalOut | None
    earned_revenue: DecimalOut | None
    lines: list[ForecastLineOut]
