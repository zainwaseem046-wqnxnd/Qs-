import uuid
from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, File, Query, Response, UploadFile

from app.api.deps import DB, Ctx, TenantContext
from app.core.errors import PayloadTooLarge
from app.domains.companies.models import Company
from app.domains.contracts.models import Commitment
from app.domains.cost_codes.models import CostCode
from app.domains.cost_codes.schemas import CostCodeRef
from app.domains.cost_management import service
from app.domains.cost_management.models import CostTransaction, Forecast
from app.domains.cost_management.schemas import (
    ForecastCreate,
    ForecastLineIn,
    ForecastLineOut,
    ForecastOut,
    ForecastSummary,
    ForecastUpdate,
    ImportOut,
    ReverseIn,
    TransactionIn,
    TransactionOut,
    TransactionPage,
    VersionIn,
)
from app.domains.projects.models import Project
from app.domains.projects.service import get_project
from app.domains.tenancy.permissions import P

router = APIRouter(tags=["cost management"])
MAX_IMPORT_BYTES = 5 * 1024 * 1024


def _tx_out(db: Any, txs: list[CostTransaction]) -> list[TransactionOut]:
    reversed_ids = service.reversed_ids(db, [t.id for t in txs])
    codes = {
        c.id: c for c in db.query(CostCode).filter(CostCode.id.in_([t.cost_code_id for t in txs if t.cost_code_id]))
    }
    coms = {
        c.id: c.number
        for c in db.query(Commitment).filter(Commitment.id.in_([t.commitment_id for t in txs if t.commitment_id]))
    }
    vendors = {
        c.id: c.name
        for c in db.query(Company).filter(Company.id.in_([t.vendor_company_id for t in txs if t.vendor_company_id]))
    }
    return [
        TransactionOut(
            id=t.id,
            transaction_type=t.transaction_type,
            transaction_date=t.transaction_date,
            description=t.description,
            reference=t.reference,
            amount=t.amount,
            reverses_id=t.reverses_id,
            reversed=t.id in reversed_ids,
            imported=t.import_batch_id is not None,
            created_at=t.created_at,
            cost_code=CostCodeRef.model_validate(codes[t.cost_code_id]) if t.cost_code_id in codes else None,
            commitment_number=coms.get(t.commitment_id) if t.commitment_id else None,
            vendor_name=vendors.get(t.vendor_company_id) if t.vendor_company_id else None,
        )
        for t in txs
    ]


