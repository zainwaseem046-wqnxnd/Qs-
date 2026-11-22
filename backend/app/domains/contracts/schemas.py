from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.core.money import DecimalOut, MoneyAmount, Percent, Quantity, UnitRate
from app.core.schemas import ApiModel, InputModel
from app.domains.companies.schemas import CompanyRef
from app.domains.cost_codes.schemas import CostCodeRef

NUMBER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._/\-]*$"


class _TermsIn(InputModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    contract_form: str | None = Field(default=None, max_length=40)
    retention_percent: Percent | None = None
    retention_terms: str | None = Field(default=None, max_length=2000)
    payment_terms_days: int | None = Field(default=None, ge=0, le=365)
    start_date: date | None = None
    completion_date: date | None = None
    scope_summary: str | None = Field(default=None, max_length=10000)

    @field_validator("retention_terms", "scope_summary", mode="before")
    @classmethod
    def _blank(cls, v: object) -> object:
        return None if isinstance(v, str) and v.strip() == "" else v

    @model_validator(mode="after")
    def _dates(self):  # type: ignore[no-untyped-def]
        if self.start_date and self.completion_date and self.completion_date < self.start_date:
            raise ValueError("Completion date must be on or after the start date")
        return self


class _ContractFields(_TermsIn):
    client_company_id: uuid.UUID | None = None
    defects_period_months: int | None = Field(default=None, ge=0, le=120)
    liquidated_damages_amount: MoneyAmount | None = None
    liquidated_damages_period: Literal["day", "week"] | None = None
    bond_required: bool | None = None
    bond_percent: Percent | None = None
    insurance_notes: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def _ld(self):  # type: ignore[no-untyped-def]
        if self.liquidated_damages_amount is not None and self.liquidated_damages_amount < 0:
            raise ValueError("Liquidated damages cannot be negative")
        if (self.liquidated_damages_amount is None) != (self.liquidated_damages_period is None):
            raise ValueError("Give both the liquidated damages amount and its period (per day or per week)")
        return self


class ContractCreate(_ContractFields):
    number: str | None = Field(default=None, min_length=1, max_length=40, pattern=NUMBER_PATTERN)
    title: str = Field(min_length=2, max_length=200)  # type: ignore[assignment]
    contract_form: str = Field(max_length=40)  # type: ignore[assignment]
    cost_code_set_id: uuid.UUID | None = None


class ContractUpdate(_ContractFields):
    version: int = Field(ge=1)


class _CommitmentFields(_TermsIn):
    exclusions: str | None = Field(default=None, max_length=10000)


class CommitmentCreate(_CommitmentFields):
    number: str | None = Field(default=None, min_length=1, max_length=40, pattern=NUMBER_PATTERN)
    commitment_type: Literal["subcontract", "purchase_order"]
    vendor_company_id: uuid.UUID
    title: str = Field(min_length=2, max_length=200)  # type: ignore[assignment]
    contract_form: str = Field(max_length=40)  # type: ignore[assignment]
    cost_code_set_id: uuid.UUID | None = None


class CommitmentUpdate(_CommitmentFields):
    version: int = Field(ge=1)
    vendor_company_id: uuid.UUID | None = None


class ExecuteIn(InputModel):
    executed_date: date
    version: int = Field(ge=1)


class StatusIn(InputModel):
    version: int = Field(ge=1)


class ContractLineIn(InputModel):
    cost_code_id: uuid.UUID | None = None
    description: str = Field(min_length=1, max_length=300)
    amount: MoneyAmount


class CommitmentLineIn(InputModel):
    cost_code_id: uuid.UUID | None = None
    description: str = Field(min_length=1, max_length=300)
    quantity: Quantity | None = None
    unit: str | None = Field(default=None, max_length=20)
    unit_rate: UnitRate | None = None
    amount: MoneyAmount | None = None

    @model_validator(mode="after")
    def _priced(self):  # type: ignore[no-untyped-def]
        measured = self.quantity is not None or self.unit_rate is not None
        if measured:
            if self.quantity is None or self.unit_rate is None or not (self.unit and self.unit.strip()):
                raise ValueError("Measured lines need quantity, unit and unit rate")
            if self.amount is not None:
                raise ValueError("Leave amount empty for measured lines; it is calculated as quantity x rate")
        elif self.amount is None:
            raise ValueError("Enter an amount, or a quantity, unit and unit rate")
        return self


class LineOut(ApiModel):
    id: uuid.UUID
    sequence: int
    cost_code: CostCodeRef | None
    description: str
    quantity: DecimalOut | None = None
    unit: str | None = None
    unit_rate: DecimalOut | None = None
    amount: DecimalOut


class _TermsOut(ApiModel):
    id: uuid.UUID
    project_id: uuid.UUID
    project_number: str
    project_name: str
    number: str
    title: str
    contract_form: str
    status: str
    currency: str
    cost_code_set_id: uuid.UUID | None
    retention_percent: DecimalOut | None
    retention_terms: str | None
    payment_terms_days: int | None
    start_date: date | None
    completion_date: date | None
    scope_summary: str | None
    original_sum: DecimalOut | None
    current_total: DecimalOut
    executed_date: date | None
    executed_at: datetime | None
    closed_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime
    is_editable: bool
    can_execute: bool
    lines: list[LineOut]


class ContractOut(_TermsOut):
    client_company: CompanyRef | None
    defects_period_months: int | None
    liquidated_damages_amount: DecimalOut | None
    liquidated_damages_period: str | None
    bond_required: bool
    bond_percent: DecimalOut | None
    insurance_notes: str | None


class CommitmentOut(_TermsOut):
    commitment_type: str
    vendor: CompanyRef
    exclusions: str | None


class ListItem(ApiModel):
    id: uuid.UUID
    project_id: uuid.UUID
    project_number: str
    project_name: str
    number: str
    title: str
    status: str
    currency: str
    counterparty: str | None
    commitment_type: str | None = None
    current_total: DecimalOut
    original_sum: DecimalOut | None
    executed_date: date | None
    updated_at: datetime


class SummaryRow(ApiModel):
    cost_code_id: uuid.UUID | None
    code: str | None
    title: str
    budget: DecimalOut
    committed: DecimalOut
    pending: DecimalOut
    uncommitted: DecimalOut
    contract_value: DecimalOut


class CommercialSummary(ApiModel):
    currency: str
    has_approved_budget: bool
    rows: list[SummaryRow]
    totals: SummaryRow
    warnings: list[str]


class ContractVocab(ApiModel):
    prime_forms: dict[str, str]
    subcontract_forms: dict[str, str]
    commitment_types: dict[str, str]
    statuses: dict[str, str]
