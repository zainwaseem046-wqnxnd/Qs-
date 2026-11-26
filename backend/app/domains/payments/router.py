import uuid
from typing import Any

from fastapi import APIRouter, Response
from sqlalchemy import select

from app.api.deps import DB, Ctx, TenantContext
from app.core.errors import Conflict
from app.domains.contracts.models import Contract
from app.domains.payments import service
from app.domains.payments.models import PaymentApplication
from app.domains.payments.schemas import (
    ApplicationCreate,
    ApplicationOut,
    ApplicationSummary,
    ApplicationUpdate,
    BillingSummaryOut,
    CertifyIn,
    LineOut,
    LineUpdate,
    PaymentIn,
    TotalsOut,
    VersionIn,
)
from app.domains.projects.models import Project
from app.domains.projects.service import get_project
from app.domains.tenancy.permissions import P

router = APIRouter(tags=["payments"])


def _summary_fields(ctx: TenantContext, a: PaymentApplication, contract: Contract) -> dict[str, Any]:
    return {
        "id": a.id,
        "project_id": a.project_id,
        "contract_id": a.contract_id,
        "contract_number": contract.number,
        "contract_title": contract.title,
        "number": a.number,
        "label": f"{service.label(ctx.tenant.country_code)} {a.number}",
        "status": a.status,
        "currency": a.currency,
        "period_to": a.period_to,
        "application_date": a.application_date,
        "due_date": a.due_date,
        "final_payment_date": a.final_payment_date,
        "pay_less_notice_date": a.pay_less_notice_date,
        "amount_due": a.amount_due,
        "certified_amount": a.certified_amount,
        "paid_amount": a.paid_amount,
        "outstanding": service.outstanding(a),
        "is_overdue": service.is_overdue(a),
    }


def _out(db: Any, ctx: TenantContext, a: PaymentApplication, project: Project) -> ApplicationOut:
    contract = db.get(Contract, a.contract_id)
    result = service.compute(db, a)
    t = result["totals"]
    live = project.archived_at is None
    return ApplicationOut(
        **_summary_fields(ctx, a, contract),
        retention_percent=a.retention_percent,
        notes=a.notes,
        submitted_at=a.submitted_at,
        certified_date=a.certified_date,
        certification_note=a.certification_note,
        paid_date=a.paid_date,
        payment_reference=a.payment_reference,
        version=a.version,
        is_editable=a.status == "draft" and ctx.has(P.PAYMENTS_EDIT) and live,
        can_certify=a.status in ("submitted", "certified") and ctx.has(P.PAYMENTS_CERTIFY) and live,
        totals=TotalsOut.model_validate(t.__dict__),
        lines=[
            LineOut(
                id=ln.id,
                item=ln.item,
                description=ln.description,
                source="contract" if ln.contract_line_id else "change_order",
                **r.__dict__,
            )
            for ln, r in result["lines"]
        ],
    )


@router.get("/projects/{project_id}/payment-applications", response_model=list[ApplicationSummary])
def list_applications(project_id: uuid.UUID, db: DB, ctx: Ctx) -> list[ApplicationSummary]:
    project = get_project(db, ctx, project_id)
    apps = service.list_for_project(db, ctx, project)
    contracts = {c.id: c for c in db.scalars(select(Contract).where(Contract.project_id == project.id))}
    return [ApplicationSummary(**_summary_fields(ctx, a, contracts[a.contract_id])) for a in apps]


@router.get("/projects/{project_id}/billing-summary", response_model=BillingSummaryOut)
def billing_summary(project_id: uuid.UUID, db: DB, ctx: Ctx) -> BillingSummaryOut:
    project = get_project(db, ctx, project_id)
    return BillingSummaryOut(**service.billing_summary(db, ctx, project))


@router.post("/projects/{project_id}/payment-applications", response_model=ApplicationOut, status_code=201)
def create_application(project_id: uuid.UUID, body: ApplicationCreate, db: DB, ctx: Ctx) -> ApplicationOut:
    project = get_project(db, ctx, project_id)
    a = service.create(db, ctx, project, body.contract_id, body.period_to, body.application_date)
    db.commit()
    return _out(db, ctx, a, project)


@router.get("/payment-applications/{app_id}", response_model=ApplicationOut)
def get_application(app_id: uuid.UUID, db: DB, ctx: Ctx) -> ApplicationOut:
    a, project = service.get_application(db, ctx, app_id)
    return _out(db, ctx, a, project)


@router.patch("/payment-applications/{app_id}", response_model=ApplicationOut)
def update_application(app_id: uuid.UUID, body: ApplicationUpdate, db: DB, ctx: Ctx) -> ApplicationOut:
    a, project = service.get_application(db, ctx, app_id)
    service.update_header(db, ctx, project, a, body.version, body.model_dump(exclude_unset=True, exclude={"version"}))
    db.commit()
    return _out(db, ctx, a, project)


@router.put("/payment-applications/{app_id}/lines/{line_id}", response_model=ApplicationOut)
def update_line(app_id: uuid.UUID, line_id: uuid.UUID, body: LineUpdate, db: DB, ctx: Ctx) -> ApplicationOut:
    a, project = service.get_application(db, ctx, app_id)
    service.update_line(db, ctx, project, a, line_id, body.model_dump())
    db.commit()
    return _out(db, ctx, a, project)


@router.post("/payment-applications/{app_id}/submit", response_model=ApplicationOut)
def submit(app_id: uuid.UUID, body: VersionIn, db: DB, ctx: Ctx) -> ApplicationOut:
    a, project = service.get_application(db, ctx, app_id)
    if service.sync_schedule(db, ctx, project, a, body.version):
        db.commit()  # keep the added lines so the user can review them, then refuse this submission
        raise Conflict(
            "A change order was approved since this application was started; its line has been added. "
            "Review the application and submit again.",
            code="schedule_changed",
        )
    service.submit(db, ctx, project, a, body.version)
    db.commit()
    return _out(db, ctx, a, project)


@router.post("/payment-applications/{app_id}/return-to-draft", response_model=ApplicationOut)
def return_to_draft(app_id: uuid.UUID, body: VersionIn, db: DB, ctx: Ctx) -> ApplicationOut:
    a, project = service.get_application(db, ctx, app_id)
    service.return_to_draft(db, ctx, project, a, body.version)
    db.commit()
    return _out(db, ctx, a, project)


@router.post("/payment-applications/{app_id}/certify", response_model=ApplicationOut)
def certify(app_id: uuid.UUID, body: CertifyIn, db: DB, ctx: Ctx) -> ApplicationOut:
    a, project = service.get_application(db, ctx, app_id)
    service.certify(db, ctx, project, a, body.version, body.model_dump(exclude={"version"}))
    db.commit()
    return _out(db, ctx, a, project)


@router.post("/payment-applications/{app_id}/payment", response_model=ApplicationOut)
def record_payment(app_id: uuid.UUID, body: PaymentIn, db: DB, ctx: Ctx) -> ApplicationOut:
    a, project = service.get_application(db, ctx, app_id)
    service.record_payment(db, ctx, project, a, body.version, body.model_dump(exclude={"version"}))
    db.commit()
    return _out(db, ctx, a, project)


@router.delete("/payment-applications/{app_id}", status_code=204)
def delete_application(app_id: uuid.UUID, db: DB, ctx: Ctx) -> Response:
    a, project = service.get_application(db, ctx, app_id)
    service.delete_draft(db, ctx, project, a)
    db.commit()
    return Response(status_code=204)
