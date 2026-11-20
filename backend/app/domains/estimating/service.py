"""Estimates: versions, priced lines, markups, issue/approve workflow, version comparison.

Workflow: a version starts as ``draft`` (editable) -> ``issued`` (frozen, totals snapshotted) -> ``approved``.
Only one draft exists at a time; a new version copies the latest version. Frozen versions are protected
by database triggers as well as by these checks.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import TenantContext
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.domains.audit import service as audit
from app.domains.cost_codes.models import CostCode, CostCodeSet
from app.domains.estimating.calc import LineResult, PricedLine, VersionTotals, calculate_line, version_totals
from app.domains.estimating.models import Estimate, EstimateLine, EstimateMarkup, EstimateVersion
from app.domains.projects.models import Project
from app.domains.projects.service import get_project, visible_project_ids
from app.domains.tenancy.permissions import P

LINE_FIELDS = [
    "cost_code_id",
    "line_type",
    "inclusion",
    "alternate_label",
    "description",
    "quantity",
    "unit",
    "labour_hours_per_unit",
    "labour_rate",
    "material_rate",
    "material_waste_percent",
    "equipment_rate",
    "subcontract_rate",
    "other_rate",
    "notes",
]


def _now() -> datetime:
    return datetime.now(UTC)


# --- estimates ----------------------------------------------------------------------------------------
def list_estimates(db: Session, ctx: TenantContext, project_id: uuid.UUID | None) -> list[tuple[Estimate, Project]]:
    ctx.require(P.ESTIMATES_VIEW)
    stmt = (
        select(Estimate, Project).join(Project, Project.id == Estimate.project_id).where(Estimate.archived_at.is_(None))
    )
    if project_id:
        get_project(db, ctx, project_id)
        stmt = stmt.where(Estimate.project_id == project_id)
    if not ctx.has(P.PROJECTS_VIEW_ALL):
        stmt = stmt.where(Estimate.project_id.in_(visible_project_ids(ctx)))
    rows = db.execute(stmt.order_by(Estimate.updated_at.desc())).unique().all()
    return [(e, p) for e, p in rows]


def get_estimate(db: Session, ctx: TenantContext, estimate_id: uuid.UUID) -> tuple[Estimate, Project]:
    ctx.require(P.ESTIMATES_VIEW)
    estimate = db.get(Estimate, estimate_id)
    if estimate is None:
        raise NotFound("Estimate not found")
    project = get_project(db, ctx, estimate.project_id)  # enforces project visibility (404 otherwise)
    return estimate, project


def can_edit(ctx: TenantContext, project: Project) -> bool:
    return ctx.has(P.ESTIMATES_EDIT) and project.archived_at is None


def _assert_editable(ctx: TenantContext, project: Project) -> None:
    ctx.require(P.ESTIMATES_EDIT)
    if project.archived_at is not None:
        raise Conflict("Archived projects are read-only", code="project_archived")


def create_estimate(db: Session, ctx: TenantContext, project: Project, data: dict[str, Any]) -> Estimate:
    _assert_editable(ctx, project)
    if data.get("cost_code_set_id"):
        code_set = db.get(CostCodeSet, data["cost_code_set_id"])
        if code_set is None or not code_set.is_active:
            raise ValidationFailed("Cost code structure not found or inactive")
    estimate = Estimate(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        project_id=project.id,
        name=data["name"].strip(),
        estimate_type=data["estimate_type"],
        cost_code_set_id=data.get("cost_code_set_id"),
        currency=data.get("currency") or project.currency,
        created_by_id=ctx.user_id,
    )
    db.add(estimate)
    db.flush()
    db.add(
        EstimateVersion(
            id=uuid.uuid4(),
            tenant_id=ctx.tenant_id,
            estimate_id=estimate.id,
            version_number=1,
            label=data.get("label"),
            price_base_date=data.get("price_base_date"),
        )
    )
    db.flush()
    audit.record(
        db,
        ctx.actor(),
        action="estimate.created",
        entity_type="estimate",
        entity_id=estimate.id,
        project_id=project.id,
        summary=f"Estimate '{estimate.name}' created",
    )
    return estimate


def rename_estimate(db: Session, ctx: TenantContext, estimate: Estimate, project: Project, name: str) -> Estimate:
    _assert_editable(ctx, project)
    if estimate.name != name:
        audit.record(
            db,
            ctx.actor(),
            action="estimate.renamed",
            entity_type="estimate",
            entity_id=estimate.id,
            project_id=project.id,
            summary="Estimate renamed",
            changes={"name": {"from": estimate.name, "to": name}},
        )
        estimate.name = name
        db.flush()
    return estimate


def versions(db: Session, estimate: Estimate) -> list[EstimateVersion]:
    return list(
        db.scalars(
            select(EstimateVersion)
            .where(EstimateVersion.estimate_id == estimate.id)
            .order_by(EstimateVersion.version_number)
        )
    )


def get_version(db: Session, estimate: Estimate, number: int) -> EstimateVersion:
    version = db.scalar(
        select(EstimateVersion).where(
            EstimateVersion.estimate_id == estimate.id, EstimateVersion.version_number == number
        )
    )
    if version is None:
        raise NotFound("Estimate version not found")
    return version


# --- pricing ------------------------------------------------------------------------------------------
@dataclass
class PricedVersion:
    version: EstimateVersion
    lines: list[tuple[EstimateLine, LineResult, CostCode | None]]
    markups: list[EstimateMarkup]
    totals: VersionTotals


def price_version(db: Session, version: EstimateVersion) -> PricedVersion:
    rows = db.execute(
        select(EstimateLine, CostCode)
        .outerjoin(CostCode, CostCode.id == EstimateLine.cost_code_id)
        .where(EstimateLine.version_id == version.id)
        .order_by(EstimateLine.sequence)
    ).all()
    lines = [(line, calculate_line(line), code) for line, code in rows]
    markups = list(
        db.scalars(
            select(EstimateMarkup).where(EstimateMarkup.version_id == version.id).order_by(EstimateMarkup.sequence)
        )
    )
    totals = version_totals([PricedLine(ln.inclusion, ln.alternate_label, r) for ln, r, _ in lines], markups)
    return PricedVersion(version, lines, markups, totals)


# --- editing --------------------------------------------------------------------------------------------
def _assert_draft(version: EstimateVersion) -> None:
    if version.status != "draft":
        raise Conflict(
            f"Version {version.version_number} is {version.status} and cannot be changed. "
            "Create a new version to make changes.",
            code="version_locked",
        )


def _check_cost_code(db: Session, estimate: Estimate, cost_code_id: uuid.UUID | None) -> None:
    if cost_code_id is None:
        return
    code = db.get(CostCode, cost_code_id)
    if code is None or not code.is_active or (estimate.cost_code_set_id and code.set_id != estimate.cost_code_set_id):
        raise ValidationFailed(
            "Invalid input",
            details=[
                {"field": "cost_code_id", "message": "Cost code not found in this estimate's cost code structure"}
            ],
        )


def _touch(version: EstimateVersion) -> None:
    version.revision += 1


def add_line(
    db: Session,
    ctx: TenantContext,
    estimate: Estimate,
    project: Project,
    version: EstimateVersion,
    data: dict[str, Any],
) -> EstimateLine:
    _assert_editable(ctx, project)
    _assert_draft(version)
    _check_cost_code(db, estimate, data.get("cost_code_id"))
    seq = (db.scalar(select(func.max(EstimateLine.sequence)).where(EstimateLine.version_id == version.id)) or 0) + 10
    line = EstimateLine(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        version_id=version.id,
        sequence=seq,
        **{k: data[k] for k in LINE_FIELDS if k in data},
    )
    db.add(line)
    _touch(version)
    db.flush()
    audit.record(
        db,
        ctx.actor(),
        action="estimate.line_added",
        entity_type="estimate",
        entity_id=estimate.id,
        project_id=project.id,
        summary=f"Line added to v{version.version_number}: {line.description[:120]}",
        changes={"line": audit.snapshot(line, LINE_FIELDS)},
    )
    return line


def get_line(db: Session, version: EstimateVersion, line_id: uuid.UUID) -> EstimateLine:
    line = db.get(EstimateLine, line_id)
    if line is None or line.version_id != version.id:
        raise NotFound("Estimate line not found")
    return line


def update_line(
    db: Session,
    ctx: TenantContext,
    estimate: Estimate,
    project: Project,
    version: EstimateVersion,
    line: EstimateLine,
    data: dict[str, Any],
) -> EstimateLine:
    _assert_editable(ctx, project)
    _assert_draft(version)
    _check_cost_code(db, estimate, data.get("cost_code_id"))
    before = audit.snapshot(line, LINE_FIELDS)
    for k in LINE_FIELDS:
        if k in data:
            setattr(line, k, data[k])
    _touch(version)
    db.flush()
    changes = audit.diff(before, audit.snapshot(line, LINE_FIELDS))
    if changes:
        audit.record(
            db,
            ctx.actor(),
            action="estimate.line_updated",
            entity_type="estimate",
            entity_id=estimate.id,
            project_id=project.id,
            summary=f"Line updated in v{version.version_number}: {line.description[:120]}",
            changes=changes,
        )
    return line


def delete_line(
    db: Session, ctx: TenantContext, estimate: Estimate, project: Project, version: EstimateVersion, line: EstimateLine
) -> None:
    _assert_editable(ctx, project)
    _assert_draft(version)
    audit.record(
        db,
        ctx.actor(),
        action="estimate.line_deleted",
        entity_type="estimate",
        entity_id=estimate.id,
        project_id=project.id,
        summary=f"Line deleted from v{version.version_number}: {line.description[:120]}",
        changes={"deleted": audit.snapshot(line, LINE_FIELDS)},
    )
    db.delete(line)
    _touch(version)
    db.flush()


def set_markups(
    db: Session,
    ctx: TenantContext,
    estimate: Estimate,
    project: Project,
    version: EstimateVersion,
    markups: list[dict[str, Any]],
) -> None:
    _assert_editable(ctx, project)
    _assert_draft(version)
    existing = list(db.scalars(select(EstimateMarkup).where(EstimateMarkup.version_id == version.id)))
    before = [
        {"name": m.name, "percent": m.percent, "basis": m.basis} for m in sorted(existing, key=lambda m: m.sequence)
    ]
    for m in existing:
        db.delete(m)
    db.flush()
    for i, m in enumerate(markups, start=1):
        db.add(EstimateMarkup(id=uuid.uuid4(), tenant_id=ctx.tenant_id, version_id=version.id, sequence=i, **m))
    _touch(version)
    db.flush()
    after = [{"name": m["name"], "percent": m["percent"], "basis": m["basis"]} for m in markups]
    audit.record(
        db,
        ctx.actor(),
        action="estimate.markups_updated",
        entity_type="estimate",
        entity_id=estimate.id,
        project_id=project.id,
        summary=f"Markups updated on v{version.version_number}",
        changes={"markups": {"from": audit._json_safe(before), "to": audit._json_safe(after)}},
    )


def update_version(
    db: Session,
    ctx: TenantContext,
    estimate: Estimate,
    project: Project,
    version: EstimateVersion,
    data: dict[str, Any],
) -> EstimateVersion:
    _assert_editable(ctx, project)
    _assert_draft(version)
    fields = [f for f in ("label", "notes", "price_base_date") if f in data]
    before = audit.snapshot(version, fields)
    for f in fields:
        setattr(version, f, data[f])
    db.flush()
    changes = audit.diff(before, audit.snapshot(version, fields))
    if changes:
        audit.record(
            db,
            ctx.actor(),
            action="estimate.version_updated",
            entity_type="estimate",
            entity_id=estimate.id,
            project_id=project.id,
            summary=f"Version {version.version_number} details updated",
            changes=changes,
        )
    return version


# --- workflow ---------------------------------------------------------------------------------------------
def issue_version(
    db: Session, ctx: TenantContext, estimate: Estimate, project: Project, version: EstimateVersion
) -> EstimateVersion:
    _assert_editable(ctx, project)
    _assert_draft(version)
    priced = price_version(db, version)
    if not priced.lines:
        raise ValidationFailed("Add at least one line before issuing this version")
    t = priced.totals
    version.direct_cost, version.markup_total, version.total = t.direct_cost, t.markup_total, t.total
    version.status = "issued"
    version.issued_at = _now()
    version.issued_by_id = ctx.user_id
    db.flush()
    audit.record(
        db,
        ctx.actor(),
        action="estimate.version_issued",
        entity_type="estimate",
        entity_id=estimate.id,
        project_id=project.id,
        summary=f"Version {version.version_number} issued",
        changes={"direct_cost": t.direct_cost, "markup_total": t.markup_total, "total": t.total},
    )
    return version


def approve_version(
    db: Session, ctx: TenantContext, estimate: Estimate, project: Project, version: EstimateVersion
) -> EstimateVersion:
    ctx.require(P.ESTIMATES_APPROVE)
    if project.archived_at is not None:
        raise Conflict("Archived projects are read-only", code="project_archived")
    if version.status != "issued":
        raise Conflict("Only issued versions can be approved", code="invalid_status")
    version.status = "approved"
    version.approved_at = _now()
    version.approved_by_id = ctx.user_id
    db.flush()
    audit.record(
        db,
        ctx.actor(),
        action="estimate.version_approved",
        entity_type="estimate",
        entity_id=estimate.id,
        project_id=project.id,
        summary=f"Version {version.version_number} approved",
        changes={"total": version.total},
    )
    return version


def new_version(db: Session, ctx: TenantContext, estimate: Estimate, project: Project) -> EstimateVersion:
    _assert_editable(ctx, project)
    latest = get_version(db, estimate, estimate.current_version_number)
    if latest.status == "draft":
        raise Conflict(
            f"Version {latest.version_number} is still a draft. Issue it before starting a new version.",
            code="draft_exists",
        )
    number = latest.version_number + 1
    copy = EstimateVersion(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        estimate_id=estimate.id,
        version_number=number,
        price_base_date=latest.price_base_date,
        label=None,
    )
    db.add(copy)
    db.flush()
    for line in db.scalars(select(EstimateLine).where(EstimateLine.version_id == latest.id)):
        db.add(
            EstimateLine(
                id=uuid.uuid4(),
                tenant_id=ctx.tenant_id,
                version_id=copy.id,
                sequence=line.sequence,
                **{k: getattr(line, k) for k in LINE_FIELDS},
            )
        )
    for m in db.scalars(select(EstimateMarkup).where(EstimateMarkup.version_id == latest.id)):
        db.add(
            EstimateMarkup(
                id=uuid.uuid4(),
                tenant_id=ctx.tenant_id,
                version_id=copy.id,
                sequence=m.sequence,
                name=m.name,
                percent=m.percent,
                basis=m.basis,
                include_in_budget=m.include_in_budget,
            )
        )
    estimate.current_version_number = number
    db.flush()
    audit.record(
        db,
        ctx.actor(),
        action="estimate.version_created",
        entity_type="estimate",
        entity_id=estimate.id,
        project_id=project.id,
        summary=f"Version {number} created from version {latest.version_number}",
    )
    return copy


# --- comparison -------------------------------------------------------------------------------------------
def compare(db: Session, estimate: Estimate, a: int, b: int) -> tuple[list[dict[str, Any]], Decimal, Decimal]:
    """Base-scope direct cost by cost code between two versions, plus each version's total."""

    def by_code(version: EstimateVersion) -> tuple[dict[tuple[str | None, str], Decimal], Decimal]:
        priced = price_version(db, version)
        out: dict[tuple[str | None, str], Decimal] = {}
        for line, result, code in priced.lines:
            if line.inclusion != "base":
                continue
            key = (code.code, code.title) if code else (None, "Unassigned (no cost code)")
            out[key] = out.get(key, Decimal(0)) + result.total
        for m in priced.totals.markups:
            key = (None, f"Markup: {m.name}")
            out[key] = out.get(key, Decimal(0)) + m.amount
        return out, priced.totals.total

    va, ta = by_code(get_version(db, estimate, a))
    vb, tb = by_code(get_version(db, estimate, b))
    keys = sorted(set(va) | set(vb), key=lambda k: (k[0] is None, k[0] or "", k[1]))
    rows = [
        {
            "cost_code": k[0],
            "title": k[1],
            "from_amount": va.get(k, Decimal("0.00")),
            "to_amount": vb.get(k, Decimal("0.00")),
            "change": vb.get(k, Decimal(0)) - va.get(k, Decimal(0)),
        }
        for k in keys
    ]
    return rows, ta, tb
