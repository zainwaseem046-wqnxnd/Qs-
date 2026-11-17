from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select

from app.api.deps import DB, Ctx, TenantContext, require
from app.core.config import get_settings
from app.domains.tenancy import service
from app.domains.tenancy.models import Permission
from app.domains.tenancy.permissions import P
from app.domains.tenancy.schemas import (
    CurrentTenantOut,
    InvitationCreate,
    InvitationCreated,
    InvitationOut,
    MemberOut,
    MemberUpdate,
    PermissionOut,
    RoleCreate,
    RoleOut,
    RoleRef,
    RoleUpdate,
    TenantOut,
    TenantUpdate,
)

router = APIRouter(prefix="/tenant", tags=["organization"])


def _role_out(role, count: int = 0) -> RoleOut:  # type: ignore[no-untyped-def]
    return RoleOut(id=role.id, key=role.key, name=role.name, description=role.description,
                   is_system=role.is_system, permission_keys=role.permission_keys, member_count=count)


@router.get("", response_model=CurrentTenantOut)
def current_tenant(ctx: Ctx) -> CurrentTenantOut:
    return CurrentTenantOut(
        tenant=TenantOut.model_validate(ctx.tenant),
        role=RoleRef.model_validate(ctx.role),
        permissions=sorted(ctx.permissions),
    )


@router.patch("", response_model=TenantOut)
def update_tenant(
    body: TenantUpdate, db: DB, ctx: Annotated[TenantContext, Depends(require(P.TENANT_MANAGE))]
) -> TenantOut:
    service.update_tenant(db, ctx, body.model_dump(exclude_unset=True))
    db.commit()
    return TenantOut.model_validate(ctx.tenant)


@router.get("/permissions", response_model=list[PermissionOut])
def permission_catalog(db: DB, ctx: Ctx) -> list[PermissionOut]:
    rows = db.scalars(select(Permission).order_by(Permission.category, Permission.key)).all()
    return [PermissionOut.model_validate(p) for p in rows]


@router.get("/roles", response_model=list[RoleOut])
def list_roles(db: DB, ctx: Annotated[TenantContext, Depends(require(P.MEMBERS_VIEW))]) -> list[RoleOut]:
    return [_role_out(r, c) for r, c in service.list_roles(db)]


@router.post("/roles", response_model=RoleOut, status_code=201)
def create_role(body: RoleCreate, db: DB, ctx: Annotated[TenantContext, Depends(require(P.ROLES_MANAGE))]) -> RoleOut:
    role = service.create_role(db, ctx, body.name, body.description, body.permissions)
    db.commit()
    return _role_out(role)


@router.patch("/roles/{role_id}", response_model=RoleOut)
def update_role(
    role_id: uuid.UUID, body: RoleUpdate, db: DB, ctx: Annotated[TenantContext, Depends(require(P.ROLES_MANAGE))]
) -> RoleOut:
    role = service.update_role(db, ctx, service.get_role(db, role_id), body.model_dump(exclude_unset=True))
    db.commit()
    return _role_out(role)


@router.delete("/roles/{role_id}", status_code=204)
def delete_role(
    role_id: uuid.UUID, db: DB, ctx: Annotated[TenantContext, Depends(require(P.ROLES_MANAGE))]
) -> Response:
    service.delete_role(db, ctx, service.get_role(db, role_id))
    db.commit()
    return Response(status_code=204)


@router.get("/members", response_model=list[MemberOut])
def list_members(db: DB, ctx: Annotated[TenantContext, Depends(require(P.MEMBERS_VIEW))]) -> list[MemberOut]:
    return [
        MemberOut(id=m.id, user_id=u.id, full_name=u.full_name, email=u.email, mfa_enabled=u.mfa_enabled,
                  role=RoleRef.model_validate(r), status=m.status, job_title=m.job_title, created_at=m.created_at)
        for m, u, r in service.list_members(db)
    ]


@router.patch("/members/{membership_id}", response_model=MemberOut)
def update_member(
    membership_id: uuid.UUID, body: MemberUpdate, db: DB,
    ctx: Annotated[TenantContext, Depends(require(P.MEMBERS_MANAGE))],
) -> MemberOut:
    m = service.update_member(db, ctx, membership_id, body.model_dump(exclude_unset=True))
    db.commit()
    ctx.restore_rls(db)
    for member, user, role in service.list_members(db):
        if member.id == m.id:
            return MemberOut(id=member.id, user_id=user.id, full_name=user.full_name, email=user.email,
                             mfa_enabled=user.mfa_enabled, role=RoleRef.model_validate(role), status=member.status,
                             job_title=member.job_title, created_at=member.created_at)
    raise AssertionError("updated member not visible")


@router.delete("/members/{membership_id}", status_code=204)
def remove_member(
    membership_id: uuid.UUID, db: DB, ctx: Annotated[TenantContext, Depends(require(P.MEMBERS_MANAGE))]
) -> Response:
    service.remove_member(db, ctx, membership_id)
    db.commit()
    return Response(status_code=204)


@router.get("/invitations", response_model=list[InvitationOut])
def list_invitations(
    db: DB, ctx: Annotated[TenantContext, Depends(require(P.MEMBERS_MANAGE))]
) -> list[InvitationOut]:
    return [
        InvitationOut(id=i.id, email=i.email, role=RoleRef.model_validate(r), expires_at=i.expires_at,
                      created_at=i.created_at, status=service.invitation_status(i))
        for i, r in service.list_invitations(db)
    ]


@router.post("/invitations", response_model=InvitationCreated, status_code=201)
def create_invitation(
    body: InvitationCreate, db: DB, ctx: Annotated[TenantContext, Depends(require(P.MEMBERS_MANAGE))]
) -> InvitationCreated:
    inv, token = service.create_invitation(db, ctx, str(body.email), body.role_id)
    role = service.get_role(db, inv.role_id)
    db.commit()
    return InvitationCreated(
        id=inv.id, email=inv.email, role=RoleRef.model_validate(role), expires_at=inv.expires_at,
        created_at=inv.created_at, status="pending",
        accept_url=f"{get_settings().public_app_url.rstrip('/')}/invite/{token}",
    )


@router.delete("/invitations/{invitation_id}", status_code=204)
def revoke_invitation(
    invitation_id: uuid.UUID, db: DB, ctx: Annotated[TenantContext, Depends(require(P.MEMBERS_MANAGE))]
) -> Response:
    service.revoke_invitation(db, ctx, invitation_id)
    db.commit()
    return Response(status_code=204)
