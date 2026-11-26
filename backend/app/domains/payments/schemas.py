from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import Field, model_validator

from app.core.money import DecimalOut, MoneyAmount, Percent
from app.core.schemas import ApiModel, InputModel


class ApplicationCreate(InputModel):
    contract_id: uuid.UUID
    period_to: date
    application_date: date | None = None


class ApplicationUpdate(InputModel):
    version: int = Field(ge=1)
    period_to: date | None = None
    application_date: date | None = None
    due_date: date | None = None
    final_payment_date: date | None = None
    pay_less_notice_date: date | None = None
    retention_percent: Percent | None = None
    notes: str | None = Field(default=None, max_length=5000)


class LineUpdate(InputModel):
    """Give either the work done this period or the percent complete to date (incl. stored materials)."""

    this_period: MoneyAmount | None = None
    percent_to_date: Percent | None = None
    materials_stored: MoneyAmount | None = None

    @model_validator(mode="after")
    def _one_of(self):  # type: ignore[no-untyped-def]
        if self.this_period is not None and self.percent_to_date is not None:
            raise ValueError("Give either this_period or percent_to_date, not both")
        if self.this_period is None and self.percent_to_date is None and self.materials_stored is None:
            raise ValueError("Nothing to update")
        return self


class VersionIn(InputModel):
    version: int = Field(ge=1)


class CertifyIn(InputModel):
    version: int = Field(ge=1)
    certified_amount: MoneyAmount | None = None
    certified_date: date | None = None
    certification_note: str | None = Field(default=None, max_length=2000)


class PaymentIn(InputModel):
    version: int = Field(ge=1)
    paid_amount: MoneyAmount | None = None
    paid_date: date | None = None
    payment_reference: str | None = Field(default=None, max_length=80)


class LineOut(ApiModel):
    id: uuid.UUID
    item: str
    description: str
    source: str  # "contract" | "change_order"
    scheduled_value: DecimalOut
    previous_work: DecimalOut
    this_period: DecimalOut
    materials_stored: DecimalOut
    completed_to_date: DecimalOut
    percent_complete: DecimalOut | None
    balance_to_finish: DecimalOut
    retention: DecimalOut


class TotalsOut(ApiModel):
    original_sum: DecimalOut
    net_changes: DecimalOut
    contract_sum_to_date: DecimalOut
    work_to_date: DecimalOut
    materials_stored: DecimalOut
    completed_to_date: DecimalOut
    retention: DecimalOut
    earned_less_retention: DecimalOut
    previous_certified: DecimalOut
    amount_due: DecimalOut
    balance_to_finish: DecimalOut
    percent_complete: DecimalOut | None


class ApplicationSummary(ApiModel):
    id: uuid.UUID
    project_id: uuid.UUID
    contract_id: uuid.UUID
    contract_number: str
    contract_title: str
    number: int
    label: str
    status: str
    currency: str
    period_to: date
    application_date: date
    due_date: date | None
    final_payment_date: date | None
    pay_less_notice_date: date | None
    amount_due: DecimalOut | None
    certified_amount: DecimalOut | None
    paid_amount: DecimalOut | None
    outstanding: DecimalOut
    is_overdue: bool


class ApplicationOut(ApplicationSummary):
    retention_percent: DecimalOut
    notes: str | None
    submitted_at: datetime | None
    certified_date: date | None
    certification_note: str | None
    paid_date: date | None
    payment_reference: str | None
    version: int
    is_editable: bool
    can_certify: bool
    totals: TotalsOut
    lines: list[LineOut]


class BillingSummaryOut(ApiModel):
    currency: str
    billed_to_date: DecimalOut | None
    earned_revenue: DecimalOut | None
    forecast_period: date | None
    over_billed: DecimalOut | None
    under_billed: DecimalOut | None
    certified_to_date: DecimalOut
    paid_to_date: DecimalOut
    outstanding: DecimalOut
    awaiting_certification: DecimalOut
    retention_held: DecimalOut
    overdue_count: int
