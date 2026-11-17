from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import Field, PlainSerializer, ValidationInfo, field_validator, model_validator

from app.core.money import CurrencyCode, MoneyAmount
from app.core.schemas import ApiModel, InputModel
from app.domains.companies.schemas import AddressIn, AddressOut, CompanyRef
from app.domains.projects.constants import (
    CONTRACT_TYPES,
    DELIVERY_METHODS,
    OUR_ROLES,
    PARTY_ROLES,
    PHASE_STATUSES,
    PROJECT_MEMBER_ROLES,
    PROJECT_STATUSES,
    SECTORS,
)

Percent = Annotated[
    Decimal,
    Field(ge=0, le=100, max_digits=5, decimal_places=2),
    PlainSerializer(lambda v: format(v, "f"), return_type=str, when_used="json"),
]


def _in(vocab: dict[str, str], label: str):  # type: ignore[no-untyped-def]
    def check(v: str | None) -> str | None:
        if v is not None and v not in vocab:
            raise ValueError(f"Unknown {label}; expected one of {sorted(vocab)}")
        return v

    return check


_status = _in(PROJECT_STATUSES, "status")
_sector = _in(SECTORS, "sector")
_delivery = _in(DELIVERY_METHODS, "delivery method")
_contract = _in(CONTRACT_TYPES, "contract type")
_our_role = _in(OUR_ROLES, "company role")
_VOCAB_CHECKS = {
    "status": _status, "sector": _sector, "delivery_method": _delivery,
    "contract_type": _contract, "our_role": _our_role,
}


class _ProjectFields(InputModel):
    description: str | None = Field(default=None, max_length=10000)
    project_type: str | None = Field(default=None, max_length=80)
    client_company_id: uuid.UUID | None = None
    site_address: AddressIn | None = None
    start_date: date | None = None
    planned_completion_date: date | None = None
    original_contract_value: MoneyAmount | None = None
    is_public_works: bool | None = None
    prevailing_wage: bool | None = None
    retainage_percent: Percent | None = None
    reporting_period_end_day: int | None = Field(default=None, ge=1, le=31)

    @field_validator("description", "project_type", mode="before")
    @classmethod
    def _blank(cls, v: object) -> object:
        return None if isinstance(v, str) and v.strip() == "" else v

    @field_validator("original_contract_value")
    @classmethod
    def _non_negative(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v < 0:
            raise ValueError("Contract value cannot be negative")
        return v

    @model_validator(mode="after")
    def _dates(self):  # type: ignore[no-untyped-def]
        if self.start_date and self.planned_completion_date and self.planned_completion_date < self.start_date:
            raise ValueError("Planned completion date must be on or after the start date")
        return self


class ProjectCreate(_ProjectFields):
    number: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
    name: str = Field(min_length=2, max_length=200)
    status: str = "preconstruction"
    sector: str
    delivery_method: str
    contract_type: str
    our_role: str = "general_contractor"
    currency: CurrencyCode = "USD"

    @field_validator("status", "sector", "delivery_method", "contract_type", "our_role")
    @classmethod
    def _vocab(cls, v: str, info: ValidationInfo) -> str:
        return _VOCAB_CHECKS[info.field_name](v)  # type: ignore[no-any-return]


class ProjectUpdate(_ProjectFields):
    version: int = Field(ge=1)
    number: str | None = Field(default=None, min_length=1, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
    name: str | None = Field(default=None, min_length=2, max_length=200)
    status: str | None = None
    sector: str | None = None
    delivery_method: str | None = None
    contract_type: str | None = None
    our_role: str | None = None
    currency: CurrencyCode | None = None
    actual_completion_date: date | None = None

    @field_validator("status", "sector", "delivery_method", "contract_type", "our_role")
    @classmethod
    def _vocab(cls, v: str | None, info: ValidationInfo) -> str | None:
        return _VOCAB_CHECKS[info.field_name](v)  # type: ignore[no-any-return]


class ProjectOut(ApiModel):
    id: uuid.UUID
    number: str
    name: str
    description: str | None
    status: str
    sector: str
    project_type: str | None
    delivery_method: str
    contract_type: str
    our_role: str
    client_company: CompanyRef | None
    site_address: AddressOut | None
    start_date: date | None
    planned_completion_date: date | None
    actual_completion_date: date | None
    original_contract_value: MoneyAmount | None
    currency: str
    is_public_works: bool
    prevailing_wage: bool
    retainage_percent: Percent | None
    reporting_period_end_day: int
    archived_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime
    # Present so clients can distinguish "hidden by permission" from "not entered".
    financials_visible: bool = True
    can_edit: bool = False


class ProjectListItem(ApiModel):
    id: uuid.UUID
    number: str
    name: str
    status: str
    sector: str
    delivery_method: str
    contract_type: str
    client_company: CompanyRef | None
    city: str | None
    state_code: str | None
    start_date: date | None
    planned_completion_date: date | None
    original_contract_value: MoneyAmount | None
    currency: str
    archived_at: datetime | None
    updated_at: datetime


class ProjectMemberIn(InputModel):
    user_id: uuid.UUID
    project_role: str

    @field_validator("project_role")
    @classmethod
    def _role(cls, v: str) -> str:
        if v not in PROJECT_MEMBER_ROLES:
            raise ValueError("Unknown project role")
        return v


class ProjectMemberUpdate(InputModel):
    project_role: str

    @field_validator("project_role")
    @classmethod
    def _role(cls, v: str) -> str:
        if v not in PROJECT_MEMBER_ROLES:
            raise ValueError("Unknown project role")
        return v


class ProjectMemberOut(ApiModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    project_role: str
    created_at: datetime


class ProjectPartyIn(InputModel):
    company_id: uuid.UUID
    party_role: str
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("party_role")
    @classmethod
    def _role(cls, v: str) -> str:
        if v not in PARTY_ROLES:
            raise ValueError("Unknown party role")
        return v


class ProjectPartyOut(ApiModel):
    id: uuid.UUID
    company: CompanyRef
    party_role: str
    notes: str | None


class ProjectPhaseIn(InputModel):
    name: str = Field(min_length=1, max_length=120)
    status: str = "planned"
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        if v not in PHASE_STATUSES:
            raise ValueError("Unknown phase status")
        return v

    @model_validator(mode="after")
    def _dates(self):  # type: ignore[no-untyped-def]
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("Phase end date must be on or after its start date")
        return self


class ProjectPhaseOut(ApiModel):
    id: uuid.UUID
    name: str
    sequence: int
    status: str
    start_date: date | None
    end_date: date | None


class VocabularyOut(ApiModel):
    project_statuses: dict[str, str]
    sectors: dict[str, str]
    delivery_methods: dict[str, str]
    contract_types: dict[str, str]
    our_roles: dict[str, str]
    project_member_roles: dict[str, str]
    party_roles: dict[str, str]
    phase_statuses: dict[str, str]
    us_states: dict[str, str]
    company_types: dict[str, str]
    document_categories: dict[str, str]
    disciplines: dict[str, str]
    currencies: list[str]
