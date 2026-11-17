"""Identity: registration, authentication, session rotation, MFA (TOTP) and invitation acceptance."""

from __future__ import annotations

import re
import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
import pyotp
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import set_rls_context
from app.core.errors import Conflict, NotAuthenticated, NotFound, ValidationFailed
from app.core.security import (
    constant_time_equals,
    create_jwt,
    decode_jwt,
    decrypt_field,
    encrypt_field,
    generate_token,
    hash_password,
    hash_token,
    password_needs_rehash,
    verify_password,
)
from app.domains.audit import service as audit
from app.domains.audit.service import AuditActor
from app.domains.identity.models import AuthSession, User
from app.domains.tenancy.models import Invitation, Role, Tenant, TenantMembership

MFA_ISSUER = "QS Intelligence USA"
# A rotated refresh token presented again within this window is treated as a benign concurrent refresh
# (e.g. two browser tabs) and rejected without revoking the whole session family.
REFRESH_REUSE_GRACE_SECONDS = 30


def _now() -> datetime:
    return datetime.now(UTC)


# --- lookups that run before an RLS user context exists -------------------------------------------
def find_user_by_email(db: Session, email: str) -> User | None:
    stmt = select(User).from_statement(text("SELECT * FROM auth_find_user_by_email(:email)"))
    return db.scalars(stmt, {"email": email.strip()}).first()


def _find_session(db: Session, token: str) -> AuthSession | None:
    stmt = select(AuthSession).from_statement(text("SELECT * FROM auth_find_session_by_token_hash(:h)"))
    return db.scalars(stmt, {"h": hash_token(token)}).first()


def _find_invitation(db: Session, token: str) -> Invitation | None:
    stmt = select(Invitation).from_statement(text("SELECT * FROM auth_find_invitation_by_token_hash(:h)"))
    return db.scalars(stmt, {"h": hash_token(token)}).first()


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48] or "org"
    if len(slug) < 2:
        slug = f"{slug}-org"
    return slug


def unique_tenant_slug(db: Session, name: str) -> str:
    base = _slugify(name)
    candidate = base
    for _ in range(10):
        if not db.scalar(text("SELECT auth_tenant_slug_exists(:s)"), {"s": candidate}):
            return candidate
        candidate = f"{base}-{secrets.token_hex(3)}"
    raise Conflict("Could not allocate an organization identifier; try a different name")


def system_role(db: Session, key: str) -> Role:
    role = db.scalar(select(Role).where(Role.tenant_id.is_(None), Role.key == key))
    if role is None:
        raise RuntimeError(f"System role {key!r} missing; run migrations")
    return role


# --- registration ---------------------------------------------------------------------------------
@dataclass
class RegistrationResult:
    user: User
    tenant: Tenant


def register_organization(
    db: Session,
    *,
    full_name: str,
    email: str,
    password: str,
    organization_name: str,
    home_state: str | None,
    meta: AuditActor,
) -> RegistrationResult:
    if find_user_by_email(db, email) is not None:
        raise Conflict("An account with this email already exists. Sign in instead.", code="email_taken")

    user_id, tenant_id = uuid.uuid4(), uuid.uuid4()
    # Context must include the new ids *before* insert so INSERT ... RETURNING passes the SELECT policy.
    set_rls_context(db, user_id=user_id, tenant_id=tenant_id)
    user = User(id=user_id, email=email.strip().lower(), full_name=full_name, password_hash=hash_password(password))
    db.add(user)
    db.flush()

    tenant = Tenant(
        id=tenant_id, name=organization_name, slug=unique_tenant_slug(db, organization_name), home_state=home_state
    )
    db.add(tenant)
    db.flush()
    db.add(TenantMembership(tenant_id=tenant_id, user_id=user_id, role_id=system_role(db, "owner").id))
    db.flush()

    actor = AuditActor(user_id, tenant_id, meta.ip_address, meta.user_agent, meta.request_id)
    audit.record(db, actor, action="tenant.created", entity_type="tenant", entity_id=tenant_id,
                 summary=f"Organization '{organization_name}' created")
    audit.record(db, actor, action="user.registered", entity_type="user", entity_id=user_id,
                 summary=f"{full_name} registered as organization owner")
    return RegistrationResult(user=user, tenant=tenant)


# --- authentication -------------------------------------------------------------------------------
def authenticate(db: Session, email: str, password: str, meta: AuditActor) -> User:
    user = find_user_by_email(db, email)
    valid = verify_password(password, user.password_hash if user else None)
    if user is None or not valid or not user.is_active:
        if user is not None:
            set_rls_context(db, user_id=user.id)
            audit.record(db, AuditActor(user.id, None, meta.ip_address, meta.user_agent, meta.request_id),
                         action="auth.login_failed", entity_type="user", entity_id=user.id,
                         summary="Failed sign-in attempt", tenant_id=None)
        raise NotAuthenticated("Invalid email or password", code="invalid_credentials")
    set_rls_context(db, user_id=user.id)
    if user.password_hash and password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return user


