"""Organization administration: settings, members, invitations and roles."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import TenantContext
from app.core.config import get_settings
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.core.security import generate_token, hash_token
from app.domains.audit import service as audit
from app.domains.identity.models import User
from app.domains.identity.service import find_user_by_email
from app.domains.tenancy.models import Invitation, Permission, Role, RolePermission, TenantMembership
from app.domains.tenancy.permissions import OWNER_ONLY_ROLES


def _now() -> datetime:
    return datetime.now(UTC)


# --- settings ---------------------------------------------------------------------------------------
def update_tenant(db: Session, ctx: TenantContext, changes: dict[str, object]) -> None:
    tenant = ctx.tenant
    if changes.get("home_state") and tenant.country_code != "US":
        raise ValidationFailed("Home state applies to US organizations only")
    fields = list(changes)
    before = audit.snapshot(tenant, fields)
    for key, value in changes.items():
        setattr(tenant, key, value)
    db.flush()
    delta = audit.diff(before, audit.snapshot(tenant, fields))
    if delta:
        audit.record(db, ctx.actor(), action="tenant.updated", entity_type="tenant", entity_id=tenant.id,
                     summary="Organization settings updated", changes=delta)


# --- roles -------------------------------------------------------------------------------------------
def list_roles(db: Session) -> list[tuple[Role, int]]:
    counts = dict(
        db.execute(select(TenantMembership.role_id, func.count()).group_by(TenantMembership.role_id)).all()
    )
    roles = db.scalars(select(Role).order_by(Role.is_system.desc(), Role.name)).all()
    return [(r, int(counts.get(r.id, 0))) for r in roles]


def get_role(db: Session, role_id: uuid.UUID) -> Role:
    role = db.get(Role, role_id)  # RLS: system roles + this tenant's roles only
    if role is None:
        raise NotFound("Role not found")
    return role


def _validate_permissions(db: Session, ctx: TenantContext, keys: list[str]) -> set[str]:
    wanted = set(keys)
    known = set(db.scalars(select(Permission.key)))
    unknown = wanted - known
    if unknown:
        raise ValidationFailed(f"Unknown permissions: {', '.join(sorted(unknown))}")
    escalation = wanted - ctx.permissions
    if escalation:
        raise PermissionDenied(f"You cannot grant permissions you do not hold: {', '.join(sorted(escalation))}")
    return wanted


def create_role(db: Session, ctx: TenantContext, name: str, description: str | None, permissions: list[str]) -> Role:
    perms = _validate_permissions(db, ctx, permissions)
    key = "custom_" + (re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:50] or "role")
    if db.scalar(select(Role).where(Role.tenant_id == ctx.tenant_id, Role.key == key)):
        raise Conflict("A role with this name already exists")
    role = Role(id=uuid.uuid4(), tenant_id=ctx.tenant_id, key=key, name=name, description=description,
                is_system=False)
    role.permissions = [RolePermission(permission_key=p) for p in sorted(perms)]
    db.add(role)
    db.flush()
    audit.record(db, ctx.actor(), action="role.created", entity_type="role", entity_id=role.id,
                 summary=f"Role '{name}' created", changes={"permissions": sorted(perms)})
    return role


def update_role(db: Session, ctx: TenantContext, role: Role, changes: dict[str, object]) -> Role:
    if role.is_system or role.tenant_id != ctx.tenant_id:
        raise PermissionDenied("System roles cannot be modified")
    before = {"name": role.name, "description": role.description, "permissions": role.permission_keys}
    if changes.get("name"):
        role.name = str(changes["name"])
    if "description" in changes:
        role.description = changes["description"]  # type: ignore[assignment]
    if changes.get("permissions") is not None:
        perms = _validate_permissions(db, ctx, list(changes["permissions"]))  # type: ignore[arg-type]
        role.permissions = [RolePermission(permission_key=p) for p in sorted(perms)]
    db.flush()
    after = {"name": role.name, "description": role.description, "permissions": role.permission_keys}
    audit.record(db, ctx.actor(), action="role.updated", entity_type="role", entity_id=role.id,
                 summary=f"Role '{role.name}' updated", changes=audit.diff(before, after))
    return role


def delete_role(db: Session, ctx: TenantContext, role: Role) -> None:
    if role.is_system or role.tenant_id != ctx.tenant_id:
        raise PermissionDenied("System roles cannot be deleted")
    in_use = db.scalar(select(func.count()).select_from(TenantMembership).where(TenantMembership.role_id == role.id))
    pending = db.scalar(
        select(func.count()).select_from(Invitation).where(
            Invitation.role_id == role.id, Invitation.accepted_at.is_(None), Invitation.revoked_at.is_(None)
        )
    )
    if in_use or pending:
        raise Conflict("Reassign members and pending invitations before deleting this role")
    audit.record(db, ctx.actor(), action="role.deleted", entity_type="role", entity_id=role.id,
                 summary=f"Role '{role.name}' deleted")
    db.delete(role)
    db.flush()


# --- members -----------------------------------------------------------------------------------------
def list_members(db: Session) -> list[tuple[TenantMembership, User, Role]]:
    rows = db.execute(
        select(TenantMembership, User, Role)
        .join(User, User.id == TenantMembership.user_id)
        .join(Role, Role.id == TenantMembership.role_id)
        .order_by(User.full_name)
    ).all()
    return [(m, u, r) for m, u, r in rows]


def _active_owner_count(db: Session, ctx: TenantContext) -> int:
    return db.scalar(
        select(func.count())
        .select_from(TenantMembership)
        .join(Role, Role.id == TenantMembership.role_id)
        .where(TenantMembership.tenant_id == ctx.tenant_id, TenantMembership.status == "active",
               Role.key == "owner", Role.tenant_id.is_(None))
    ) or 0


def _assert_can_assign(ctx: TenantContext, role: Role) -> None:
    if role.key in OWNER_ONLY_ROLES and role.is_system and ctx.role.key != "owner":
        raise PermissionDenied("Only an owner can grant the Owner role")
    missing = set(role.permission_keys) - ctx.permissions
    if missing:
        raise PermissionDenied("You cannot assign a role with permissions you do not hold")


def update_member(
    db: Session, ctx: TenantContext, membership_id: uuid.UUID, changes: dict[str, object]
) -> TenantMembership:
    membership = db.get(TenantMembership, membership_id)
    if membership is None or membership.tenant_id != ctx.tenant_id:
        raise NotFound("Member not found")
    current_role = get_role(db, membership.role_id)
    is_owner_target = current_role.key == "owner" and current_role.is_system
    if is_owner_target and ctx.role.key != "owner":
        raise PermissionDenied("Only an owner can change another owner")

    before = {"role": current_role.key, "status": membership.status, "job_title": membership.job_title}
    new_role = current_role
    if changes.get("role_id") is not None and changes["role_id"] != membership.role_id:
        new_role = get_role(db, changes["role_id"])  # type: ignore[arg-type]
        _assert_can_assign(ctx, new_role)
    new_status = changes.get("status") or membership.status

    demoting_owner = is_owner_target and (new_role.key != "owner" or new_status != "active")
    if demoting_owner and _active_owner_count(db, ctx) <= 1:
        raise Conflict("An organization must keep at least one active owner")
    if membership.user_id == ctx.user_id and new_status != "active":
        raise Conflict("You cannot suspend yourself")

    membership.role_id = new_role.id
    membership.status = str(new_status)
    if "job_title" in changes:
        membership.job_title = changes["job_title"]  # type: ignore[assignment]
    db.flush()
    after = {"role": new_role.key, "status": membership.status, "job_title": membership.job_title}
    delta = audit.diff(before, after)
    if delta:
        audit.record(db, ctx.actor(), action="member.updated", entity_type="membership", entity_id=membership.id,
                     summary="Member access updated", changes=delta)
    return membership


def remove_member(db: Session, ctx: TenantContext, membership_id: uuid.UUID) -> None:
    membership = db.get(TenantMembership, membership_id)
    if membership is None or membership.tenant_id != ctx.tenant_id:
        raise NotFound("Member not found")
    role = get_role(db, membership.role_id)
    if role.key == "owner" and role.is_system:
        if ctx.role.key != "owner":
            raise PermissionDenied("Only an owner can remove another owner")
        if _active_owner_count(db, ctx) <= 1:
            raise Conflict("An organization must keep at least one active owner")
    if membership.user_id == ctx.user_id:
        raise Conflict("You cannot remove yourself")
    audit.record(db, ctx.actor(), action="member.removed", entity_type="membership", entity_id=membership.id,
                 summary="Member removed from organization", changes={"user_id": str(membership.user_id)})
    db.delete(membership)
    db.flush()


# --- invitations -------------------------------------------------------------------------------------
def invitation_status(inv: Invitation) -> str:
    if inv.accepted_at:
        return "accepted"
    if inv.revoked_at:
        return "revoked"
    if inv.expires_at <= _now():
        return "expired"
    return "pending"


def list_invitations(db: Session) -> list[tuple[Invitation, Role]]:
    rows = db.execute(
        select(Invitation, Role).join(Role, Role.id == Invitation.role_id).order_by(Invitation.created_at.desc())
    ).all()
    return [(i, r) for i, r in rows]


def create_invitation(db: Session, ctx: TenantContext, email: str, role_id: uuid.UUID) -> tuple[Invitation, str]:
    role = get_role(db, role_id)
    _assert_can_assign(ctx, role)
    email = email.strip().lower()
    existing_user = find_user_by_email(db, email)
    if existing_user is not None:
        already = db.scalar(
            select(TenantMembership).where(TenantMembership.tenant_id == ctx.tenant_id,
                                           TenantMembership.user_id == existing_user.id)
        )
        if already is not None:
            raise Conflict("This person is already a member of the organization")
    pending = db.scalars(
        select(Invitation).where(func.lower(Invitation.email) == email, Invitation.accepted_at.is_(None),
                                 Invitation.revoked_at.is_(None))
    ).all()
    for inv in pending:  # a new invitation supersedes older pending ones
        inv.revoked_at = _now()
    token = generate_token()
    invitation = Invitation(
        id=uuid.uuid4(), tenant_id=ctx.tenant_id, email=email, role_id=role.id, token_hash=hash_token(token),
        invited_by_id=ctx.user_id,
        expires_at=_now() + timedelta(seconds=get_settings().invitation_ttl_seconds),
    )
    db.add(invitation)
    db.flush()
    audit.record(db, ctx.actor(), action="member.invited", entity_type="invitation", entity_id=invitation.id,
                 summary=f"Invited {email} as {role.name}")
    return invitation, token


def revoke_invitation(db: Session, ctx: TenantContext, invitation_id: uuid.UUID) -> Invitation:
    inv = db.get(Invitation, invitation_id)
    if inv is None or inv.tenant_id != ctx.tenant_id:
        raise NotFound("Invitation not found")
    if invitation_status(inv) != "pending":
        raise Conflict("Only pending invitations can be revoked")
    inv.revoked_at = _now()
    audit.record(db, ctx.actor(), action="member.invitation_revoked", entity_type="invitation", entity_id=inv.id,
                 summary=f"Invitation for {inv.email} revoked")
    return inv