@router.get("/projects/{project_id}/cost-transactions", response_model=TransactionPage)
def list_transactions(
    project_id: uuid.UUID,
    db: DB,
    ctx: Ctx,
    cost_code_id: uuid.UUID | None = None,
    transaction_type: Literal["actual", "accrual"] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TransactionPage:
    project = get_project(db, ctx, project_id)
    rows, total, amount = service.list_transactions(
        db,
        ctx,
        project,
        cost_code_id=cost_code_id,
        transaction_type=transaction_type,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return TransactionPage(items=_tx_out(db, rows), total=total, amount_total=amount, limit=limit, offset=offset)


@router.post("/projects/{project_id}/cost-transactions", response_model=TransactionOut, status_code=201)
def post_transaction(project_id: uuid.UUID, body: TransactionIn, db: DB, ctx: Ctx) -> TransactionOut:
    project = get_project(db, ctx, project_id)
    tx = service.post_transaction(db, ctx, project, body.model_dump())
    db.commit()
    return _tx_out(db, [tx])[0]


@router.post("/projects/{project_id}/cost-transactions/{tx_id}/reverse", response_model=TransactionOut, status_code=201)
def reverse(project_id: uuid.UUID, tx_id: uuid.UUID, body: ReverseIn, db: DB, ctx: Ctx) -> TransactionOut:
    project = get_project(db, ctx, project_id)
    rev = service.reverse(db, ctx, project, service.get_transaction(db, project, tx_id), body.reason)
    db.commit()
    return _tx_out(db, [rev])[0]


@router.post("/projects/{project_id}/cost-transactions/import", response_model=ImportOut)
def import_costs(project_id: uuid.UUID, db: DB, ctx: Ctx, file: Annotated[UploadFile, File()]) -> ImportOut:
    project = get_project(db, ctx, project_id)
    content = file.file.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        raise PayloadTooLarge("Import files are limited to 5 MB")
    created, total, errors = service.import_csv(db, ctx, project, file.filename or "import.csv", content)
    if errors:
        db.rollback()
    else:
        db.commit()
    return ImportOut(created=created, total=total, errors=errors)


def _forecast_out(db: Any, ctx: TenantContext, f: Forecast, project: Project) -> ForecastOut:
    result = service.compute(db, ctx, project, f)
    t = result["totals"]
    return ForecastOut(
        id=f.id,
        project_id=project.id,
        period=f.period,
        period_end=service.period_end(f.period),
        status=f.status,
        currency=f.currency,
        revenue_adjustment=f.revenue_adjustment,
        revenue_adjustment_note=f.revenue_adjustment_note,
        notes=f.notes,
        version=f.version,
        approved_at=f.approved_at,
        is_editable=f.status == "draft" and ctx.has(P.FORECASTS_EDIT) and project.archived_at is None,
        can_approve=f.status == "draft" and ctx.has(P.FORECASTS_APPROVE) and project.archived_at is None,
        revised_contract=result["revised_contract"],
        revenue=t.revenue,
        revised_budget=t.revised_budget,
        committed=t.committed,
        cost_to_date=t.cost_to_date,
        cost_to_complete=t.cost_to_complete,
        final_cost=t.final_cost,
        variance=t.variance,
        gross_profit=t.gross_profit,
        margin_percent=t.margin_percent,
        percent_complete=t.percent_complete,
        earned_revenue=t.earned_revenue,
        lines=[
            ForecastLineOut(
                id=x["line"].id,
                cost_code=CostCodeRef.model_validate(x["code"]) if x["code"] else None,
                method=x["line"].method,
                manual_ctc=x["line"].manual_ctc,
                notes=x["line"].notes,
                revised_budget=x["result"].revised_budget,
                committed=x["result"].committed,
                cost_to_date=x["result"].cost_to_date,
                cost_to_complete=x["result"].cost_to_complete,
                final_cost=x["result"].final_cost,
                variance=x["result"].variance,
            )
            for x in result["lines"]
        ],
    )


@router.get("/projects/{project_id}/forecasts", response_model=list[ForecastSummary])
def list_forecasts(project_id: uuid.UUID, db: DB, ctx: Ctx) -> list[ForecastSummary]:
    project = get_project(db, ctx, project_id)
    return [ForecastSummary.model_validate(f) for f in service.list_forecasts(db, ctx, project)]


@router.post("/projects/{project_id}/forecasts", response_model=ForecastOut, status_code=201)
def create_forecast(project_id: uuid.UUID, body: ForecastCreate, db: DB, ctx: Ctx) -> ForecastOut:
    project = get_project(db, ctx, project_id)
    f = service.create_forecast(db, ctx, project, body.period)
    db.commit()
    return _forecast_out(db, ctx, f, project)


@router.get("/forecasts/{forecast_id}", response_model=ForecastOut)
def get_forecast(forecast_id: uuid.UUID, db: DB, ctx: Ctx) -> ForecastOut:
    f, project = service.get_forecast(db, ctx, forecast_id)
    return _forecast_out(db, ctx, f, project)


@router.patch("/forecasts/{forecast_id}", response_model=ForecastOut)
def update_forecast(forecast_id: uuid.UUID, body: ForecastUpdate, db: DB, ctx: Ctx) -> ForecastOut:
    f, project = service.get_forecast(db, ctx, forecast_id)
    service.update_header(db, ctx, project, f, body.version, body.model_dump(exclude_unset=True, exclude={"version"}))
    db.commit()
    return _forecast_out(db, ctx, f, project)


@router.put("/forecasts/{forecast_id}/lines/{line_id}", response_model=ForecastOut)
def update_line(forecast_id: uuid.UUID, line_id: uuid.UUID, body: ForecastLineIn, db: DB, ctx: Ctx) -> ForecastOut:
    f, project = service.get_forecast(db, ctx, forecast_id)
    service.update_line(db, ctx, project, f, line_id, body.model_dump())
    db.commit()
    return _forecast_out(db, ctx, f, project)


@router.post("/forecasts/{forecast_id}/approve", response_model=ForecastOut)
def approve_forecast(forecast_id: uuid.UUID, body: VersionIn, db: DB, ctx: Ctx) -> ForecastOut:
    f, project = service.get_forecast(db, ctx, forecast_id)
    service.approve(db, ctx, project, f, body.version)
    db.commit()
    return _forecast_out(db, ctx, f, project)


@router.delete("/forecasts/{forecast_id}", status_code=204)
def delete_forecast(forecast_id: uuid.UUID, db: DB, ctx: Ctx) -> Response:
    f, project = service.get_forecast(db, ctx, forecast_id)
    service.delete_draft(db, ctx, project, f)
    db.commit()
    return Response(status_code=204)
