"""Project cost budgets.

Creating a budget from an approved estimate version:
  * one budget line per cost code = sum of that code's base-scope line totals (ordered by code)
  * base lines without a cost code roll into one "Unassigned (no cost code)" line
  * each markup with include_in_budget = true becomes its own line ("Markup: <name>")
  * markups with include_in_budget = false (typically profit/fee) are NOT budgeted cost
  * alternates and excluded lines are not part of the budget
Budget total = sum of budget lines. Approval freezes the budget (database trigger).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import TenantContext
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.domains.audit import service as audit
from app.domains.budgets.models import Budget, BudgetLine
from app.domains.cost_codes.models import CostCode, CostCodeSet
from app.domains.estimating import service as estimating
from app.domains.estimating.models import Estimate, EstimateVersion
from app.domains.projects.models import Project
from app.domains.projects.service import get_project
from app.domains.tenancy.permissions import P


def _assert_editable(ctx: TenantContext, project: Project, budget: Budget | None = None) -> None:
    ctx.require(P.BUDGETS_EDIT)
    if project.archived_at is not None:
        raise Conflict("Archived projects are read-only", code="project_archived")
    if budget is not None and budget.status != "draft":
        raise Conflict(
            "Approved budgets cannot be changed. Revisions come through budget transfers and change orders.",
            code="budget_locked",
        )


def list_budgets(db: Session, ctx: TenantContext, project: Project) -> list[Budget]:
    ctx.require(P.BUDGETS_VIEW)
    return list(db.scalars(select(Budget).where(Budget.project_id == project.id).order_by(Budget.created_at)))


def get_budget(db: Session, ctx: TenantContext, budget_id: uuid.UUID) -> tuple[Budget, Project]:
    ctx.require(P.BUDGETS_VIEW)
    budget = db.get(Budget, budget_id)
    if budget is None:
        raise NotFound("Budget not found")
    return budget, get_project(db, ctx, budget.project_id)


def lines(db: Session, budget: Budget) -> list[tuple[BudgetLine, CostCode | None]]:
    rows = db.execute(
        select(BudgetLine, CostCode)
        .outerjoin(CostCode, CostCode.id == BudgetLine.cost_code_id)
        .where(BudgetLine.budget_id == budget.id)
        .order_by(BudgetLine.sequence)
    ).all()
    return [(line, code) for line, code in rows]


def total(db: Session, budget: Budget) -> Decimal:
    if budget.total is not None:
        return budget.total
    return db.scalar(
        select(func.coalesce(func.sum(BudgetLine.amount), 0)).where(BudgetLine.budget_id == budget.id)
    ) or Decimal("0.00")


def create_blank(db: Session, ctx: TenantContext, project: Project, data: dict[str, Any]) -> Budget:
    _assert_editable(ctx, project)
    if data.get("cost_code_set_id") and db.get(CostCodeSet, data["cost_code_set_id"]) is None:
        raise ValidationFailed("Cost code structure not found")
    budget = Budget(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        project_id=project.id,
        name=data["name"],
        currency=data.get("currency") or project.currency,
        cost_code_set_id=data.get("cost_code_set_id"),
        created_by_id=ctx.user_id,
    )
    db.add(budget)
    db.flush()
    audit.record(
        db,
        ctx.actor(),
        action="budget.created",
        entity_type="budget",
        entity_id=budget.id,
        project_id=project.id,
        summary=f"Budget '{budget.name}' created",
    )
    return budget


def create_from_estimate(
    db: Session, ctx: TenantContext, project: Project, estimate_id: uuid.UUID, version_number: int, name: str
) -> Budget:
    _assert_editable(ctx, project)
    estimate = db.get(Estimate, estimate_id)
    if estimate is None or estimate.project_id != project.id:
        raise ValidationFailed("Estimate not found on this project")
    version: EstimateVersion = estimating.get_version(db, estimate, version_number)
    if version.status != "approved":
        raise Conflict("Only approved estimate versions can become a budget", code="estimate_not_approved")
    priced = estimating.price_version(db, version)

    by_code: dict[uuid.UUID | None, tuple[CostCode | None, Decimal]] = {}
    for line, result, code in priced.lines:
        if line.inclusion != "base":
            continue
        key = code.id if code else None
        prev = by_code.get(key, (code, Decimal(0)))[1]
        by_code[key] = (code, prev + result.total)

    budget = Budget(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        project_id=project.id,
        name=name,
        currency=estimate.currency,
        cost_code_set_id=estimate.cost_code_set_id,
        source_estimate_version_id=version.id,
        created_by_id=ctx.user_id,
    )
    db.add(budget)
    db.flush()
    seq = 0
    coded = sorted(((c, amt) for k, (c, amt) in by_code.items() if k is not None), key=lambda x: x[0].code)  # type: ignore[union-attr]
    for code, amount in coded:
        seq += 10
        db.add(
            BudgetLine(
                id=uuid.uuid4(),
                tenant_id=ctx.tenant_id,
                budget_id=budget.id,
                sequence=seq,
                cost_code_id=code.id,
                description=code.title,
                amount=amount,
            )
        )  # type: ignore[union-attr]
    if None in by_code:
        seq += 10
        db.add(
            BudgetLine(
                id=uuid.uuid4(),
                tenant_id=ctx.tenant_id,
                budget_id=budget.id,
                sequence=seq,
                description="Unassigned (no cost code)",
                amount=by_code[None][1],
            )
        )
    excluded = []
    for m in priced.totals.markups:
        if not m.include_in_budget:
            excluded.append(f"{m.name} ({m.amount})")
            continue
        seq += 10
        db.add(
            BudgetLine(
                id=uuid.uuid4(),
                tenant_id=ctx.tenant_id,
                budget_id=budget.id,
                sequence=seq,
                description=f"Markup: {m.name}",
                amount=m.amount,
                notes=f"{m.percent}% on {'direct cost' if m.basis == 'direct_cost' else 'running total'}",
            )
        )
    db.flush()
    audit.record(
        db,
        ctx.actor(),
        action="budget.created_from_estimate",
        entity_type="budget",
        entity_id=budget.id,
        project_id=project.id,
        summary=f"Budget '{name}' created from estimate '{estimate.name}' v{version.version_number}",
        changes={"estimate_total": version.total, "budget_total": total(db, budget), "markups_not_budgeted": excluded},
    )
    return budget


def _check_code(db: Session, budget: Budget, cost_code_id: uuid.UUID | None) -> None:
    if cost_code_id is None:
        return
    code = db.get(CostCode, cost_code_id)
    if code is None or (budget.cost_code_set_id and code.set_id != budget.cost_code_set_id):
        raise ValidationFailed(
            "Invalid input",
            details=[{"field": "cost_code_id", "message": "Cost code not found in this budget's structure"}],
        )


def add_line(db: Session, ctx: TenantContext, project: Project, budget: Budget, data: dict[str, Any]) -> BudgetLine:
    _assert_editable(ctx, project, budget)
    _check_code(db, budget, data.get("cost_code_id"))
    seq = (db.scalar(select(func.max(BudgetLine.sequence)).where(BudgetLine.budget_id == budget.id)) or 0) + 10
    line = BudgetLine(id=uuid.uuid4(), tenant_id=ctx.tenant_id, budget_id=budget.id, sequence=seq, **data)
    db.add(line)
    budget.revision += 1
    db.flush()
    audit.record(
        db,
        ctx.actor(),
        action="budget.line_added",
        entity_type="budget",
        entity_id=budget.id,
        project_id=project.id,
        summary=f"Budget line added: {line.description}",
        changes={"amount": line.amount},
    )
    return line


def get_line(db: Session, budget: Budget, line_id: uuid.UUID) -> BudgetLine:
    line = db.get(BudgetLine, line_id)
    if line is None or line.budget_id != budget.id:
        raise NotFound("Budget line not found")
    return line


def update_line(
    db: Session, ctx: TenantContext, project: Project, budget: Budget, line: BudgetLine, data: dict[str, Any]
) -> None:
    _assert_editable(ctx, project, budget)
    _check_code(db, budget, data.get("cost_code_id"))
    fields = ["cost_code_id", "description", "amount", "notes"]
    before = audit.snapshot(line, fields)
    for f in fields:
        setattr(line, f, data.get(f))
    budget.revision += 1
    db.flush()
    changes = audit.diff(before, audit.snapshot(line, fields))
    if changes:
        audit.record(
            db,
            ctx.actor(),
            action="budget.line_updated",
            entity_type="budget",
            entity_id=budget.id,
            project_id=project.id,
            summary=f"Budget line updated: {line.description}",
            changes=changes,
        )


def delete_line(db: Session, ctx: TenantContext, project: Project, budget: Budget, line: BudgetLine) -> None:
    _assert_editable(ctx, project, budget)
    audit.record(
        db,
        ctx.actor(),
        action="budget.line_deleted",
        entity_type="budget",
        entity_id=budget.id,
        project_id=project.id,
        summary=f"Budget line deleted: {line.description}",
        changes={"amount": line.amount},
    )
    db.delete(line)
    budget.revision += 1
    db.flush()


def approve(db: Session, ctx: TenantContext, project: Project, budget: Budget) -> Budget:
    ctx.require(P.BUDGETS_APPROVE)
    if project.archived_at is not None:
        raise Conflict("Archived projects are read-only", code="project_archived")
    if budget.status != "draft":
        raise Conflict("This budget is already approved", code="budget_locked")
    if not lines(db, budget):
        raise ValidationFailed("Add at least one budget line before approval")
    existing = db.scalar(
        select(Budget.id).where(Budget.project_id == project.id, Budget.status == "approved", Budget.kind == "original")
    )
    if existing:
        raise Conflict("This project already has an approved original budget", code="budget_exists")
    budget.total = total(db, budget)
    budget.status = "approved"
    budget.approved_at = datetime.now(UTC)
    budget.approved_by_id = ctx.user_id
    try:
        db.flush()
    except IntegrityError as exc:
        raise Conflict("This project already has an approved original budget", code="budget_exists") from exc
    audit.record(
        db,
        ctx.actor(),
        action="budget.approved",
        entity_type="budget",
        entity_id=budget.id,
        project_id=project.id,
        summary=f"Original budget '{budget.name}' approved",
        changes={"total": budget.total},
    )
    return budget


def delete_draft(db: Session, ctx: TenantContext, project: Project, budget: Budget) -> None:
    _assert_editable(ctx, project, budget)
    audit.record(
        db,
        ctx.actor(),
        action="budget.deleted",
        entity_type="budget",
        entity_id=budget.id,
        project_id=project.id,
        summary=f"Draft budget '{budget.name}' deleted",
    )
    db.delete(budget)
    db.flush()
