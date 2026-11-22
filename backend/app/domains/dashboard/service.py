"""Executive dashboard aggregates.

All sums are computed by PostgreSQL over NUMERIC columns and returned as Decimal. Amounts are grouped by
currency and never summed across currencies. Only projects visible to the caller are included.

Phase 1 scope: portfolio composition and contract values recorded on project records. Budget, cost,
commitment, forecast and cash-flow metrics require Phase 2 data and are reported as unavailable rather
than estimated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import TenantContext
from app.domains.audit.models import AuditEvent
from app.domains.budgets.models import Budget
from app.domains.contracts.models import Commitment, CommitmentLine
from app.domains.projects.constants import LIVE_STATUSES
from app.domains.projects.models import Project
from app.domains.projects.service import visible_project_ids
from app.domains.tenancy.permissions import P


@dataclass
class CurrencyTotal:
    currency: str
    amount: Decimal
    project_count: int
    projects_without_value: int


@dataclass
class DashboardData:
    total_projects: int
    by_status: dict[str, int]
    by_sector: dict[str, int]
    live_contract_value: list[CurrencyTotal] | None
    pursuit_value: list[CurrencyTotal] | None
    original_budget: list[CurrencyTotal] | None
    committed_cost: list[CurrencyTotal] | None
    upcoming_completions: list[Project]
    recent_projects: list[Project]
    recent_events: list[AuditEvent]
    financials_visible: bool
    unavailable_metrics: list[str] = field(default_factory=list)


UNAVAILABLE_PHASE_2 = [
    "Revised budget", "Actual cost", "Forecast final cost",
    "Forecast revenue", "Forecast gross profit", "Forecast gross margin", "Pending changes",
    "Outstanding payments", "Cash flow",
]


def _scope(ctx: TenantContext):  # type: ignore[no-untyped-def]
    conditions = [Project.archived_at.is_(None)]
    if not ctx.has(P.PROJECTS_VIEW_ALL):
        conditions.append(Project.id.in_(visible_project_ids(ctx)))
    return conditions


def _currency_totals(db: Session, ctx: TenantContext, statuses: tuple[str, ...]) -> list[CurrencyTotal]:
    rows = db.execute(
        select(
            Project.currency,
            func.coalesce(func.sum(Project.original_contract_value), 0),
            func.count(),
            func.count().filter(Project.original_contract_value.is_(None)),
        )
        .where(*_scope(ctx), Project.status.in_(statuses))
        .group_by(Project.currency)
        .order_by(Project.currency)
    ).all()
    return [CurrencyTotal(c, Decimal(a), int(n), int(missing)) for c, a, n, missing in rows]


def _budget_totals(db: Session, ctx: TenantContext) -> list[CurrencyTotal]:
    """Approved original budgets of live projects, by currency. projects_without_value counts live projects
    (in that currency) that do not yet have an approved original budget."""
    approved = (
        select(Budget.project_id, Budget.currency, Budget.total)
        .where(Budget.status == "approved", Budget.kind == "original")
        .subquery()
    )
    rows = db.execute(
        select(
            Project.currency,
            func.coalesce(func.sum(approved.c.total), 0),
            func.count(approved.c.project_id),
            func.count().filter(approved.c.project_id.is_(None)),
        )
        .select_from(Project)
        .outerjoin(approved, approved.c.project_id == Project.id)
        .where(*_scope(ctx), Project.status.in_(LIVE_STATUSES))
        .group_by(Project.currency)
        .order_by(Project.currency)
    ).all()
    return [CurrencyTotal(c, Decimal(a), int(n), int(missing)) for c, a, n, missing in rows]


def _committed_totals(db: Session, ctx: TenantContext) -> list[CurrencyTotal]:
    """Executed/closed commitments on live projects, by currency. project_count = projects with commitments;
    projects_without_value = live projects with none yet."""
    committed = (
        select(Commitment.project_id, func.sum(CommitmentLine.amount).label("amount"))
        .join(CommitmentLine, CommitmentLine.commitment_id == Commitment.id)
        .where(Commitment.status.in_(("executed", "closed")))
        .group_by(Commitment.project_id)
        .subquery()
    )
    rows = db.execute(
        select(
            Project.currency,
            func.coalesce(func.sum(committed.c.amount), 0),
            func.count(committed.c.project_id),
            func.count().filter(committed.c.project_id.is_(None)),
        )
        .select_from(Project)
        .outerjoin(committed, committed.c.project_id == Project.id)
        .where(*_scope(ctx), Project.status.in_(LIVE_STATUSES))
        .group_by(Project.currency)
        .order_by(Project.currency)
    ).all()
    return [CurrencyTotal(c, Decimal(a), int(n), int(missing)) for c, a, n, missing in rows]


def build(db: Session, ctx: TenantContext) -> DashboardData:
    scope = _scope(ctx)
    by_status = dict(db.execute(select(Project.status, func.count()).where(*scope).group_by(Project.status)).all())
    by_sector = dict(db.execute(select(Project.sector, func.count()).where(*scope).group_by(Project.sector)).all())
    financials = ctx.has(P.PROJECTS_FINANCIALS_VIEW)

    today = date.today()
    upcoming = db.scalars(
        select(Project).where(*scope, Project.status.in_(LIVE_STATUSES),
                              Project.planned_completion_date.between(today, today + timedelta(days=90)))
        .order_by(Project.planned_completion_date).limit(8)
    ).unique().all()
    recent = db.scalars(select(Project).where(*scope).order_by(Project.updated_at.desc()).limit(6)).unique().all()

    events_stmt = select(AuditEvent).where(AuditEvent.tenant_id == ctx.tenant_id)
    if ctx.has(P.AUDIT_VIEW):
        pass
    elif ctx.has(P.PROJECTS_VIEW_ALL):
        events_stmt = events_stmt.where(AuditEvent.project_id.is_not(None))
    else:
        events_stmt = events_stmt.where(AuditEvent.project_id.in_(visible_project_ids(ctx)))
    events = db.scalars(events_stmt.order_by(AuditEvent.occurred_at.desc()).limit(10)).all()

    return DashboardData(
        total_projects=sum(by_status.values()),
        by_status={k: int(v) for k, v in by_status.items()},
        by_sector={k: int(v) for k, v in by_sector.items()},
        live_contract_value=_currency_totals(db, ctx, LIVE_STATUSES) if financials else None,
        pursuit_value=_currency_totals(db, ctx, ("pursuit",)) if financials else None,
        original_budget=_budget_totals(db, ctx) if ctx.has(P.BUDGETS_VIEW) else None,
        committed_cost=_committed_totals(db, ctx) if ctx.has(P.COMMITMENTS_VIEW) else None,
        upcoming_completions=list(upcoming),
        recent_projects=list(recent),
        recent_events=list(events),
        financials_visible=financials,
        unavailable_metrics=UNAVAILABLE_PHASE_2,
    )
