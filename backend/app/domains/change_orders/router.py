import uuid
from typing import Any

from fastapi import APIRouter, Response

from app.api.deps import DB, Ctx, TenantContext
from app.domains.change_orders import service
from app.domains.change_orders.constants import REASONS, STATUSES
from app.domains.change_orders.models import ChangeOrder
from app.domains.change_orders.schemas import (
    ChangeOrderCreate,
    ChangeOrderListItem,
    ChangeOrderOut,
    ChangeOrderUpdate,
    DecisionIn,
    LineIn,
    LineOut,
    TargetRef,
    VersionIn,
)
from app.domains.cost_codes.schemas import CostCodeRef
from app.domains.projects.models import Project
from app.domains.tenancy.permissions import P

router = APIRouter(tags=["change orders"])


def _target(db: Any, ctx: TenantContext, co: ChangeOrder) -> tuple[TargetRef, str, str]:
    t = service.target_of(db, co)
    label, _ = service.label_for(ctx, t)
    ref = TargetRef(
        type=t.type,
        id=t.obj.id,
        number=t.obj.number,
        title=t.obj.title,
        counterparty=service.counterparty_name(db, t),
        contract_form=t.obj.contract_form,
    )
    return ref, label, t.obj.currency


def _out(db: Any, ctx: TenantContext, co: ChangeOrder, project: Project) -> ChangeOrderOut:
    ref, label, currency = _target(db, ctx, co)
    amount, budget = service.totals(db, co)
    return ChangeOrderOut(
        id=co.id,
        project_id=project.id,
        project_number=project.number,
        project_name=project.name,
        target=ref,
        label=label,
        number=co.number,
        title=co.title,
        description=co.description,
        reason=co.reason,
        reference=co.reference,
        status=co.status,
        currency=currency,
        schedule_impact_days=co.schedule_impact_days,
        notified_date=co.notified_date,
        response_due_date=co.response_due_date,
        overdue=service.is_overdue(co),
        submitted_at=co.submitted_at,
        decided_at=co.decided_at,
        decision_notes=co.decision_notes,
        total=amount,
        budget_total=budget,
        version=co.version,
        created_at=co.created_at,
        updated_at=co.updated_at,
        is_editable=service.is_editable(ctx, co, project),
        can_approve=ctx.has(P.CHANGES_APPROVE) and project.archived_at is None,
        lines=[
            LineOut(
                id=ln.id,
                sequence=ln.sequence,
                description=ln.description,
                quantity=ln.quantity,
                unit=ln.unit,
                unit_rate=ln.unit_rate,
                amount=ln.amount,
                budget_amount=ln.budget_amount,
                cost_code=CostCodeRef.model_validate(code) if code else None,
            )
            for ln, code in service.lines(db, co)
        ],
    )


@router.get("/change-orders/reference")
def reference(ctx: Ctx) -> dict[str, dict[str, str]]:
    return {"reasons": REASONS, "statuses": STATUSES}


@router.get("/change-orders", response_model=list[ChangeOrderListItem])
def list_change_orders(
    db: DB,
    ctx: Ctx,
    project_id: uuid.UUID | None = None,
    contract_id: uuid.UUID | None = None,
    commitment_id: uuid.UUID | None = None,
    status: str | None = None,
) -> list[ChangeOrderListItem]:
    out = []
    for co, project in service.list_change_orders(
        db, ctx, project_id=project_id, contract_id=contract_id, commitment_id=commitment_id, status=status
    ):
        ref, label, currency = _target(db, ctx, co)
        out.append(
            ChangeOrderListItem(
                id=co.id,
                project_id=project.id,
                project_number=project.number,
                project_name=project.name,
                target=ref,
                label=label,
                number=co.number,
                title=co.title,
                status=co.status,
                currency=currency,
                total=service.totals(db, co)[0],
                response_due_date=co.response_due_date,
                overdue=service.is_overdue(co),
                updated_at=co.updated_at,
            )
        )
    return out


@router.post("/change-orders", response_model=ChangeOrderOut, status_code=201)
def create(body: ChangeOrderCreate, db: DB, ctx: Ctx) -> ChangeOrderOut:
    co, project = service.create(db, ctx, body.model_dump())
    db.commit()
    return _out(db, ctx, co, project)


@router.get("/change-orders/{co_id}", response_model=ChangeOrderOut)
def get(co_id: uuid.UUID, db: DB, ctx: Ctx) -> ChangeOrderOut:
    co, project = service.get_change_order(db, ctx, co_id)
    return _out(db, ctx, co, project)


@router.patch("/change-orders/{co_id}", response_model=ChangeOrderOut)
def update(co_id: uuid.UUID, body: ChangeOrderUpdate, db: DB, ctx: Ctx) -> ChangeOrderOut:
    co, project = service.get_change_order(db, ctx, co_id)
    service.update(db, ctx, project, co, body.version, body.model_dump(exclude_unset=True, exclude={"version"}))
    db.commit()
    return _out(db, ctx, co, project)


@router.delete("/change-orders/{co_id}", status_code=204)
def delete(co_id: uuid.UUID, db: DB, ctx: Ctx) -> Response:
    co, project = service.get_change_order(db, ctx, co_id)
    service.delete_draft(db, ctx, project, co)
    db.commit()
    return Response(status_code=204)


@router.post("/change-orders/{co_id}/lines", response_model=ChangeOrderOut, status_code=201)
def add_line(co_id: uuid.UUID, body: LineIn, db: DB, ctx: Ctx) -> ChangeOrderOut:
    co, project = service.get_change_order(db, ctx, co_id)
    service.add_line(db, ctx, project, co, body.model_dump())
    db.commit()
    return _out(db, ctx, co, project)


@router.put("/change-orders/{co_id}/lines/{line_id}", response_model=ChangeOrderOut)
def update_line(co_id: uuid.UUID, line_id: uuid.UUID, body: LineIn, db: DB, ctx: Ctx) -> ChangeOrderOut:
    co, project = service.get_change_order(db, ctx, co_id)
    service.update_line(db, ctx, project, co, service.get_line(db, co, line_id), body.model_dump())
    db.commit()
    return _out(db, ctx, co, project)


@router.delete("/change-orders/{co_id}/lines/{line_id}", response_model=ChangeOrderOut)
def delete_line(co_id: uuid.UUID, line_id: uuid.UUID, db: DB, ctx: Ctx) -> ChangeOrderOut:
    co, project = service.get_change_order(db, ctx, co_id)
    service.delete_line(db, ctx, project, co, service.get_line(db, co, line_id))
    db.commit()
    return _out(db, ctx, co, project)


def _action(name: str, fn: Any, body_model: type) -> None:
    def handler(co_id: uuid.UUID, body: body_model, db: DB, ctx: Ctx) -> ChangeOrderOut:  # type: ignore[valid-type]
        co, project = service.get_change_order(db, ctx, co_id)
        args = (body.version, body.notes) if isinstance(body, DecisionIn) else (body.version,)  # type: ignore[attr-defined]
        fn(db, ctx, project, co, *args)
        db.commit()
        return _out(db, ctx, co, project)

    router.add_api_route(
        f"/change-orders/{{co_id}}/{name}",
        handler,
        methods=["POST"],
        response_model=ChangeOrderOut,
        name=f"change_order_{name.replace('-', '_')}",
    )


_action("submit", service.submit, VersionIn)
_action("return-to-draft", service.return_to_draft, VersionIn)
_action("withdraw", service.withdraw, VersionIn)
_action("approve", service.approve, DecisionIn)
_action("reject", service.reject, DecisionIn)
