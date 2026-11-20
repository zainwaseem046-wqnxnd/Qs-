from __future__ import annotations

import uuid

from fastapi import APIRouter, Response

from app.api.deps import DB, Ctx
from app.domains.budgets import service
from app.domains.budgets.models import Budget
from app.domains.budgets.schemas import BudgetCreate, BudgetFromEstimate, BudgetLineIn, BudgetLineOut, BudgetOut
from app.domains.cost_codes.schemas import CostCodeRef
from app.domains.estimating.models import Estimate, EstimateVersion
from app.domains.projects.models import Project
from app.domains.projects.service import get_project
from app.domains.tenancy.permissions import P

router = APIRouter(tags=["budgets"])


def _out(db, ctx, project: Project, budget: Budget) -> BudgetOut:  # type: ignore[no-untyped-def]
    source = None
    if budget.source_estimate_version_id:
        version = db.get(EstimateVersion, budget.source_estimate_version_id)
        estimate = db.get(Estimate, version.estimate_id) if version else None
        if version and estimate:
            source = f"{estimate.name} — version {version.version_number}"
    return BudgetOut(
        id=budget.id,
        project_id=budget.project_id,
        name=budget.name,
        kind=budget.kind,
        status=budget.status,
        currency=budget.currency,
        cost_code_set_id=budget.cost_code_set_id,
        source_estimate_version_id=budget.source_estimate_version_id,
        source_description=source,
        total=service.total(db, budget),
        approved_at=budget.approved_at,
        created_at=budget.created_at,
        is_editable=budget.status == "draft" and ctx.has(P.BUDGETS_EDIT) and project.archived_at is None,
        lines=[
            BudgetLineOut(
                id=ln.id,
                sequence=ln.sequence,
                description=ln.description,
                amount=ln.amount,
                notes=ln.notes,
                cost_code=CostCodeRef.model_validate(code) if code else None,
            )
            for ln, code in service.lines(db, budget)
        ],
    )


@router.get("/projects/{project_id}/budgets", response_model=list[BudgetOut])
def list_budgets(project_id: uuid.UUID, db: DB, ctx: Ctx) -> list[BudgetOut]:
    project = get_project(db, ctx, project_id)
    return [_out(db, ctx, project, b) for b in service.list_budgets(db, ctx, project)]


@router.post("/projects/{project_id}/budgets", response_model=BudgetOut, status_code=201)
def create_budget(project_id: uuid.UUID, body: BudgetCreate, db: DB, ctx: Ctx) -> BudgetOut:
    project = get_project(db, ctx, project_id)
    budget = service.create_blank(db, ctx, project, body.model_dump())
    db.commit()
    return _out(db, ctx, project, budget)


@router.post("/projects/{project_id}/budgets/from-estimate", response_model=BudgetOut, status_code=201)
def create_from_estimate(project_id: uuid.UUID, body: BudgetFromEstimate, db: DB, ctx: Ctx) -> BudgetOut:
    project = get_project(db, ctx, project_id)
    budget = service.create_from_estimate(db, ctx, project, body.estimate_id, body.version_number, body.name)
    db.commit()
    return _out(db, ctx, project, budget)


@router.get("/budgets/{budget_id}", response_model=BudgetOut)
def get_budget(budget_id: uuid.UUID, db: DB, ctx: Ctx) -> BudgetOut:
    budget, project = service.get_budget(db, ctx, budget_id)
    return _out(db, ctx, project, budget)


@router.post("/budgets/{budget_id}/lines", response_model=BudgetOut, status_code=201)
def add_line(budget_id: uuid.UUID, body: BudgetLineIn, db: DB, ctx: Ctx) -> BudgetOut:
    budget, project = service.get_budget(db, ctx, budget_id)
    service.add_line(db, ctx, project, budget, body.model_dump())
    db.commit()
    return _out(db, ctx, project, budget)


@router.put("/budgets/{budget_id}/lines/{line_id}", response_model=BudgetOut)
def update_line(budget_id: uuid.UUID, line_id: uuid.UUID, body: BudgetLineIn, db: DB, ctx: Ctx) -> BudgetOut:
    budget, project = service.get_budget(db, ctx, budget_id)
    service.update_line(db, ctx, project, budget, service.get_line(db, budget, line_id), body.model_dump())
    db.commit()
    return _out(db, ctx, project, budget)


@router.delete("/budgets/{budget_id}/lines/{line_id}", response_model=BudgetOut)
def delete_line(budget_id: uuid.UUID, line_id: uuid.UUID, db: DB, ctx: Ctx) -> BudgetOut:
    budget, project = service.get_budget(db, ctx, budget_id)
    service.delete_line(db, ctx, project, budget, service.get_line(db, budget, line_id))
    db.commit()
    return _out(db, ctx, project, budget)


@router.post("/budgets/{budget_id}/approve", response_model=BudgetOut)
def approve(budget_id: uuid.UUID, db: DB, ctx: Ctx) -> BudgetOut:
    budget, project = service.get_budget(db, ctx, budget_id)
    service.approve(db, ctx, project, budget)
    db.commit()
    return _out(db, ctx, project, budget)


@router.delete("/budgets/{budget_id}", status_code=204)
def delete_budget(budget_id: uuid.UUID, db: DB, ctx: Ctx) -> Response:
    budget, project = service.get_budget(db, ctx, budget_id)
    service.delete_draft(db, ctx, project, budget)
    db.commit()
    return Response(status_code=204)
