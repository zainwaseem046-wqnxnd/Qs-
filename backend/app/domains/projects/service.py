"""Projects: lifecycle, visibility, team, parties and phases.

Visibility rule: users with ``projects.view_all`` see every project in the tenant; everyone else sees
only projects on which they are a project member. Invisible projects behave exactly like missing ones
(404), so project IDs cannot be probed.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import TenantContext
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.domains.audit import service as audit
from app.domains.companies.models import Address, Company
from app.domains.companies.schemas import AddressIn
from app.domains.companies.service import address_snapshot, apply_address
from app.domains.identity.models import User
from app.domains.projects.models import Project, ProjectMember, ProjectParty, ProjectPhase
from app.domains.tenancy.models import TenantMembership
from app.domains.tenancy.permissions import P

PROJECT_FIELDS = [
    "number", "name", "description", "status", "sector", "project_type", "delivery_method", "contract_type",
    "our_role", "client_company_id", "start_date", "planned_completion_date", "actual_completion_date",
    "original_contract_value", "currency", "is_public_works", "prevailing_wage", "retainage_percent",
    "reporting_period_end_day",
]
FINANCIAL_FIELDS = {"original_contract_value", "retainage_percent"}
NON_NULLABLE = {"number", "name", "status", "sector", "delivery_method", "contract_type", "our_role", "currency",
                "is_public_works", "prevailing_wage", "reporting_period_end_day"}

SORTS = {
    "name": func.lower(Project.name),
    "number": Project.number,
    "updated_at": Project.updated_at,
    "start_date": Project.start_date,
    "status": Project.status,
    "contract_value": Project.original_contract_value,
}


def visible_project_ids(ctx: TenantContext) -> Select[tuple[uuid.UUID]]:
    return select(ProjectMember.project_id).where(ProjectMember.user_id == ctx.user_id)


def _visible(stmt: Select[Any], ctx: TenantContext) -> Select[Any]:
    if ctx.has(P.PROJECTS_VIEW_ALL):
        return stmt
    return stmt.where(Project.id.in_(visible_project_ids(ctx)))


def list_projects(
    db: Session, ctx: TenantContext, *, q: str | None, status: str | None, sector: str | None,
    include_archived: bool, sort: str, order: str, limit: int, offset: int,
) -> tuple[list[Project], int]:
    stmt = _visible(select(Project), ctx)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Project.name.ilike(like), Project.number.ilike(like)))
    if status:
        stmt = stmt.where(Project.status == status)
    if sector:
        stmt = stmt.where(Project.sector == sector)
    if not include_archived:
        stmt = stmt.where(Project.archived_at.is_(None))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    sort_col = SORTS.get(sort, SORTS["updated_at"])
    if sort == "contract_value" and not ctx.has(P.PROJECTS_FINANCIALS_VIEW):
        sort_col = SORTS["updated_at"]  # do not leak hidden values through ordering
    ordered = sort_col.desc().nulls_last() if order == "desc" else sort_col.asc().nulls_last()
    rows = db.scalars(stmt.order_by(ordered, Project.id).limit(limit).offset(offset)).unique().all()
    return list(rows), total


def get_project(db: Session, ctx: TenantContext, project_id: uuid.UUID) -> Project:
    project = db.scalar(_visible(select(Project).where(Project.id == project_id), ctx))
    if project is None:
        raise NotFound("Project not found")
    return project


def can_edit(ctx: TenantContext, project: Project) -> bool:
    return ctx.has(P.PROJECTS_EDIT) and project.archived_at is None


def _assert_editable(ctx: TenantContext, project: Project) -> None:
    ctx.require(P.PROJECTS_EDIT)
    if project.archived_at is not None:
        raise Conflict("Archived projects are read-only. Restore the project to edit it.", code="project_archived")


def _validate_client(db: Session, company_id: uuid.UUID | None) -> None:
    if company_id is not None and db.get(Company, company_id) is None:
        raise ValidationFailed("Client company not found", details=[{"field": "client_company_id",
                                                                       "message": "Company not found"}])


def _number_taken(db: Session, number: str, exclude: uuid.UUID | None = None) -> bool:
    stmt = select(Project.id).where(func.lower(Project.number) == number.lower())
    if exclude:
        stmt = stmt.where(Project.id != exclude)
    return db.scalar(stmt) is not None


def create_project(db: Session, ctx: TenantContext, data: dict[str, Any], site_address: AddressIn | None) -> Project:
    if not ctx.has(P.PROJECTS_FINANCIALS_VIEW):
        for field in FINANCIAL_FIELDS:
            data.pop(field, None)
    _validate_client(db, data.get("client_company_id"))
    if _number_taken(db, data["number"]):
        raise Conflict(f"Project number {data['number']} is already in use", code="duplicate_number")
    data["currency"] = data.get("currency") or ctx.tenant.default_currency
    values = {k: v for k, v in data.items() if k in PROJECT_FIELDS and not (k in NON_NULLABLE and v is None)}
    project = Project(id=uuid.uuid4(), tenant_id=ctx.tenant_id, created_by_id=ctx.user_id, **values)
    project.site_address = apply_address(db, ctx, None, site_address, "site_address")
    db.add(project)
    try:
        db.flush()
    except IntegrityError as exc:  # race on the unique number
        raise Conflict(f"Project number {data['number']} is already in use", code="duplicate_number") from exc
    # The creator joins the project team so the project stays visible without projects.view_all.
    db.add(ProjectMember(tenant_id=ctx.tenant_id, project_id=project.id, user_id=ctx.user_id,
                         project_role="project_manager"))
    db.flush()
    audit.record(db, ctx.actor(), action="project.created", entity_type="project", entity_id=project.id,
                 project_id=project.id, summary=f"Project {project.number} '{project.name}' created",
                 changes={"created": audit.snapshot(project, [f for f in PROJECT_FIELDS
                                                              if ctx.has(P.PROJECTS_FINANCIALS_VIEW)
                                                              or f not in FINANCIAL_FIELDS])})
    return project


def update_project(
    db: Session, ctx: TenantContext, project: Project, version: int, data: dict[str, Any],
    site_address: AddressIn | None, address_provided: bool,
) -> Project:
    _assert_editable(ctx, project)
    if project.version != version:
        raise Conflict("This project was changed by someone else. Reload to see the latest version.",
                       code="version_conflict")
    if not ctx.has(P.PROJECTS_FINANCIALS_VIEW) and FINANCIAL_FIELDS & data.keys():
        raise ValidationFailed("You do not have permission to change commercial values")
    for key in NON_NULLABLE:
        if key in data and data[key] is None:
            data.pop(key)
    if "client_company_id" in data:
        _validate_client(db, data["client_company_id"])
    if data.get("number") and _number_taken(db, data["number"], exclude=project.id):
        raise Conflict(f"Project number {data['number']} is already in use", code="duplicate_number")

    fields = [f for f in PROJECT_FIELDS if f in data]
    before = audit.snapshot(project, fields)
    before_addr = address_snapshot(project.site_address)
    for key in fields:
        setattr(project, key, data[key])
    start, planned = project.start_date, project.planned_completion_date
    if start and planned and planned < start:
        raise ValidationFailed("Planned completion date must be on or after the start date")
    if address_provided:
        project.site_address = apply_address(db, ctx, project.site_address, site_address, "site_address")
    project.version += 1
    db.flush()
    changes = audit.diff(before, audit.snapshot(project, fields))
    after_addr = address_snapshot(project.site_address)
    if address_provided and before_addr != after_addr:
        changes["site_address"] = {"from": before_addr, "to": after_addr}
    if changes:
        audit.record(db, ctx.actor(), action="project.updated", entity_type="project", entity_id=project.id,
                     project_id=project.id, summary=f"Project {project.number} updated", changes=changes)
    return project


def set_archived(db: Session, ctx: TenantContext, project: Project, archived: bool) -> Project:
    ctx.require(P.PROJECTS_ARCHIVE)
    if archived == (project.archived_at is not None):
        raise Conflict("Project is already archived" if archived else "Project is not archived")
    project.archived_at = datetime.now(UTC) if archived else None
    project.version += 1
    db.flush()
    action = "project.archived" if archived else "project.restored"
    audit.record(db, ctx.actor(), action=action, entity_type="project", entity_id=project.id,
                 project_id=project.id, summary=f"Project {project.number} {'archived' if archived else 'restored'}")
    return project


# --- team ------------------------------------------------------------------------------------------
def list_members(db: Session, project: Project) -> list[tuple[ProjectMember, User]]:
    rows = db.execute(
        select(ProjectMember, User).join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project.id).order_by(User.full_name)
    ).all()
    return [(m, u) for m, u in rows]


def add_member(db: Session, ctx: TenantContext, project: Project, user_id: uuid.UUID, role: str) -> ProjectMember:
    ctx.require(P.PROJECTS_MEMBERS_MANAGE)
    _assert_editable_team(project)
    membership = db.scalar(select(TenantMembership).where(TenantMembership.user_id == user_id,
                                                          TenantMembership.status == "active"))
    if membership is None:
        raise ValidationFailed("User is not an active member of this organization")
    if db.scalar(select(ProjectMember).where(ProjectMember.project_id == project.id,
                                             ProjectMember.user_id == user_id)):
        raise Conflict("User is already on the project team")
    member = ProjectMember(id=uuid.uuid4(), tenant_id=ctx.tenant_id, project_id=project.id, user_id=user_id,
                           project_role=role)
    db.add(member)
    db.flush()
    user = db.get(User, user_id)
    audit.record(db, ctx.actor(), action="project.member_added", entity_type="project_member", entity_id=member.id,
                 project_id=project.id, summary=f"{user.full_name if user else user_id} added to team as {role}")
    return member


def _assert_editable_team(project: Project) -> None:
    if project.archived_at is not None:
        raise Conflict("Archived projects are read-only", code="project_archived")


def get_member(db: Session, project: Project, member_id: uuid.UUID) -> ProjectMember:
    member = db.get(ProjectMember, member_id)
    if member is None or member.project_id != project.id:
        raise NotFound("Team member not found")
    return member


def update_member(db: Session, ctx: TenantContext, project: Project, member: ProjectMember, role: str) -> None:
    ctx.require(P.PROJECTS_MEMBERS_MANAGE)
    _assert_editable_team(project)
    if member.project_role != role:
        audit.record(db, ctx.actor(), action="project.member_updated", entity_type="project_member",
                     entity_id=member.id, project_id=project.id, summary="Project role changed",
                     changes={"project_role": {"from": member.project_role, "to": role}})
        member.project_role = role
        db.flush()


def remove_member(db: Session, ctx: TenantContext, project: Project, member: ProjectMember) -> None:
    ctx.require(P.PROJECTS_MEMBERS_MANAGE)
    _assert_editable_team(project)
    audit.record(db, ctx.actor(), action="project.member_removed", entity_type="project_member",
                 entity_id=member.id, project_id=project.id, summary="Team member removed",
                 changes={"user_id": str(member.user_id), "project_role": member.project_role})
    db.delete(member)
    db.flush()


# --- parties ---------------------------------------------------------------------------------------
def list_parties(db: Session, project: Project) -> list[ProjectParty]:
    return list(db.scalars(select(ProjectParty).where(ProjectParty.project_id == project.id)
                           .order_by(ProjectParty.party_role)).unique())


def add_party(db: Session, ctx: TenantContext, project: Project, company_id: uuid.UUID, role: str,
              notes: str | None) -> ProjectParty:
    _assert_editable(ctx, project)
    company = db.get(Company, company_id)
    if company is None:
        raise ValidationFailed("Company not found")
    if db.scalar(select(ProjectParty).where(ProjectParty.project_id == project.id,
                                            ProjectParty.company_id == company_id, ProjectParty.party_role == role)):
        raise Conflict("This company already has that role on the project")
    party = ProjectParty(id=uuid.uuid4(), tenant_id=ctx.tenant_id, project_id=project.id, company_id=company_id,
                         party_role=role, notes=notes)
    db.add(party)
    db.flush()
    audit.record(db, ctx.actor(), action="project.party_added", entity_type="project_party", entity_id=party.id,
                 project_id=project.id, summary=f"{company.name} added as {role}")
    return party


def remove_party(db: Session, ctx: TenantContext, project: Project, party_id: uuid.UUID) -> None:
    _assert_editable(ctx, project)
    party = db.get(ProjectParty, party_id)
    if party is None or party.project_id != project.id:
        raise NotFound("Project party not found")
    audit.record(db, ctx.actor(), action="project.party_removed", entity_type="project_party", entity_id=party.id,
                 project_id=project.id, summary=f"{party.company.name} removed as {party.party_role}")
    db.delete(party)
    db.flush()


# --- phases ----------------------------------------------------------------------------------------
def list_phases(db: Session, project: Project) -> list[ProjectPhase]:
    return list(db.scalars(select(ProjectPhase).where(ProjectPhase.project_id == project.id)
                           .order_by(ProjectPhase.sequence)))


def add_phase(db: Session, ctx: TenantContext, project: Project, data: dict[str, Any]) -> ProjectPhase:
    _assert_editable(ctx, project)
    next_seq = (db.scalar(select(func.max(ProjectPhase.sequence)).where(ProjectPhase.project_id == project.id))
                or 0) + 1
    phase = ProjectPhase(id=uuid.uuid4(), tenant_id=ctx.tenant_id, project_id=project.id, sequence=next_seq, **data)
    db.add(phase)
    db.flush()
    audit.record(db, ctx.actor(), action="project.phase_added", entity_type="project_phase", entity_id=phase.id,
                 project_id=project.id, summary=f"Phase '{phase.name}' added")
    return phase


def get_phase(db: Session, project: Project, phase_id: uuid.UUID) -> ProjectPhase:
    phase = db.get(ProjectPhase, phase_id)
    if phase is None or phase.project_id != project.id:
        raise NotFound("Phase not found")
    return phase


def update_phase(db: Session, ctx: TenantContext, project: Project, phase: ProjectPhase,
                 data: dict[str, Any]) -> ProjectPhase:
    _assert_editable(ctx, project)
    fields = list(data)
    before = audit.snapshot(phase, fields)
    for k, v in data.items():
        setattr(phase, k, v)
    db.flush()
    changes = audit.diff(before, audit.snapshot(phase, fields))
    if changes:
        audit.record(db, ctx.actor(), action="project.phase_updated", entity_type="project_phase",
                     entity_id=phase.id, project_id=project.id, summary=f"Phase '{phase.name}' updated",
                     changes=changes)
    return phase


def delete_phase(db: Session, ctx: TenantContext, project: Project, phase: ProjectPhase) -> None:
    _assert_editable(ctx, project)
    audit.record(db, ctx.actor(), action="project.phase_deleted", entity_type="project_phase", entity_id=phase.id,
                 project_id=project.id, summary=f"Phase '{phase.name}' deleted")
    db.delete(phase)
    db.flush()


def address_city_state(address: Address | None) -> tuple[str | None, str | None]:
    return (address.city, address.state_code) if address else (None, None)
