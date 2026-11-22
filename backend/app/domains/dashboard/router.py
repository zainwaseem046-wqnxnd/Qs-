from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import DB, TenantContext, require
from app.core.money import DecimalOut, MoneyAmount
from app.core.schemas import ApiModel
from app.domains.audit.schemas import AuditEventOut, to_out
from app.domains.dashboard import service
from app.domains.projects.router import list_item
from app.domains.projects.schemas import ProjectListItem
from app.domains.tenancy.permissions import P

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class CurrencyTotalOut(ApiModel):
    currency: str
    amount: MoneyAmount
    project_count: int
    projects_without_value: int


class PendingChangesOut(ApiModel):
    currency: str
    amount: MoneyAmount
    count: int
    overdue_count: int


class ForecastTotalsOut(ApiModel):
    currency: str
    revenue: MoneyAmount
    cost_to_date: MoneyAmount
    final_cost: MoneyAmount
    gross_profit: MoneyAmount
    margin_percent: DecimalOut | None
    projects_forecast: int
    projects_without_forecast: int
    latest_period: date | None


class DashboardOut(ApiModel):
    total_projects: int
    by_status: dict[str, int]
    by_sector: dict[str, int]
    live_contract_value: list[CurrencyTotalOut] | None
    pursuit_value: list[CurrencyTotalOut] | None
    original_budget: list[CurrencyTotalOut] | None
    committed_cost: list[CurrencyTotalOut] | None
    pending_changes: list[PendingChangesOut] | None
    forecast: list[ForecastTotalsOut] | None
    upcoming_completions: list[ProjectListItem]
    recent_projects: list[ProjectListItem]
    recent_activity: list[AuditEventOut]
    financials_visible: bool
    unavailable_metrics: list[str]
    unavailable_reason: str


@router.get("/summary", response_model=DashboardOut)
def summary(db: DB, ctx: Annotated[TenantContext, Depends(require(P.DASHBOARD_VIEW))]) -> DashboardOut:
    data = service.build(db, ctx)

    def totals(rows):  # type: ignore[no-untyped-def]
        return None if rows is None else [CurrencyTotalOut.model_validate(r.__dict__) for r in rows]

    return DashboardOut(
        total_projects=data.total_projects,
        by_status=data.by_status,
        by_sector=data.by_sector,
        live_contract_value=totals(data.live_contract_value),
        pursuit_value=totals(data.pursuit_value),
        original_budget=totals(data.original_budget),
        committed_cost=totals(data.committed_cost),
        forecast=None
        if data.forecast is None
        else [ForecastTotalsOut.model_validate(f.__dict__) for f in data.forecast],
        pending_changes=None
        if data.pending_changes is None
        else [PendingChangesOut.model_validate(p.__dict__) for p in data.pending_changes],
        upcoming_completions=[list_item(ctx, p) for p in data.upcoming_completions],
        recent_projects=[list_item(ctx, p) for p in data.recent_projects],
        recent_activity=to_out(db, data.recent_events, redact_financials=not data.financials_visible),
        financials_visible=data.financials_visible,
        unavailable_metrics=data.unavailable_metrics,
        unavailable_reason=(
            "These metrics are calculated from payment applications, which are delivered in the next milestone. "
            "They are not estimated."
        ),
    )