def complete_login(db: Session, user: User, meta: AuditActor) -> None:
    user.last_login_at = _now()
    audit.record(db, AuditActor(user.id, None, meta.ip_address, meta.user_agent, meta.request_id),
                 action="auth.login", entity_type="user", entity_id=user.id, summary="Signed in", tenant_id=None)


def create_access_token(user: User) -> str:
    return create_jwt(user.id, "access", get_settings().access_token_ttl_seconds)


def create_session(
    db: Session, user: User, *, user_agent: str | None, ip: str | None, family_id: uuid.UUID | None = None
) -> str:
    token = generate_token()
    db.add(
        AuthSession(
            user_id=user.id,
            family_id=family_id or uuid.uuid4(),
            token_hash=hash_token(token),
            expires_at=_now() + timedelta(seconds=get_settings().refresh_token_ttl_seconds),
            user_agent=(user_agent or "")[:500] or None,
            ip_address=ip,
        )
    )
    db.flush()
    return token


class RefreshReuseDetected(NotAuthenticated):
    """Raised after the session family was revoked; the caller must COMMIT before re-raising."""


def rotate_refresh_token(db: Session, token: str, *, user_agent: str | None, ip: str | None) -> tuple[User, str]:
    session = _find_session(db, token)
    if session is None:
        raise NotAuthenticated("Session expired. Please sign in again.", code="refresh_invalid")
    set_rls_context(db, user_id=session.user_id)
    now = _now()
    if session.revoked_at is not None or session.expires_at <= now:
        raise NotAuthenticated("Session expired. Please sign in again.", code="refresh_invalid")
    if session.rotated_at is not None:
        if (now - session.rotated_at).total_seconds() <= REFRESH_REUSE_GRACE_SECONDS:
            raise NotAuthenticated("Session was refreshed elsewhere", code="refresh_superseded")
        revoke_family(db, session.family_id)
        audit.record(db, AuditActor(session.user_id, None, ip, user_agent), action="auth.refresh_reuse_detected",
                     entity_type="user", entity_id=session.user_id,
                     summary="Refresh token reuse detected; all sessions in the family were revoked", tenant_id=None)
        raise RefreshReuseDetected("Session invalidated for security reasons. Please sign in again.",
                                   code="refresh_reused")
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise NotAuthenticated("Account is not active")
    session.rotated_at = now
    new_token = create_session(db, user, user_agent=user_agent, ip=ip, family_id=session.family_id)
    return user, new_token


