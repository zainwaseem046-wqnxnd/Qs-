from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from app.core.schemas import ApiModel, InputModel
from app.domains.projects.constants import COMPANY_TYPES, US_STATES


class AddressIn(InputModel):
    line1: str | None = Field(default=None, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=120)
    state_code: str | None = None
    postal_code: str | None = Field(default=None, pattern=r"^\d{5}(-\d{4})?$")
    county: str | None = Field(default=None, max_length=120)
    country_code: str = Field(default="US", pattern=r"^[A-Z]{2}$")

    @field_validator("*", mode="before")
    @classmethod
    def _blank_to_none(cls, v: object) -> object:
        return None if isinstance(v, str) and v.strip() == "" else v

    @field_validator("state_code")
    @classmethod
    def _state(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.upper()
        if v not in US_STATES:
            raise ValueError("Unknown US state or territory code")
        return v

    def is_empty(self) -> bool:
        return not any([self.line1, self.line2, self.city, self.state_code, self.postal_code, self.county])


class AddressOut(ApiModel):
    line1: str | None
    line2: str | None
    city: str | None
    state_code: str | None
    postal_code: str | None
    county: str | None
    country_code: str


class CompanyBase(InputModel):
    legal_name: str | None = Field(default=None, max_length=200)
    trades: list[str] = Field(default_factory=list, max_length=30)
    website: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    notes: str | None = Field(default=None, max_length=5000)
    address: AddressIn | None = None

    @field_validator("legal_name", "website", "phone", "notes", "email", mode="before")
    @classmethod
    def _blank(cls, v: object) -> object:
        return None if isinstance(v, str) and v.strip() == "" else v

    @field_validator("trades")
    @classmethod
    def _trades(cls, v: list[str]) -> list[str]:
        cleaned = sorted({t.strip() for t in v if t.strip()})
        if any(len(t) > 80 for t in cleaned):
            raise ValueError("Trade names must be 80 characters or fewer")
        return cleaned


def _check_type(v: str) -> str:
    if v not in COMPANY_TYPES:
        raise ValueError(f"Unknown company type; expected one of {sorted(COMPANY_TYPES)}")
    return v


class CompanyCreate(CompanyBase):
    name: str = Field(min_length=1, max_length=200)
    company_type: str

    @field_validator("company_type")
    @classmethod
    def _type(cls, v: str) -> str:
        return _check_type(v)


class CompanyUpdate(CompanyBase):
    version: int = Field(ge=1, description="Current version for optimistic concurrency")
    name: str | None = Field(default=None, min_length=1, max_length=200)
    company_type: str | None = None
    is_active: bool | None = None

    @field_validator("company_type")
    @classmethod
    def _type(cls, v: str | None) -> str | None:
        return _check_type(v) if v is not None else v


class CompanyOut(ApiModel):
    id: uuid.UUID
    name: str
    legal_name: str | None
    company_type: str
    trades: list[str]
    website: str | None
    phone: str | None
    email: str | None
    notes: str | None
    is_active: bool
    address: AddressOut | None
    version: int
    created_at: datetime
    updated_at: datetime


class CompanyRef(ApiModel):
    id: uuid.UUID
    name: str
    company_type: str


class ContactIn(InputModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    title: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    mobile: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("title", "email", "phone", "mobile", "notes", mode="before")
    @classmethod
    def _blank(cls, v: object) -> object:
        return None if isinstance(v, str) and v.strip() == "" else v


class ContactOut(ApiModel):
    id: uuid.UUID
    company_id: uuid.UUID | None
    first_name: str
    last_name: str
    title: str | None
    email: str | None
    phone: str | None
    mobile: str | None
    notes: str | None
    created_at: datetime
