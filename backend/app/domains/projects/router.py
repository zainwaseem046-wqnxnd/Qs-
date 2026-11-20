from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import DB, Ctx, TenantContext, require
from app.core.money import SUPPORTED_CURRENCIES
from app.core.regions import COUNTRIES, MEASUREMENT_SYSTEMS
from app.core.schemas import Page
from app.domains.audit.schemas import AuditEventOut, to_out
from app.domains.audit.service import list_events
from app.domains.documents.constants import DISCIPLINES, DOCUMENT_CATEGORIES
from app.domains.projects import constants as C
from app.domains.projects import service
from app.domains.projects.models import Project
from app.domains.projects.schemas import (
    ProjectCreate,
    ProjectListItem,
    ProjectMemberIn,
    ProjectMemberOut,
    ProjectMemberUpdate,
    ProjectOut,
    ProjectPartyIn,
    ProjectPartyOut,
    ProjectPhaseIn,
    ProjectPhaseOut,
    ProjectUpdate,
    VocabularyOut,
)
from app.domains.tenancy.permissions import P

router = APIRouter(prefix="/projects", tags=["projects"])
vocab_router = APIRouter(tags=["reference"])


@vocab_router.get("/vocabulary", response_model=VocabularyOut)
def vocabulary(ctx: Ctx) -> VocabularyOut:
    country_vocab = C.vocab_for(ctx.tenant.country_code)
    return VocabularyOut(
        project_statuses=C.PROJECT_STATUSES, sectors=C.SECTORS,
        delivery_methods=country_vocab["delivery_methods"], contract_types=country_vocab["contract_types"],
        our_roles=country_vocab["our_roles"], project_member_roles=C.PROJECT_MEMBER_ROLES,
        party_roles=C.PARTY_ROLES, phase_statuses=C.PHASE_STATUSES, us_states=C.US_STATES,
        company_types=C.COMPANY_TYPES, document_categories=DOCUMENT_CATEGORIES, disciplines=DISCIPLINES,
        currencies=sorted(SUPPORTED_CURRENCIES),
        countries={c.code: c.name for c in COUNTRIES.values()}, measurement_systems=MEASUREMENT_SYSTEMS,
    )


def project_out(ctx: TenantContext, project: Project) -> ProjectOut:
    out = ProjectOut.model_validate(project)
    out.can_edit = service.can_edit(ctx, project)
    if not ctx.has(P.PROJECTS_FINANCIALS_VIEW):
        out.original_contract_value = None
        out.retainage_percent = None
        out.financials_visible = False
    return out


def list_item(ctx: TenantContext, p: Project) -> ProjectListItem:
    city, state = service.address_city_state(p.site_address)
    item = ProjectListItem.model_validate(
        {**{k: getattr(p, k) for k in ProjectListItem.model_fields if hasattr(p, k)}, "city": city,
         "state_code": state}
    )
    if not ctx.has(P.PROJECTS_FINANCIALS_VIEW):
        item.original_contract_value = None
    return item


@router.get("", response_model=Page[ProjectListItem])
def list_projects(
    db: DB, ctx: Ctx,
    q: Annotated[str | None, Query(max_length=100)] = None,
    status: str | None = None,
    sector: str | None = None,
    include_archived: bool = False,
    sort: Literal["name", "number", "updated_at", "start_date", "status", "contract_value"] = "updated_at",
    order: Literal["asc", "desc"] = "desc",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ProjectListItem]:
    rows, total = service.list_projects(db, ctx, q=q, status=status, sector=sector,
                                        include_archived=include_archived, sort=sort, order=order,
                                        limit=limit, offset=offset)
    return Page(items=[list_item(ctx, p) for p in rows], total=total, limit=limit, offset=offset)


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(
    body: ProjectCreate, db: DB, ctx: Annotated[TenantContext, Depends(require(P.PROJECTS_CREATE))]
) -> ProjectOut:
    project = service.create_project(db, ctx, body.model_dump(exclude={"site_address"}), body.site_address)
    db.commit()
    return project_out(ctx, project)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: uuid.UUID, db: DB, ctx: Ctx) -> ProjectOut:
    return project_out(ctx, service.get_project(db, ctx, project_id))


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: uuid.UUID, body: ProjectUpdate, db: DB, ctx: Ctx) -> ProjectOut:
    project = service.get_project(db, ctx, project_id)
    data = body.model_dump(exclude_unset=True, exclude={"site_address", "version"})
    service.update_project(db, ctx, project, body.version, data, body.site_address,
                           address_provided="site_address" in body.model_fields_set)
    db.commit()
    return project_out(ctx, project)


@router.post("/{project_id}/archive", response_model=ProjectOut)
def archive_project(project_id: uuid.UUID, db: DB, ctx: Ctx) -> ProjectOut:
    project = service.set_archived(db, ctx, service.get_project(db, ctx, project_id), True)
    db.commit()
    return project_out(ctx, project)


@router.post("/{project_id}/restore", response_model=ProjectOut)
def restore_project(project_id: uuid.UUID, db: DB, ctx: Ctx) -> ProjectOut:
    project = service.set_archived(db, ctx, service.get_project(db, ctx, project_id), False)
    db.commit()
    return project_out(ctx, project)


