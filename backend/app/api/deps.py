"""Authentication, tenant resolution and permission enforcement for every request.

Resolution order (each step narrows the RLS context):
1. Authenticate the user from a Bearer token or the ``qs_access`` cookie (cookie auth requires CSRF).
2. Set ``app.user_id`` so the user's own rows become visible.
3. Read ``X-Tenant-ID``, set ``app.tenant_id`` and require an *active* membership in that tenant.
4. Load the membership's role permissions; route dependencies check them with ``require(...)``.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated

import jwt
from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db, set_rls_context
from app.core.errors import NotAuthenticated, PermissionDenied
from app.core.security import constant_time_equals, decode_jwt
from app.domains.audit.service import AuditActor
from app.domains.identity.models import User
from app.domains.tenancy.models import Role, Tenant, TenantMembership

ACCESS_COOKIE = "qs_access"
REFRESH_COOKIE = "qs_refresh"
CSRF_COOKIE = "qs_csrf"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

DB = Annotated[Session, Depends(get_db)]


def client_ip(request: Request) -> str | None:
    # Behind the load balancer, X-Forwarded-For is set by trusted infrastructure (see docs/SECURITY.md).
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


@dataclass
class UserContext:
    user: User
    ip_address: str | None
    user_agent: str | None
    request_id: str | None

    def actor(self, tenant_id: uuid.UUID | None = None) -> AuditActor:
        return AuditActor(self.user.id, tenant_id, self.ip_address, self.user_agent, self.request_id)


@dataclass
class TenantContext:
    user: User
    tenant: Tenant
    membership: TenantMembership
    role: Role
    permissions: frozenset[str] = field(default_factory=frozenset)
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None

    @property
    def tenant_id(self) -> uuid.UUID:
        return self.tenant.id

    @property
    def user_id(self) -> uuid.UUID:
        return self.user.id

    def has(self, permission: str) -> bool:
        return permission in self.permissions

    def require(self, permission: str) -> None:
        if permission not in self.permissions:
            raise PermissionDenied(f"You do not have permission to perform this action ({permission})")

    def actor(self) -> AuditActor:
        return AuditActor(self.user.id, self.tenant.id, self.ip_address, self.user_agent, self.request_id)

    def restore_rls(self, db: Session) -> None:
        """Re-apply RLS context after a commit (settings are transaction-local)."""
        set_rls_context(db, user_id=self.user.id, tenant_id=self.tenant.id)


def _extract_token(request: Request) -> tuple[str | None, bool]:
    auth = request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip(), False
    cookie = request.cookies.get(ACCESS_COOKIE)
    return (cookie, True) if cookie else (None, False)


def _check_csrf(request: Request) -> None:
    if request.method in SAFE_METHODS:
        return
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get(CSRF_HEADER)
    if not cookie or not header or not constant_time_equals(cookie, header):
        raise PermissionDenied("CSRF token missing or invalid", code="csrf_failed")


def get_user_context(request: Request, db: DB) -> UserContext:
    token, from_cookie = _extract_token(request)
    if not token:
        raise NotAuthenticated("Authentication required")
    if from_cookie:
        _check_csrf(request)
    try:
        payload = decode_jwt(token, "access")
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise NotAuthenticated("Session expired or invalid", code="token_invalid") from exc
    set_rls_context(db, user_id=user_id)
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise NotAuthenticated("Account is not active")
    return UserContext(
        user=user,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
        request_id=request.headers.get("x-request-id"),
    )


CurrentUser = Annotated[UserContext, Depends(get_user_context)]


def get_tenant_context(
    uctx: CurrentUser,
    db: DB,
    x_tenant_id: Annotated[str | None, Header()] = None,
) -> TenantContext:
    if not x_tenant_id:
        raise PermissionDenied("X-Tenant-ID header is required", code="tenant_required")
    try:
        tenant_id = uuid.UUID(x_tenant_id)
    except ValueError as exc:
        raise PermissionDenied("Invalid tenant identifier", code="tenant_invalid") from exc

    set_rls_context(db, user_id=uctx.user.id, tenant_id=tenant_id)
    membership = db.scalar(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant_id, TenantMembership.user_id == uctx.user.id
        )
    )
    # Identical error for "no such tenant" and "not a member" so tenant IDs cannot be probed.
    if membership is None or membership.status != "active":
        raise PermissionDenied("You do not have access to this organization", code="tenant_forbidden")
    tenant = db.get(Tenant, tenant_id)
    role = db.get(Role, membership.role_id)
    if tenant is None or role is None or tenant.status != "active":
        raise PermissionDenied("You do not have access to this organization", code="tenant_forbidden")
    return TenantContext(
        user=uctx.user,
        tenant=tenant,
        membership=membership,
        role=role,
        permissions=frozenset(role.permission_keys),
        ip_address=uctx.ip_address,
        user_agent=uctx.user_agent,
        request_id=uctx.request_id,
    )


Ctx = Annotated[TenantContext, Depends(get_tenant_context)]


def require(*permissions: str) -> Callable[[TenantContext], TenantContext]:
    """Route dependency: the caller must hold ALL of the listed permissions."""

    def _dep(ctx: Ctx) -> TenantContext:
        for permission in permissions:
            ctx.require(permission)
        return ctx

    return _dep
