"""Change orders / variations / compensation events.

Signed contracts and approved budgets are never edited. Revised figures are derived:
    revised contract sum   = original sum + approved client-side change amounts
    revised commitment     = original value + approved commitment change amounts
    budget adjustments     = approved client-side change lines' budget_amount, by cost code
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import TenantContext
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.money import extend
from app.domains.audit import service as audit
from app.domains.change_orders.constants import change_label, commitment_change_label
from app.domains.change_orders.models import ChangeOrder, ChangeOrderLine
from app.domains.companies.models import Company
from app.domains.contracts.models import Commitment, Contract
from app.domains.cost_codes.models import CostCode
from app.domains.projects.models import Project
from app.domains.projects.service import get_project, visible_project_ids
from app.domains.tenancy.permissions import P

ZERO = Decimal("0.00")
FIELDS = ["title", "description", "reason", "reference", "schedule_impact_days", "notified_date", "response_due_date"]
PENDING = ("draft", "submitted")


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Target:
    type: str
    obj: Contract | Commitment

    @property
    def counterparty_id(self) -> uuid.UUID | None:
        return self.obj.client_company_id if isinstance(self.obj, Contract) else self.obj.vendor_company_id


def target_of(db: Session, co: ChangeOrder) -> Target:
    if co.contract_id:
        return Target("contract", db.get(Contract, co.contract_id))  # type: ignore[arg-type]
    return Target("commitment", db.get(Commitment, co.commitment_id))  # type: ignore[arg-type]


def label_for(ctx: TenantContext, target: Target) -> tuple[str, str]:
    fn = change_label if target.type == "contract" else commitment_change_label
    return fn(ctx.tenant.country_code, target.obj.contract_form)


def counterparty_name(db: Session, target: Target) -> str | None:
    cid = target.counterparty_id
    company = db.get(Company, cid) if cid else None
    return company.name if company else None


def is_overdue(co: ChangeOrder) -> bool:
    return co.status in PENDING and co.response_due_date is not None and co.response_due_date < date.today()


# --- reads -----------------------------------------------------------------------------------------------------
def list_change_orders(
    db: Session,
    ctx: TenantContext,
    *,
    project_id: uuid.UUID | None = None,
    contract_id: uuid.UUID | None = None,
    commitment_id: uuid.UUID | None = None,
    status: str | None = None,
) -> list[tuple[ChangeOrder, Project]]:
    ctx.require(P.CHANGES_VIEW)
    stmt = select(ChangeOrder, Project).join(Project, Project.id == ChangeOrder.project_id)
    if project_id:
        get_project(db, ctx, project_id)
        stmt = stmt.where(ChangeOrder.project_id == project_id)
    if contract_id:
        stmt = stmt.where(ChangeOrder.contract_id == contract_id)
    if commitment_id:
        stmt = stmt.where(ChangeOrder.commitment_id == commitment_id)
    if status:
        stmt = stmt.where(ChangeOrder.status == status)
    if not ctx.has(P.PROJECTS_VIEW_ALL):
        stmt = stmt.where(ChangeOrder.project_id.in_(visible_project_ids(ctx)))
    rows = db.execute(stmt.order_by(Project.number, ChangeOrder.created_at)).unique().all()
    return [(co, p) for co, p in rows]


def get_change_order(db: Session, ctx: TenantContext, co_id: uuid.UUID) -> tuple[ChangeOrder, Project]:
    ctx.require(P.CHANGES_VIEW)
    co = db.get(ChangeOrder, co_id)
    if co is None:
        raise NotFound("Change order not found")
    return co, get_project(db, ctx, co.project_id)


def lines(db: Session, co: ChangeOrder) -> list[tuple[ChangeOrderLine, CostCode | None]]:
    rows = db.execute(
        select(ChangeOrderLine, CostCode)
        .outerjoin(CostCode, CostCode.id == ChangeOrderLine.cost_code_id)
        .where(ChangeOrderLine.change_order_id == co.id)
        .order_by(ChangeOrderLine.sequence)
    ).all()
    return [(ln, code) for ln, code in rows]


def totals(db: Session, co: ChangeOrder) -> tuple[Decimal, Decimal]:
    amount, budget = db.execute(
        select(
            func.coalesce(func.sum(ChangeOrderLine.amount), 0),
            func.coalesce(func.sum(ChangeOrderLine.budget_amount), 0),
        ).where(ChangeOrderLine.change_order_id == co.id)
    ).one()
    return Decimal(amount).quantize(Decimal("0.01")), Decimal(budget).quantize(Decimal("0.01"))


def is_editable(ctx: TenantContext, co: ChangeOrder, project: Project) -> bool:
    return co.status == "draft" and ctx.has(P.CHANGES_EDIT) and project.archived_at is None


def change_totals(
    db: Session, *, contract_id: uuid.UUID | None = None, commitment_id: uuid.UUID | None = None
) -> dict[str, Any]:
    """Approved and pending (draft + submitted) change totals for one contract or commitment."""
    col = ChangeOrder.contract_id if contract_id else ChangeOrder.commitment_id
    target = contract_id or commitment_id
    amount = func.coalesce(
        select(func.sum(ChangeOrderLine.amount))
        .where(ChangeOrderLine.change_order_id == ChangeOrder.id)
        .correlate(ChangeOrder)
        .scalar_subquery(),
        0,
    )
    row = db.execute(
        select(
            func.coalesce(func.sum(case((ChangeOrder.status == "approved", amount), else_=0)), 0),
            func.coalesce(func.sum(case((ChangeOrder.status.in_(PENDING), amount), else_=0)), 0),
            func.count().filter(ChangeOrder.status == "approved"),
            func.count().filter(ChangeOrder.status.in_(PENDING)),
        ).where(col == target)
    ).one()
    q = Decimal("0.01")
    return {
        "approved": Decimal(row[0]).quantize(q),
        "pending": Decimal(row[1]).quantize(q),
        "approved_count": int(row[2]),
        "pending_count": int(row[3]),
    }


# --- create / edit ---------------------------------------------------------------------------------------------
def _assert_editable(ctx: TenantContext, project: Project, co: ChangeOrder | None = None) -> None:
    ctx.require(P.CHANGES_EDIT)
    if project.archived_at is not None:
        raise Conflict("Archived projects are read-only", code="project_archived")
    if co is not None and co.status != "draft":
        raise Conflict(
            f"{co.number} is {co.status}. Only drafts can be changed"
            + (" — return it to draft first." if co.status == "submitted" else "."),
            code="change_locked",
        )


def _check_version(co: ChangeOrder, version: int) -> None:
    if co.version != version:
        raise Conflict("This change order was changed by someone else. Reload and try again.", code="version_conflict")


def _next_number(db: Session, project_id: uuid.UUID, prefix: str) -> str:
    existing = db.scalars(
        select(ChangeOrder.number).where(ChangeOrder.project_id == project_id, ChangeOrder.number.like(f"{prefix}-%"))
    ).all()
    used = [int(m.group(1)) for n in existing if (m := re.fullmatch(rf"{re.escape(prefix)}-(\d+)", n))]
    return f"{prefix}-{(max(used) if used else 0) + 1:03d}"


def create(db: Session, ctx: TenantContext, data: dict[str, Any]) -> tuple[ChangeOrder, Project]:
    model = Contract if data["target_type"] == "contract" else Commitment
    if data["target_type"] == "contract":
        ctx.require(P.CONTRACTS_VIEW)
    else:
        ctx.require(P.COMMITMENTS_VIEW)
    obj = db.get(model, data["target_id"])
    if obj is None:
        raise ValidationFailed("Invalid input", details=[{"field": "target_id", "message": "Contract not found"}])
    project = get_project(db, ctx, obj.project_id)
    _assert_editable(ctx, project)
    if obj.status != "executed":
        raise Conflict(
            "Change orders can only be raised against executed (signed) contracts that are not closed",
            code="target_not_executed",
        )
    target = Target(data["target_type"], obj)
    _, prefix = label_for(ctx, target)
    number = data.get("number") or _next_number(db, project.id, prefix)
    if db.scalar(
        select(ChangeOrder.id).where(
            ChangeOrder.project_id == project.id, func.lower(ChangeOrder.number) == number.lower()
        )
    ):
        raise Conflict(f"Number {number} is already used on this project", code="duplicate_number")
    co = ChangeOrder(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        project_id=project.id,
        number=number,
        contract_id=obj.id if target.type == "contract" else None,
        commitment_id=obj.id if target.type == "commitment" else None,
        created_by_id=ctx.user_id,
        **{k: data[k] for k in FIELDS if data.get(k) is not None},
    )
    db.add(co)
    try:
        db.flush()
    except IntegrityError as exc:
        raise Conflict(f"Number {number} is already used on this project", code="duplicate_number") from exc
    label, _ = label_for(ctx, target)
    audit.record(
        db,
        ctx.actor(),
        action="change_order.created",
        entity_type="change_order",
        entity_id=co.id,
        project_id=project.id,
        summary=f"{label} {co.number} '{co.title}' raised against {obj.number}",
    )
    return co, project


def update(
    db: Session, ctx: TenantContext, project: Project, co: ChangeOrder, version: int, data: dict[str, Any]
) -> ChangeOrder:
    _assert_editable(ctx, project, co)
    _check_version(co, version)
    for required in ("title", "reason"):
        if required in data and data[required] is None:
            data.pop(required)
    fields = [f for f in FIELDS if f in data]
    before = audit.snapshot(co, fields)
    for f in fields:
        setattr(co, f, data[f])
    if co.notified_date and co.response_due_date and co.response_due_date < co.notified_date:
        raise ValidationFailed("Response due date must be on or after the notified date")
    co.version += 1
    db.flush()
    changes = audit.diff(before, audit.snapshot(co, fields))
    if changes:
        audit.record(
            db,
            ctx.actor(),
            action="change_order.updated",
            entity_type="change_order",
            entity_id=co.id,
            project_id=project.id,
            summary=f"{co.number} details updated",
            changes=changes,
        )
    return co


def _line_values(db: Session, co: ChangeOrder, data: dict[str, Any]) -> dict[str, Any]:
    target = target_of(db, co)
    if data.get("cost_code_id"):
        code = db.get(CostCode, data["cost_code_id"])
        if (
            code is None
            or not code.is_active
            or (target.obj.cost_code_set_id and code.set_id != target.obj.cost_code_set_id)
        ):
            raise ValidationFailed(
                "Invalid input",
                details=[
                    {"field": "cost_code_id", "message": "Cost code not found in the contract's cost code structure"}
                ],
            )
    if target.type == "commitment" and data.get("budget_amount") is not None:
        raise ValidationFailed(
            "Invalid input",
            details=[
                {"field": "budget_amount", "message": "Budget adjustments are recorded on client-side changes only"}
            ],
        )
    qty, rate = data.get("quantity"), data.get("unit_rate")
    amount = extend(qty, rate) if qty is not None and rate is not None else data["amount"]
    return {
        "cost_code_id": data.get("cost_code_id"),
        "description": data["description"].strip(),
        "quantity": qty,
        "unit": data.get("unit") or None,
        "unit_rate": rate,
        "amount": amount,
        "budget_amount": data.get("budget_amount"),
    }


def add_line(db: Session, ctx: TenantContext, project: Project, co: ChangeOrder, data: dict[str, Any]) -> None:
    _assert_editable(ctx, project, co)
    values = _line_values(db, co, data)
    seq = (
        db.scalar(select(func.max(ChangeOrderLine.sequence)).where(ChangeOrderLine.change_order_id == co.id)) or 0
    ) + 10
    db.add(ChangeOrderLine(id=uuid.uuid4(), tenant_id=ctx.tenant_id, change_order_id=co.id, sequence=seq, **values))
    co.version += 1
    db.flush()
    audit.record(
        db,
        ctx.actor(),
        action="change_order.line_added",
        entity_type="change_order",
        entity_id=co.id,
        project_id=project.id,
        summary=f"Line added to {co.number}: {values['description']}",
        changes={"amount": values["amount"], "budget_amount": values["budget_amount"]},
    )


def get_line(db: Session, co: ChangeOrder, line_id: uuid.UUID) -> ChangeOrderLine:
    line = db.get(ChangeOrderLine, line_id)
    if line is None or line.change_order_id != co.id:
        raise NotFound("Line not found")
    return line


def update_line(
    db: Session, ctx: TenantContext, project: Project, co: ChangeOrder, line: ChangeOrderLine, data: dict[str, Any]
) -> None:
    _assert_editable(ctx, project, co)
    values = _line_values(db, co, data)
    before = audit.snapshot(line, list(values))
    for k, v in values.items():
        setattr(line, k, v)
    co.version += 1
    db.flush()
    changes = audit.diff(before, audit.snapshot(line, list(values)))
    if changes:
        audit.record(
            db,
            ctx.actor(),
            action="change_order.line_updated",
            entity_type="change_order",
            entity_id=co.id,
            project_id=project.id,
            summary=f"Line updated on {co.number}: {line.description}",
            changes=changes,
        )


def delete_line(db: Session, ctx: TenantContext, project: Project, co: ChangeOrder, line: ChangeOrderLine) -> None:
    _assert_editable(ctx, project, co)
    audit.record(
        db,
        ctx.actor(),
        action="change_order.line_deleted",
        entity_type="change_order",
        entity_id=co.id,
        project_id=project.id,
        summary=f"Line deleted from {co.number}: {line.description}",
        changes={"amount": line.amount},
    )
    db.delete(line)
    co.version += 1
    db.flush()


def delete_draft(db: Session, ctx: TenantContext, project: Project, co: ChangeOrder) -> None:
    _assert_editable(ctx, project, co)
    audit.record(
        db,
        ctx.actor(),
        action="change_order.deleted",
        entity_type="change_order",
        entity_id=co.id,
        project_id=project.id,
        summary=f"Draft {co.number} deleted",
    )
    db.delete(co)
    db.flush()


# --- workflow -----------------------------------------------------------------------------------------------------
def _transition(
    db: Session,
    ctx: TenantContext,
    project: Project,
    co: ChangeOrder,
    version: int,
    *,
    allowed_from: tuple[str, ...],
    to: str,
    permission: str,
    notes: str | None = None,
) -> ChangeOrder:
    ctx.require(permission)
    if project.archived_at is not None:
        raise Conflict("Archived projects are read-only", code="project_archived")
    _check_version(co, version)
    if co.status not in allowed_from:
        raise Conflict(f"Cannot move {co.number} from {co.status} to {to}", code="invalid_status")
    target = target_of(db, co)
    if to in ("submitted", "approved") and target.obj.status != "executed":
        raise Conflict(
            f"{target.obj.number} is {target.obj.status}; changes can only be agreed on an executed contract",
            code="target_not_executed",
        )
    amount, budget = totals(db, co)
    if to == "submitted" and not lines(db, co):
        raise ValidationFailed("Add at least one priced line before submitting")
    before = co.status
    co.status = to
    if to == "submitted":
        co.submitted_at = _now()
    if to in ("approved", "rejected"):
        co.decided_at = _now()
        co.decided_by_id = ctx.user_id
        co.decision_notes = notes
    if to == "approved":
        co.approved_amount = amount
        co.approved_budget_amount = budget if target.type == "contract" else None
    co.version += 1
    db.flush()
    label, _ = label_for(ctx, target)
    audit.record(
        db,
        ctx.actor(),
        action=f"change_order.{to}",
        entity_type="change_order",
        entity_id=co.id,
        project_id=project.id,
        summary=f"{label} {co.number} {to.replace('_', ' ')}" + (f" ({amount})" if to == "approved" else ""),
        changes={"status": {"from": before, "to": to}, "amount": amount, **({"notes": notes} if notes else {})},
    )
    return co


def submit(db: Session, ctx: TenantContext, project: Project, co: ChangeOrder, version: int) -> ChangeOrder:
    return _transition(
        db, ctx, project, co, version, allowed_from=("draft",), to="submitted", permission=P.CHANGES_EDIT
    )


def return_to_draft(db: Session, ctx: TenantContext, project: Project, co: ChangeOrder, version: int) -> ChangeOrder:
    return _transition(
        db, ctx, project, co, version, allowed_from=("submitted",), to="draft", permission=P.CHANGES_EDIT
    )


def approve(
    db: Session, ctx: TenantContext, project: Project, co: ChangeOrder, version: int, notes: str | None
) -> ChangeOrder:
    return _transition(
        db,
        ctx,
        project,
        co,
        version,
        allowed_from=("submitted",),
        to="approved",
        permission=P.CHANGES_APPROVE,
        notes=notes,
    )


def reject(
    db: Session, ctx: TenantContext, project: Project, co: ChangeOrder, version: int, notes: str | None
) -> ChangeOrder:
    if not notes or not notes.strip():
        raise ValidationFailed("Give a reason for rejecting", details=[{"field": "notes", "message": "Required"}])
    return _transition(
        db,
        ctx,
        project,
        co,
        version,
        allowed_from=("submitted",),
        to="rejected",
        permission=P.CHANGES_APPROVE,
        notes=notes.strip(),
    )


def withdraw(db: Session, ctx: TenantContext, project: Project, co: ChangeOrder, version: int) -> ChangeOrder:
    return _transition(db, ctx, project, co, version, allowed_from=PENDING, to="withdrawn", permission=P.CHANGES_EDIT)


# --- roll-ups used by the commercial summary and dashboard ------------------------------------------------------
def approved_lines_by_code(
    db: Session, project_id: uuid.UUID, side: str
) -> list[tuple[uuid.UUID | None, Decimal, Decimal | None, str]]:
    """(cost_code_id, amount, budget_amount, status) for client-side ('contract') or commitment-side change lines
    on the project, excluding rejected/withdrawn changes."""
    col = ChangeOrder.contract_id if side == "contract" else ChangeOrder.commitment_id
    rows = db.execute(
        select(ChangeOrderLine.cost_code_id, ChangeOrderLine.amount, ChangeOrderLine.budget_amount, ChangeOrder.status)
        .join(ChangeOrder, ChangeOrder.id == ChangeOrderLine.change_order_id)
        .where(
            ChangeOrder.project_id == project_id,
            col.is_not(None),
            ChangeOrder.status.in_(("draft", "submitted", "approved")),
        )
    ).all()
    return [(c, a, b, s) for c, a, b, s in rows]