# --- team ---
def _member_out(m, u) -> ProjectMemberOut:  # type: ignore[no-untyped-def]
    return ProjectMemberOut(id=m.id, user_id=u.id, full_name=u.full_name, email=u.email,
                            project_role=m.project_role, created_at=m.created_at)


@router.get("/{project_id}/members", response_model=list[ProjectMemberOut])
def list_members(project_id: uuid.UUID, db: DB, ctx: Ctx) -> list[ProjectMemberOut]:
    project = service.get_project(db, ctx, project_id)
    return [_member_out(m, u) for m, u in service.list_members(db, project)]


@router.post("/{project_id}/members", response_model=ProjectMemberOut, status_code=201)
def add_member(project_id: uuid.UUID, body: ProjectMemberIn, db: DB, ctx: Ctx) -> ProjectMemberOut:
    project = service.get_project(db, ctx, project_id)
    member = service.add_member(db, ctx, project, body.user_id, body.project_role)
    db.commit()
    ctx.restore_rls(db)
    user = next(u for m, u in service.list_members(db, project) if m.id == member.id)
    return _member_out(member, user)


@router.patch("/{project_id}/members/{member_id}", response_model=ProjectMemberOut)
def update_member(
    project_id: uuid.UUID, member_id: uuid.UUID, body: ProjectMemberUpdate, db: DB, ctx: Ctx
) -> ProjectMemberOut:
    project = service.get_project(db, ctx, project_id)
    member = service.get_member(db, project, member_id)
    service.update_member(db, ctx, project, member, body.project_role)
    user = next(u for m, u in service.list_members(db, project) if m.id == member.id)
    db.commit()
    return _member_out(member, user)


@router.delete("/{project_id}/members/{member_id}", status_code=204)
def remove_member(project_id: uuid.UUID, member_id: uuid.UUID, db: DB, ctx: Ctx) -> Response:
    project = service.get_project(db, ctx, project_id)
    service.remove_member(db, ctx, project, service.get_member(db, project, member_id))
    db.commit()
    return Response(status_code=204)


# --- parties ---
@router.get("/{project_id}/parties", response_model=list[ProjectPartyOut])
def list_parties(project_id: uuid.UUID, db: DB, ctx: Ctx) -> list[ProjectPartyOut]:
    project = service.get_project(db, ctx, project_id)
    return [ProjectPartyOut.model_validate(p) for p in service.list_parties(db, project)]


@router.post("/{project_id}/parties", response_model=ProjectPartyOut, status_code=201)
def add_party(project_id: uuid.UUID, body: ProjectPartyIn, db: DB, ctx: Ctx) -> ProjectPartyOut:
    project = service.get_project(db, ctx, project_id)
    party = service.add_party(db, ctx, project, body.company_id, body.party_role, body.notes)
    out = ProjectPartyOut.model_validate(party)
    db.commit()
    return out


@router.delete("/{project_id}/parties/{party_id}", status_code=204)
def remove_party(project_id: uuid.UUID, party_id: uuid.UUID, db: DB, ctx: Ctx) -> Response:
    project = service.get_project(db, ctx, project_id)
    service.remove_party(db, ctx, project, party_id)
    db.commit()
    return Response(status_code=204)


# --- phases ---
@router.get("/{project_id}/phases", response_model=list[ProjectPhaseOut])
def list_phases(project_id: uuid.UUID, db: DB, ctx: Ctx) -> list[ProjectPhaseOut]:
    project = service.get_project(db, ctx, project_id)
    return [ProjectPhaseOut.model_validate(p) for p in service.list_phases(db, project)]


@router.post("/{project_id}/phases", response_model=ProjectPhaseOut, status_code=201)
def add_phase(project_id: uuid.UUID, body: ProjectPhaseIn, db: DB, ctx: Ctx) -> ProjectPhaseOut:
    project = service.get_project(db, ctx, project_id)
    phase = service.add_phase(db, ctx, project, body.model_dump())
    db.commit()
    return ProjectPhaseOut.model_validate(phase)


@router.put("/{project_id}/phases/{phase_id}", response_model=ProjectPhaseOut)
def update_phase(project_id: uuid.UUID, phase_id: uuid.UUID, body: ProjectPhaseIn, db: DB, ctx: Ctx) -> ProjectPhaseOut:
    project = service.get_project(db, ctx, project_id)
    phase = service.update_phase(db, ctx, project, service.get_phase(db, project, phase_id), body.model_dump())
    db.commit()
    return ProjectPhaseOut.model_validate(phase)


@router.delete("/{project_id}/phases/{phase_id}", status_code=204)
def delete_phase(project_id: uuid.UUID, phase_id: uuid.UUID, db: DB, ctx: Ctx) -> Response:
    project = service.get_project(db, ctx, project_id)
    service.delete_phase(db, ctx, project, service.get_phase(db, project, phase_id))
    db.commit()
    return Response(status_code=204)


# --- activity ---
@router.get("/{project_id}/activity", response_model=Page[AuditEventOut])
def project_activity(
    project_id: uuid.UUID, db: DB, ctx: Ctx,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AuditEventOut]:
    project = service.get_project(db, ctx, project_id)
    events, total = list_events(db, ctx.tenant_id, project_id=project.id, limit=limit, offset=offset)
    hide = not ctx.has(P.PROJECTS_FINANCIALS_VIEW)
    return Page(items=to_out(db, events, redact_financials=hide), total=total, limit=limit, offset=offset)