def revoke_family(db: Session, family_id: uuid.UUID) -> None:
    db.execute(
        update(AuthSession)
        .where(AuthSession.family_id == family_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def logout(db: Session, token: str | None) -> uuid.UUID | None:
    if not token:
        return None
    session = _find_session(db, token)
    if session is None:
        return None
    set_rls_context(db, user_id=session.user_id)
    revoke_family(db, session.family_id)
    return session.user_id


def revoke_all_sessions(db: Session, user_id: uuid.UUID) -> None:
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def change_password(db: Session, user: User, current: str, new: str, meta: AuditActor) -> None:
    if not verify_password(current, user.password_hash):
        raise ValidationFailed("Current password is incorrect", code="invalid_password")
    if verify_password(new, user.password_hash):
        raise ValidationFailed("New password must be different from the current password")
    user.password_hash = hash_password(new)
    revoke_all_sessions(db, user.id)
    audit.record(db, meta, action="auth.password_changed", entity_type="user", entity_id=user.id,
                 summary="Password changed; all sessions revoked", tenant_id=None)


# --- MFA (TOTP, RFC 6238) ------------------------------------------------------------------------
def create_mfa_challenge(user: User) -> str:
    return create_jwt(user.id, "mfa", get_settings().mfa_challenge_ttl_seconds)


def user_from_mfa_challenge(db: Session, token: str) -> User:
    try:
        payload = decode_jwt(token, "mfa")
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise NotAuthenticated("Verification expired. Please sign in again.", code="mfa_token_invalid") from exc
    set_rls_context(db, user_id=user_id)
    user = db.get(User, user_id)
    if user is None or not user.is_active or not user.mfa_enabled:
        raise NotAuthenticated("Verification expired. Please sign in again.", code="mfa_token_invalid")
    return user


def _verify_totp(secret: str, code: str, last_step: int | None) -> int | None:
    totp = pyotp.TOTP(secret)
    current = int(time.time()) // totp.interval
    for step in (current - 1, current, current + 1):
        if last_step is not None and step <= last_step:
            continue
        if constant_time_equals(totp.generate_otp(step), code):
            return step
    return None


def verify_mfa_code(user: User, code: str) -> bool:
    if not user.mfa_enabled or not user.mfa_secret_encrypted:
        return False
    step = _verify_totp(decrypt_field(user.mfa_secret_encrypted), code, user.mfa_last_totp_step)
    if step is None:
        return False
    user.mfa_last_totp_step = step
    return True


def start_mfa_setup(user: User, password: str) -> tuple[str, str]:
    if not verify_password(password, user.password_hash):
        raise ValidationFailed("Password is incorrect", code="invalid_password")
    if user.mfa_enabled:
        raise Conflict("Two-factor authentication is already enabled")
    secret = pyotp.random_base32()
    user.mfa_pending_secret_encrypted = encrypt_field(secret)
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=MFA_ISSUER)
    return secret, uri


def enable_mfa(db: Session, user: User, code: str, meta: AuditActor) -> None:
    if user.mfa_enabled:
        raise Conflict("Two-factor authentication is already enabled")
    if not user.mfa_pending_secret_encrypted:
        raise ValidationFailed("Start two-factor setup first")
    secret = decrypt_field(user.mfa_pending_secret_encrypted)
    step = _verify_totp(secret, code, None)
    if step is None:
        raise ValidationFailed("Invalid verification code", code="invalid_code")
    user.mfa_secret_encrypted = user.mfa_pending_secret_encrypted
    user.mfa_pending_secret_encrypted = None
    user.mfa_enabled = True
    user.mfa_last_totp_step = step
    audit.record(db, meta, action="auth.mfa_enabled", entity_type="user", entity_id=user.id,
                 summary="Two-factor authentication enabled", tenant_id=None)


def disable_mfa(db: Session, user: User, password: str, code: str, meta: AuditActor) -> None:
    if not user.mfa_enabled:
        raise Conflict("Two-factor authentication is not enabled")
    if not verify_password(password, user.password_hash):
        raise ValidationFailed("Password is incorrect", code="invalid_password")
    if not verify_mfa_code(user, code):
        raise ValidationFailed("Invalid verification code", code="invalid_code")
    user.mfa_enabled = False
    user.mfa_secret_encrypted = None
    user.mfa_last_totp_step = None
    audit.record(db, meta, action="auth.mfa_disabled", entity_type="user", entity_id=user.id,
                 summary="Two-factor authentication disabled", tenant_id=None)


# --- memberships ----------------------------------------------------------------------------------
def memberships_for_user(db: Session, user_id: uuid.UUID) -> list[tuple[TenantMembership, Tenant, Role | None]]:
    """All active memberships of the user (RLS permits a user to see their own memberships)."""
    rows = db.execute(
        select(TenantMembership, Tenant)
        .join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .where(TenantMembership.user_id == user_id, TenantMembership.status == "active", Tenant.status == "active")
        .order_by(Tenant.name)
    ).all()
    result = []
    for membership, tenant in rows:
        # Custom roles of other tenants are hidden by RLS until that tenant is selected; system roles are visible.
        role = db.get(Role, membership.role_id)
        result.append((membership, tenant, role))
    return result


# --- invitations ----------------------------------------------------------------------------------
@dataclass
class InvitationLookup:
    invitation: Invitation
    tenant: Tenant
    role: Role
    existing_user: User | None


def lookup_invitation(db: Session, token: str) -> InvitationLookup:
    invitation = _find_invitation(db, token)
    if invitation is None or invitation.revoked_at or invitation.accepted_at or invitation.expires_at <= _now():
        raise NotFound("This invitation is invalid, expired or already used", code="invitation_invalid")
    existing = find_user_by_email(db, invitation.email)
    set_rls_context(db, user_id=existing.id if existing else None, tenant_id=invitation.tenant_id)
    tenant = db.get(Tenant, invitation.tenant_id)
    role = db.get(Role, invitation.role_id)
    if tenant is None or role is None or tenant.status != "active":
        raise NotFound("This invitation is invalid, expired or already used", code="invitation_invalid")
    return InvitationLookup(invitation, tenant, role, existing)


def accept_invitation(
    db: Session, token: str, *, full_name: str | None, password: str | None, meta: AuditActor
) -> tuple[User, bool]:
    """Returns (user, created). New accounts are signed in; existing accounts prove ownership by password."""
    found = lookup_invitation(db, token)
    inv = found.invitation
    if found.existing_user is not None:
        user = found.existing_user
        if not password or not verify_password(password, user.password_hash):
            raise ValidationFailed("Enter the password for your existing account", code="invalid_password")
        created = False
    else:
        if not full_name or not password:
            raise ValidationFailed("Full name and password are required to create your account")
        user_id = uuid.uuid4()
        set_rls_context(db, user_id=user_id, tenant_id=inv.tenant_id)
        user = User(id=user_id, email=inv.email.lower(), full_name=full_name, password_hash=hash_password(password))
        db.add(user)
        db.flush()
        created = True

    set_rls_context(db, user_id=user.id, tenant_id=inv.tenant_id)
    existing = db.scalar(
        select(TenantMembership).where(TenantMembership.tenant_id == inv.tenant_id,
                                       TenantMembership.user_id == user.id)
    )
    if existing is not None:
        raise Conflict("You are already a member of this organization")
    db.add(TenantMembership(tenant_id=inv.tenant_id, user_id=user.id, role_id=inv.role_id))
    inv.accepted_at = _now()
    db.flush()
    audit.record(db, AuditActor(user.id, inv.tenant_id, meta.ip_address, meta.user_agent, meta.request_id),
                 action="member.joined", entity_type="membership", entity_id=user.id,
                 summary=f"{user.full_name} accepted an invitation as {found.role.name}")
    return user, created
