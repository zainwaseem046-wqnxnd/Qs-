from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import EmailStr, Field, field_validator

from app.core.money import SUPPORTED_CURRENCIES
from app.core.schemas import ApiModel, InputModel
from app.domains.projects.constants import US_STATES


class TenantOut(ApiModel):
    id: uuid.UUID
    name: str
    slug: str
    default_currency: str
    measurement_system: str
    home_state: str | None
    timezone: str
    country_code: str
    data_region: str


class RoleRef(ApiModel):
    id: uuid.UUID
    key: str
    name: str


class CurrentTenantOut(ApiModel):
    tenant: TenantOut
    role: RoleRef
    permissions: list[str]


class TenantUpdate(InputModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    default_currency: str | None = None
    home_state: str | None = None
    timezone: str | None = Field(default=None, max_length=64)
    measurement_system: Literal["us_customary", "metric"] | None = None

    @field_validator("default_currency")
    @classmethod
    def _currency(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v.upper() not in SUPPORTED_CURRENCIES:
            raise ValueError("Unsupported currency")
        return v.upper()

    @field_validator("home_state")
    @classmethod
    def _state(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v.upper() not in US_STATES:
            raise ValueError("Unknown US state code")
        return v.upper()

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str | None) -> str | None:
        if v is None:
            return v
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unknown time zone") from exc
        return v


class PermissionOut(ApiModel):
    key: str
    category: str
    description: str


class RoleOut(ApiModel):
    id: uuid.UUID
    key: str
    name: str
    description: str | None
    is_system: bool
    permission_keys: list[str]
    member_count: int = 0


class RoleCreate(InputModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[str] = Field(min_length=1)


class RoleUpdate(InputModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[str] | None = Field(default=None, min_length=1)


class MemberOut(ApiModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    mfa_enabled: bool
    role: RoleRef
    status: str
    job_title: str | None
    created_at: datetime


class MemberUpdate(InputModel):
    role_id: uuid.UUID | None = None
    status: Literal["active", "suspended"] | None = None
    job_title: str | None = Field(default=None, max_length=120)


class InvitationCreate(InputModel):
    email: EmailStr
    role_id: uuid.UUID


class InvitationOut(ApiModel):
    id: uuid.UUID
    email: str
    role: RoleRef
    expires_at: datetime
    created_at: datetime
    status: str


class InvitationCreated(InvitationOut):
    # Shown exactly once to the inviter as a fallback in case the email does not arrive.
    accept_url: str
    email_sent: bool
