"""Prime contracts and commitments.

Shared lifecycle: draft (editable) -> executed (terms and lines frozen, original sum recorded) -> closed;
draft -> void. Contract/commitment currency is the project currency in this milestone (multi-currency
commitments are a later item). Measured commitment lines are priced as round2(quantity x unit_rate).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import TenantContext
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.money import extend
from app.domains.audit import service as audit
from app.domains.budgets.models import Budget, BudgetLine
from app.domains.companies.models import Company
from app.domains.contracts.constants import prime_forms, subcontract_forms
from app.domains.contracts.models import Commitment, CommitmentLine, Contract, ContractLine
from app.domains.cost_codes.models import CostCode, CostCodeSet
from app.domains.estimating.models import Estimate
from app.domains.projects.models import Project
from app.domains.projects.service import get_project, visible_project_ids
from app.domains.tenancy.permissions import P

ZERO = Decimal("0.00")
TERMS_FIELDS = [
    "title",
    "contract_form",
    "retention_percent",
    "retention_terms",
    "payment_terms_days",
    "start_date",
    "completion_date",
    "scope_summary",
]
CONTRACT_FIELDS = [
    *TERMS_FIELDS,
    "client_company_id",
    "defects_period_months",
    "liquidated_damages_amount",
    "liquidated_damages_period",
    "bond_required",
    "bond_percent",
    "insurance_notes",
]
COMMITMENT_FIELDS = [*TERMS_FIELDS, "vendor_company_id", "exclusions"]


@dataclass(frozen=True)
class Kind:
    name: str
    model: type[Contract] | type[Commitment]
    line_model: type[ContractLine] | type[CommitmentLine]
    fk: str
    fields: list[str]
    view: str
    edit: str
    execute: str
    label: str


CONTRACT = Kind(
    "contract",
    Contract,
    ContractLine,
    "contract_id",
    CONTRACT_FIELDS,
    P.CONTRACTS_VIEW,
    P.CONTRACTS_EDIT,
    P.CONTRACTS_EXECUTE,
    "Prime contract",
)
COMMITMENT = Kind(
    "commitment",
    Commitment,
    CommitmentLine,
    "commitment_id",
    COMMITMENT_FIELDS,
    P.COMMITMENTS_VIEW,
    P.COMMITMENTS_EDIT,
    P.COMMITMENTS_EXECUTE,
    "Commitment",
)


def _now() -> datetime:
    return datetime.now(UTC)


def _record_label(kind: Kind, obj: Any) -> str:
    if kind is COMMITMENT:
        return f"{'Subcontract' if obj.commitment_type == 'subcontract' else 'Purchase order'} {obj.number}"
    return f"Prime contract {obj.number}"


# --- reads ---------------------------------------------------------------------------------------------------
def list_records(
    db: Session, ctx: TenantContext, kind: Kind, project_id: uuid.UUID | None, status: str | None = None
) -> list[tuple[Any, Project]]:
    ctx.require(kind.view)
    m = kind.model
    stmt = select(m, Project).join(Project, Project.id == m.project_id)
    if project_id:
        get_project(db, ctx, project_id)
        stmt = stmt.where(m.project_id == project_id)
    if status:
        stmt = stmt.where(m.status == status)
    if not ctx.has(P.PROJECTS_VIEW_ALL):
        stmt = stmt.where(m.project_id.in_(visible_project_ids(ctx)))
    return [(r, p) for r, p in db.execute(stmt.order_by(Project.number, m.number)).unique().all()]


def get_record(db: Session, ctx: TenantContext, kind: Kind, record_id: uuid.UUID) -> tuple[Any, Project]:
    ctx.require(kind.view)
    obj = db.get(kind.model, record_id)
    if obj is None:
        raise NotFound(f"{kind.label} not found")
    return obj, get_project(db, ctx, obj.project_id)


def lines(db: Session, kind: Kind, obj: Any) -> list[tuple[Any, CostCode | None]]:
    lm = kind.line_model
    rows = db.execute(
        select(lm, CostCode)
        .outerjoin(CostCode, CostCode.id == lm.cost_code_id)
        .where(getattr(lm, kind.fk) == obj.id)
        .order_by(lm.sequence)
    ).all()
    return [(ln, code) for ln, code in rows]


def current_total(db: Session, kind: Kind, obj: Any) -> Decimal:
    lm = kind.line_model
    total = db.scalar(select(func.coalesce(func.sum(lm.amount), 0)).where(getattr(lm, kind.fk) == obj.id))
    return Decimal(total).quantize(Decimal("0.01"))


def is_editable(ctx: TenantContext, kind: Kind, obj: Any, project: Project) -> bool:
    return obj.status == "draft" and ctx.has(kind.edit) and project.archived_at is None


# --- validation ----------------------------------------------------------------------------------------------
def _assert_editable(ctx: TenantContext, kind: Kind, project: Project, obj: Any | None = None) -> None:
    ctx.require(kind.edit)
    if project.archived_at is not None:
        raise Conflict("Archived projects are read-only", code="project_archived")
    if obj is not None and obj.status != "draft":
        raise Conflict(
            f"{_record_label(kind, obj)} is {obj.status}; its terms and lines are locked. "
            "Changes after execution are made through change orders.",
            code="record_locked",
        )


def _check_form(ctx: TenantContext, kind: Kind, form: str | None, commitment_type: str | None = None) -> None:
    if form is None:
        return
    country = ctx.tenant.country_code
    allowed = prime_forms(country) if kind is CONTRACT else subcontract_forms(country)
    if form not in allowed:
        raise ValidationFailed(
            "Invalid input",
            details=[
                {"field": "contract_form", "message": f"Not an available contract form for {country} organizations"}
            ],
        )


def _check_company(db: Session, company_id: uuid.UUID | None, field: str) -> None:
    if company_id is not None and db.get(Company, company_id) is None:
        raise ValidationFailed("Invalid input", details=[{"field": field, "message": "Company not found"}])


def _default_code_set(db: Session, project: Project) -> uuid.UUID | None:
    """Prefer the approved budget's structure, then the latest estimate's, so codes roll up consistently."""
    budget_set = db.scalar(
        select(Budget.cost_code_set_id).where(
            Budget.project_id == project.id, Budget.status == "approved", Budget.cost_code_set_id.is_not(None)
        )
    )
    if budget_set:
        return budget_set
    return db.scalar(
        select(Estimate.cost_code_set_id)
        .where(Estimate.project_id == project.id, Estimate.cost_code_set_id.is_not(None))
        .order_by(Estimate.updated_at.desc())
        .limit(1)
    )


def _next_number(db: Session, kind: Kind, project: Project, prefix: str) -> str:
    m = kind.model
    existing = db.scalars(select(m.number).where(m.project_id == project.id, m.number.like(f"{prefix}-%"))).all()
    used = [int(x.group(1)) for n in existing if (x := re.fullmatch(rf"{re.escape(prefix)}-(\d+)", n))]
    return f"{prefix}-{(max(used) if used else 0) + 1:03d}"


def _check_line_code(db: Session, obj: Any, cost_code_id: uuid.UUID | None) -> None:
    if cost_code_id is None:
        return
    code = db.get(CostCode, cost_code_id)
    if code is None or not code.is_active or (obj.cost_code_set_id and code.set_id != obj.cost_code_set_id):
        raise ValidationFailed(
            "Invalid input",
            details=[{"field": "cost_code_id", "message": "Cost code not found in this record's cost code structure"}],
        )


# --- create / update ------------------------------------------------------------------------------------------
def create(db: Session, ctx: TenantContext, kind: Kind, project: Project, data: dict[str, Any]) -> Any:
    _assert_editable(ctx, kind, project)
    _check_form(ctx, kind, data.get("contract_form"))
    if kind is CONTRACT:
        _check_company(db, data.get("client_company_id"), "client_company_id")
        prefix = "PC"
    else:
        _check_company(db, data.get("vendor_company_id"), "vendor_company_id")
        prefix = "SC" if data["commitment_type"] == "subcontract" else "PO"
    code_set = data.get("cost_code_set_id") or _default_code_set(db, project)
    if code_set and db.get(CostCodeSet, code_set) is None:
        raise ValidationFailed("Cost code structure not found")
    number = data.get("number") or _next_number(db, kind, project, prefix)
    m = kind.model
    if db.scalar(select(m.id).where(m.project_id == project.id, func.lower(m.number) == number.lower())):
        raise Conflict(f"Number {number} is already used on this project", code="duplicate_number")
    values = {k: data[k] for k in kind.fields if data.get(k) is not None}
    if kind is COMMITMENT:
        values["commitment_type"] = data["commitment_type"]
    obj = m(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        project_id=project.id,
        number=number,
        currency=project.currency,
        cost_code_set_id=code_set,
        created_by_id=ctx.user_id,
        **values,
    )
    db.add(obj)
    try:
        db.flush()
    except IntegrityError as exc:
        raise Conflict(f"Number {number} is already used on this project", code="duplicate_number") from exc
    audit.record(
        db,
        ctx.actor(),
        action=f"{kind.name}.created",
        entity_type=kind.name,
        entity_id=obj.id,
        project_id=project.id,
        summary=f"{_record_label(kind, obj)} '{obj.title}' created",
    )
    return obj


def update(
    db: Session, ctx: TenantContext, kind: Kind, project: Project, obj: Any, version: int, data: dict[str, Any]
) -> Any:
    _assert_editable(ctx, kind, project, obj)
    if obj.version != version:
        raise Conflict("This record was changed by someone else. Reload and try again.", code="version_conflict")
    _check_form(ctx, kind, data.get("contract_form"))
    for f in ("client_company_id", "vendor_company_id"):
        if f in data:
            _check_company(db, data[f], f)
    if kind is COMMITMENT and "vendor_company_id" in data and data["vendor_company_id"] is None:
        data.pop("vendor_company_id")
    for required in ("title", "contract_form"):
        if required in data and data[required] is None:
            data.pop(required)
    fields = [f for f in kind.fields if f in data]
    before = audit.snapshot(obj, fields)
    for f in fields:
        setattr(obj, f, data[f])
    if obj.start_date and obj.completion_date and obj.completion_date < obj.start_date:
        raise ValidationFailed("Completion date must be on or after the start date")
    obj.version += 1
    db.flush()
    changes = audit.diff(before, audit.snapshot(obj, fields))
    if changes:
        audit.record(
            db,
            ctx.actor(),
            action=f"{kind.name}.updated",
            entity_type=kind.name,
            entity_id=obj.id,
            project_id=project.id,
            summary=f"{_record_label(kind, obj)} terms updated",
            changes=changes,
        )
    return obj


# --- lines ---------------------------------------------------------------------------------------------------
def _line_values(kind: Kind, data: dict[str, Any]) -> dict[str, Any]:
    values = {"cost_code_id": data.get("cost_code_id"), "description": data["description"].strip()}
    if kind is COMMITMENT:
        qty, rate = data.get("quantity"), data.get("unit_rate")
        values.update(quantity=qty, unit_rate=rate, unit=(data.get("unit") or None))
        values["amount"] = extend(qty, rate) if qty is not None and rate is not None else data["amount"]
    else:
        values["amount"] = data["amount"]
    return values


def add_line(db: Session, ctx: TenantContext, kind: Kind, project: Project, obj: Any, data: dict[str, Any]) -> Any:
    _assert_editable(ctx, kind, project, obj)
    _check_line_code(db, obj, data.get("cost_code_id"))
    lm = kind.line_model
    seq = (db.scalar(select(func.max(lm.sequence)).where(getattr(lm, kind.fk) == obj.id)) or 0) + 10
    line = lm(id=uuid.uuid4(), tenant_id=ctx.tenant_id, sequence=seq, **{kind.fk: obj.id}, **_line_values(kind, data))
    db.add(line)
    obj.version += 1
    db.flush()
    audit.record(
        db,
        ctx.actor(),
        action=f"{kind.name}.line_added",
        entity_type=kind.name,
        entity_id=obj.id,
        project_id=project.id,
        summary=f"Line added to {_record_label(kind, obj)}: {line.description}",
        changes={"amount": line.amount},
    )
    return line


def get_line(db: Session, kind: Kind, obj: Any, line_id: uuid.UUID) -> Any:
    line = db.get(kind.line_model, line_id)
    if line is None or getattr(line, kind.fk) != obj.id:
        raise NotFound("Line not found")
    return line


def update_line(
    db: Session, ctx: TenantContext, kind: Kind, project: Project, obj: Any, line: Any, data: dict[str, Any]
) -> None:
    _assert_editable(ctx, kind, project, obj)
    _check_line_code(db, obj, data.get("cost_code_id"))
    values = _line_values(kind, data)
    before = audit.snapshot(line, list(values))
    for k, v in values.items():
        setattr(line, k, v)
    obj.version += 1
    db.flush()
    changes = audit.diff(before, audit.snapshot(line, list(values)))
    if changes:
        audit.record(
            db,
            ctx.actor(),
            action=f"{kind.name}.line_updated",
            entity_type=kind.name,
            entity_id=obj.id,
            project_id=project.id,
            summary=f"Line updated on {_record_label(kind, obj)}: {line.description}",
            changes=changes,
        )


def delete_line(db: Session, ctx: TenantContext, kind: Kind, project: Project, obj: Any, line: Any) -> None:
    _assert_editable(ctx, kind, project, obj)
    audit.record(
        db,
        ctx.actor(),
        action=f"{kind.name}.line_deleted",
        entity_type=kind.name,
        entity_id=obj.id,
        project_id=project.id,
        summary=f"Line deleted from {_record_label(kind, obj)}: {line.description}",
        changes={"amount": line.amount},
    )
    db.delete(line)
    obj.version += 1
    db.flush()


# --- lifecycle -------------------------------------------------------------------------------------------------
def _check_version(obj: Any, version: int) -> None:
    if obj.version != version:
        raise Conflict("This record was changed by someone else. Reload and try again.", code="version_conflict")


def execute(
    db: Session, ctx: TenantContext, kind: Kind, project: Project, obj: Any, version: int, executed_date: date
) -> Any:
    ctx.require(kind.execute)
    if project.archived_at is not None:
        raise Conflict("Archived projects are read-only", code="project_archived")
    _check_version(obj, version)
    if obj.status != "draft":
        raise Conflict(f"Only draft records can be executed (this one is {obj.status})", code="invalid_status")
    if not lines(db, kind, obj):
        raise ValidationFailed("Add at least one line before executing")
    if executed_date > date.today():
        raise ValidationFailed("The execution date cannot be in the future")
    obj.original_sum = current_total(db, kind, obj)
    obj.status = "executed"
    obj.executed_date = executed_date
    obj.executed_at = _now()
    obj.executed_by_id = ctx.user_id
    obj.version += 1
    db.flush()
    audit.record(
        db,
        ctx.actor(),
        action=f"{kind.name}.executed",
        entity_type=kind.name,
        entity_id=obj.id,
        project_id=project.id,
        summary=f"{_record_label(kind, obj)} executed",
        changes={"original_sum": obj.original_sum, "executed_date": executed_date},
    )
    return obj


def set_status(
    db: Session, ctx: TenantContext, kind: Kind, project: Project, obj: Any, version: int, target: str
) -> Any:
    ctx.require(kind.execute)
    _check_version(obj, version)
    allowed = {("executed", "closed"), ("draft", "void")}
    if (obj.status, target) not in allowed:
        raise Conflict(f"Cannot change status from {obj.status} to {target}", code="invalid_status")
    obj.status = target
    if target == "closed":
        obj.closed_at = _now()
    obj.version += 1
    db.flush()
    audit.record(
        db,
        ctx.actor(),
        action=f"{kind.name}.{target}",
        entity_type=kind.name,
        entity_id=obj.id,
        project_id=project.id,
        summary=f"{_record_label(kind, obj)} {'closed' if target == 'closed' else 'voided'}",
    )
    return obj


def delete_draft(db: Session, ctx: TenantContext, kind: Kind, project: Project, obj: Any) -> None:
    _assert_editable(ctx, kind, project, obj)
    audit.record(
        db,
        ctx.actor(),
        action=f"{kind.name}.deleted",
        entity_type=kind.name,
        entity_id=obj.id,
        project_id=project.id,
        summary=f"Draft {_record_label(kind, obj)} deleted",
    )
    db.delete(obj)
    db.flush()


# --- commercial summary ------------------------------------------------------------------------------------------
COMMITTED_STATUSES = ("executed", "closed")


def commercial_summary(db: Session, ctx: TenantContext, project: Project) -> dict[str, Any]:
    """Budget vs committed cost by cost code (project currency).

    budget          = approved original budget lines
    budget_changes  = budget_amount on lines of APPROVED client-side change orders
    revised_budget  = budget + budget_changes
    committed       = lines of executed/closed commitments + APPROVED commitment change orders
    pending         = lines of draft commitments + DRAFT/SUBMITTED commitment change orders
    uncommitted     = revised_budget - committed (negative = over-committed)
    contract_value  = executed/closed prime contract lines + APPROVED client-side change orders (revenue)
    Rejected and withdrawn change orders are ignored.
    """
    from app.domains.change_orders.service import approved_lines_by_code  # local import avoids a cycle

    if not (ctx.has(P.BUDGETS_VIEW) or ctx.has(P.COMMITMENTS_VIEW)):
        ctx.require(P.COMMITMENTS_VIEW)
    warnings: list[str] = []
    columns = ("budget", "budget_changes", "committed", "pending", "contract_value", "cost_to_date")
    rows: dict[uuid.UUID | None, dict[str, Decimal]] = {}

    def add(code_id: uuid.UUID | None, column: str, amount: Decimal) -> None:
        row = rows.setdefault(code_id, dict.fromkeys(columns, ZERO))
        row[column] += amount

    budget = db.scalar(select(Budget).where(Budget.project_id == project.id, Budget.status == "approved"))
    if budget is not None and ctx.has(P.BUDGETS_VIEW):
        if budget.currency != project.currency:
            warnings.append(
                f"The approved budget is in {budget.currency}; summary is in {project.currency}. Budget excluded."
            )
        else:
            for code_id, amount in db.execute(
                select(BudgetLine.cost_code_id, BudgetLine.amount).where(BudgetLine.budget_id == budget.id)
            ):
                add(code_id, "budget", amount)
    if ctx.has(P.COMMITMENTS_VIEW):
        stmt = (
            select(Commitment.status, CommitmentLine.cost_code_id, CommitmentLine.amount)
            .join(Commitment, Commitment.id == CommitmentLine.commitment_id)
            .where(Commitment.project_id == project.id, Commitment.status != "void")
        )
        for status, code_id, amount in db.execute(stmt):
            add(code_id, "committed" if status in COMMITTED_STATUSES else "pending", amount)
        if ctx.has(P.CHANGES_VIEW):
            for code_id, amount, _b, status in approved_lines_by_code(db, project.id, "commitment"):
                add(code_id, "committed" if status == "approved" else "pending", amount)
    if ctx.has(P.CONTRACTS_VIEW):
        stmt = (
            select(ContractLine.cost_code_id, ContractLine.amount)
            .join(Contract, Contract.id == ContractLine.contract_id)
            .where(Contract.project_id == project.id, Contract.status.in_(COMMITTED_STATUSES))
        )
        for code_id, amount in db.execute(stmt):
            add(code_id, "contract_value", amount)
    if ctx.has(P.CHANGES_VIEW):
        for code_id, amount, budget_amount, status in approved_lines_by_code(db, project.id, "contract"):
            if status != "approved":
                continue
            if ctx.has(P.CONTRACTS_VIEW):
                add(code_id, "contract_value", amount)
            if budget_amount is not None and ctx.has(P.BUDGETS_VIEW):
                add(code_id, "budget_changes", budget_amount)

    if ctx.has(P.COSTS_VIEW):
        from app.domains.cost_management.service import cost_to_date_by_code  # local import avoids a cycle

        for code_id, amount in cost_to_date_by_code(db, project.id).items():
            add(code_id, "cost_to_date", amount)

    codes = {c.id: c for c in db.scalars(select(CostCode).where(CostCode.id.in_([k for k in rows if k])))}
    out = []
    for code_id, r in rows.items():
        code = codes.get(code_id) if code_id else None
        revised = r["budget"] + r["budget_changes"]
        out.append(
            {
                "cost_code_id": code_id,
                "code": code.code if code else None,
                "title": code.title if code else "Unassigned (no cost code)",
                **r,
                "revised_budget": revised,
                "uncommitted": revised - r["committed"],
            }
        )
    out.sort(key=lambda r: (r["code"] is None, r["code"] or ""))
    totals = {k: sum((r[k] for r in out), ZERO) for k in (*columns, "revised_budget", "uncommitted")}
    over = [r["code"] or r["title"] for r in out if r["revised_budget"] > 0 and r["uncommitted"] < 0]
    if over:
        warnings.append(f"Over-committed against budget: {', '.join(over)}")
    return {
        "currency": project.currency,
        "has_approved_budget": budget is not None,
        "rows": out,
        "totals": {"cost_code_id": None, "code": None, "title": "Total", **totals},
        "warnings": warnings,
    }
