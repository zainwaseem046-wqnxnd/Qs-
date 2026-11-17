from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from app.core.schemas import ApiModel, InputModel
from app.core.security import PASSWORD_MAX_LENGTH, validate_password_strength
from app.domains.projects.constants import US_STATES


class RegisterRequest(InputModel):
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(max_length=PASSWORD_MAX_LENGTH)
    organization_name: str = Field(min_length=2, max_length=200)
    home_state: str | None = Field(default=None, description="Two-letter US state code")

    @field_validator("password")
    @classmethod
    def _pw(cls, v: str) -> str:
        return validate_password_strength(v)

    @field_validator("home_state")
    @classmethod
    def _state(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        v = v.upper()
        if v not in US_STATES:
            raise ValueError("Unknown US state code")
        return v


class LoginRequest(InputModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class MfaVerifyRequest(InputModel):
    mfa_token: str = Field(min_length=10, max_length=2000)
    code: str = Field(pattern=r"^\d{6}$")


class MfaCodeRequest(InputModel):
    code: str = Field(pattern=r"^\d{6}$")


class PasswordConfirmRequest(InputModel):
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class MfaDisableRequest(InputModel):
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)
    code: str = Field(pattern=r"^\d{6}$")


class ChangePasswordRequest(InputModel):
    current_password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)
    new_password: str = Field(max_length=PASSWORD_MAX_LENGTH)

    @field_validator("new_password")
    @classmethod
    def _pw(cls, v: str) -> str:
        return validate_password_strength(v)


class UpdateProfileRequest(InputModel):
    full_name: str = Field(min_length=2, max_length=200)


class AcceptInvitationRequest(InputModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    password: str | None = Field(default=None, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("password")
    @classmethod
    def _pw(cls, v: str | None) -> str | None:
        return validate_password_strength(v) if v else None


class UserOut(ApiModel):
    id: uuid.UUID
    email: str
    full_name: str
    mfa_enabled: bool
    last_login_at: datetime | None = None


class MembershipSummary(ApiModel):
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_slug: str
    role_key: str | None
    role_name: str | None


class SessionOut(ApiModel):
    user: UserOut
    memberships: list[MembershipSummary]


class LoginResult(ApiModel):
    mfa_required: bool = False
    mfa_token: str | None = None
    session: SessionOut | None = None
    # Returned for API (non-browser) clients; browsers use the httpOnly cookies instead.
    access_token: str | None = None


class MfaSetupOut(ApiModel):
    secret: str
    otpauth_uri: str


class InvitationPreview(ApiModel):
    email: str
    tenant_name: str
    role_name: str
    expires_at: datetime
    account_exists: bool
