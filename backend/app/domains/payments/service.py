"""Payment applications / interim valuations. See calc.py for the arithmetic and models.py for the lifecycle."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import TenantContext
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.money import round_money
from app.domains.audit import service as audit
from app.domains.change_orders.models import ChangeOrder
from app.domains.contracts.models import Contract, ContractLine
from app.domains.cost_management.models import Forecast
from app.domains.payments import calc
from app.domains.payments.models import PaymentApplication, PaymentApplicationLine
from app.domains.projects.models import Project
from app.domains.tenancy.permissions import P

ZERO = Decimal("0.00")
HEADER_FIELDS = (
    "period_to",
    "application_date",
    "due_date",
    "final_payment_date",
    "pay_less_notice_date",
    "retention_percent",
    "notes",
)


def _now() -> datetime:
    return datetime.now(UTC)


def _assert_live(project: Project) -> None:
    if project.archived_at is not None:
        raise Conflict("Archived projects are read-only", code="project_archived")


def _check_version(a: PaymentApplication, version: int | None) -> None:
    if version is not None and a.version != version:
        raise Conflict("This application was changed by someone else. Reload and try again.", code="version_conflict")


def label(country: str) -> str:
    return "Valuation" if country == "GB" else "Pay application"


# --- reads ---------------------------------------------------------------------------------------------------------
def list_for_project(db: Session, ctx: TenantContext, project: Project) -> list[PaymentApplication]:
    ctx.require(P.PAYMENTS_VIEW)
    return list(
        db.scalars(
            select(PaymentApplication)
            .where(PaymentApplication.project_id == project.id)
            .order_by(PaymentApplication.contract_id, PaymentApplication.number.desc())
        )
    )


def get_application(db: Session, ctx: TenantContext, app_id: uuid.UUID) -> tuple[PaymentApplication, Project]:
    from app.domains.projects.service import get_project

    ctx.require(P.PAYMENTS_VIEW)
    a = db.get(PaymentApplication, app_id)
    if a is None:
        raise NotFound("Payment application not found")
    return a, get_project(db, ctx, a.project_id)


def lines_of(db: Session, a: PaymentApplication) -> list[PaymentApplicationLine]:
    return list(
        db.scalars(
            select(PaymentApplicationLine)
            .where(PaymentApplicationLine.application_id == a.id)
            .order_by(PaymentApplicationLine.sequence)
        )
    )


def previous_certified(db: Session, a: PaymentApplication) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(PaymentApplication.certified_amount), 0)).where(
            PaymentApplication.contract_id == a.contract_id,
            PaymentApplication.number < a.number,
            PaymentApplication.status.in_(("certified", "paid")),
        )
    )
    return Decimal(total).quantize(Decimal("0.01"))


def compute(db: Session, a: PaymentApplication) -> dict[str, Any]:
    lines = lines_of(db, a)
    results = [
        calc.line(ln.scheduled_value, ln.previous_work, ln.this_period, ln.materials_stored, a.retention_percent)
        for ln in lines
    ]
    original = sum((ln.scheduled_value for ln in lines if ln.contract_line_id), ZERO)
    changes = sum((ln.scheduled_value for ln in lines if ln.change_order_id), ZERO)
    prev = previous_certified(db, a) if a.status == "draft" else (a.previous_certified or ZERO)
    return {
        "lines": list(zip(lines, results, strict=True)),
        "totals": calc.totals(results, original, changes, prev),
    }


# --- schedule of values ----------------------------------------------------------------------------------------------
def _sov_sources(db: Session, contract: Contract) -> list[dict[str, Any]]:
    """Contract lines in order, then approved change orders in the order they were approved."""
    out: list[dict[str, Any]] = []
    for n, ln in enumerate(
        db.scalars(select(ContractLine).where(ContractLine.contract_id == contract.id).order_by(ContractLine.sequence)),
        start=1,
    ):
        out.append(
            {
                "contract_line_id": ln.id,
                "change_order_id": None,
                "cost_code_id": ln.cost_code_id,
                "item": str(n),
                "description": ln.description,
                "scheduled_value": ln.amount,
            }
        )
    for co in db.scalars(
        select(ChangeOrder)
        .where(ChangeOrder.contract_id == contract.id, ChangeOrder.status == "approved")
        .order_by(ChangeOrder.decided_at, ChangeOrder.number)
    ):
        out.append(
            {
                "contract_line_id": None,
                "change_order_id": co.id,
                "cost_code_id": None,
                "item": co.number,
                "description": co.title,
                "scheduled_value": co.approved_amount or ZERO,
            }
        )
    return out


def _sync_lines(db: Session, ctx: TenantContext, a: PaymentApplication, previous: PaymentApplication | None) -> int:
    """Add schedule-of-values lines for sources not yet on the application (e.g. a change approved since it was
    started). Previous-work and stored figures carry forward from the previous application. Returns lines added."""
    contract = db.get(Contract, a.contract_id)
    assert contract is not None
    existing = lines_of(db, a)
    have = {(ln.contract_line_id, ln.change_order_id) for ln in existing}
    prior = {}
    if previous:
        prior = {(ln.contract_line_id, ln.change_order_id): ln for ln in lines_of(db, previous)}
    seq = max((ln.sequence for ln in existing), default=0)
    added = 0
    for src in _sov_sources(db, contract):
        key = (src["contract_line_id"], src["change_order_id"])
        if key in have:
            continue
        p = prior.get(key)
        seq += 1
        db.add(
            PaymentApplicationLine(
                id=uuid.uuid4(),
                tenant_id=ctx.tenant_id,
                application_id=a.id,
                sequence=seq,
                previous_work=(p.previous_work + p.this_period) if p else ZERO,
                this_period=ZERO,
                materials_stored=p.materials_stored if p else ZERO,
                **src,
            )
        )
        added += 1
    db.flush()
    return added


def _previous(db: Session, a: PaymentApplication) -> PaymentApplication | None:
    return db.scalar(
        select(PaymentApplication)
        .where(PaymentApplication.contract_id == a.contract_id, PaymentApplication.number < a.number)
        .order_by(PaymentApplication.number.desc())
        .limit(1)
    )


# --- lifecycle -----------------------------------------------------------------------------------------------------
def create(
    db: Session,
    ctx: TenantContext,
    project: Project,
    contract_id: uuid.UUID,
    period_to: date,
    application_date: date | None,
) -> PaymentApplication:
    ctx.require(P.PAYMENTS_EDIT)
    _assert_live(project)
    contract = db.get(Contract, contract_id)
    if contract is None or contract.project_id != project.id:
        raise NotFound("Contract not found")
    if contract.status != "executed":
        raise Conflict(
            "Payment applications can only be made against an executed contract", code="contract_not_executed"
        )
    application_date = application_date or date.today()
    if application_date > date.today():
        raise ValidationFailed(
            "Invalid input", details=[{"field": "application_date", "message": "Cannot be in the future"}]
        )
    open_app = db.scalar(
        select(PaymentApplication.number).where(
            PaymentApplication.contract_id == contract.id, PaymentApplication.status.in_(("draft", "submitted"))
        )
    )
    if open_app is not None:
        raise Conflict(
            f"Application {open_app} is still open; it must be certified before the next one",
            code="application_open",
        )
    previous = db.scalar(
        select(PaymentApplication)
        .where(PaymentApplication.contract_id == contract.id)
        .order_by(PaymentApplication.number.desc())
        .limit(1)
    )
    if previous and period_to <= previous.period_to:
        raise ValidationFailed(
            "Invalid input",
            details=[
                {"field": "period_to", "message": f"Must be after the previous period end ({previous.period_to})"}
            ],
        )
    if contract.executed_date and period_to < contract.executed_date:
        raise ValidationFailed(
            "Invalid input", details=[{"field": "period_to", "message": "Cannot be before the contract was signed"}]
        )
    if ctx.tenant.country_code == "GB":
        due = period_to + timedelta(days=7)  # JCT-style default: due 7 days after the valuation date
        final, pay_less = calc.payment_dates(due, contract.payment_terms_days)
    else:
        due = application_date + timedelta(days=contract.payment_terms_days or 30)
        final, pay_less = None, None
    a = PaymentApplication(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        project_id=project.id,
        contract_id=contract.id,
        number=(previous.number + 1) if previous else 1,
        currency=contract.currency,
        period_to=period_to,
        application_date=application_date,
        due_date=due,
        final_payment_date=final,
        pay_less_notice_date=pay_less,
        retention_percent=contract.retention_percent or ZERO,
        created_by_id=ctx.user_id,
    )
    db.add(a)
    db.flush()
    _sync_lines(db, ctx, a, previous)
    audit.record(
        db,
        ctx.actor(),
        action="payment_application.created",
        entity_type="payment_application",
        entity_id=a.id,
        project_id=project.id,
        summary=f"{label(ctx.tenant.country_code)} {a.number} started on {contract.number}",
    )
    return a


def _assert_draft(ctx: TenantContext, project: Project, a: PaymentApplication, version: int | None = None) -> None:
    ctx.require(P.PAYMENTS_EDIT)
    _assert_live(project)
    if a.status != "draft":
        raise Conflict("Only draft applications can be changed", code="application_locked")
    _check_version(a, version)


def update_header(
    db: Session, ctx: TenantContext, project: Project, a: PaymentApplication, version: int, data: dict[str, Any]
) -> None:
    _assert_draft(ctx, project, a, version)
    fields = [k for k in HEADER_FIELDS if k in data]
    for required in ("period_to", "application_date", "retention_percent"):
        if required in data and data[required] is None:
            raise ValidationFailed("Invalid input", details=[{"field": required, "message": "Required"}])
    previous = _previous(db, a)
    period_to = data.get("period_to", a.period_to)
    if previous and period_to <= previous.period_to:
        raise ValidationFailed(
            "Invalid input",
            details=[
                {"field": "period_to", "message": f"Must be after the previous period end ({previous.period_to})"}
            ],
        )
    if data.get("application_date") and data["application_date"] > date.today():
        raise ValidationFailed(
            "Invalid input", details=[{"field": "application_date", "message": "Cannot be in the future"}]
        )
    due = data.get("due_date", a.due_date)
    final = data.get("final_payment_date", a.final_payment_date)
    if due and final and final < due:
        raise ValidationFailed(
            "Invalid input", details=[{"field": "final_payment_date", "message": "Cannot be before the due date"}]
        )
    before = audit.snapshot(a, fields)
    for k in fields:
        setattr(a, k, data[k])
    a.version += 1
    db.flush()
    changes = audit.diff(before, audit.snapshot(a, fields))
    if changes:
        audit.record(
            db,
            ctx.actor(),
            action="payment_application.updated",
            entity_type="payment_application",
            entity_id=a.id,
            project_id=project.id,
            summary=f"{label(ctx.tenant.country_code)} {a.number} updated",
            changes=changes,
        )


def update_line(
    db: Session,
    ctx: TenantContext,
    project: Project,
    a: PaymentApplication,
    line_id: uuid.UUID,
    data: dict[str, Any],
) -> None:
    _assert_draft(ctx, project, a)
    ln = db.get(PaymentApplicationLine, line_id)
    if ln is None or ln.application_id != a.id:
        raise NotFound("Line not found")
    stored = data["materials_stored"] if data.get("materials_stored") is not None else ln.materials_stored
    if data.get("percent_to_date") is not None:
        this_period = calc.this_period_from_percent(
            ln.scheduled_value, data["percent_to_date"], ln.previous_work, stored
        )
    elif data.get("this_period") is not None:
        this_period = data["this_period"]
    else:
        this_period = ln.this_period
    errors = calc.line_errors(ln.scheduled_value, ln.previous_work, this_period, stored)
    if errors:
        raise ValidationFailed(errors[0], details=[{"field": "this_period", "message": m} for m in errors])
    before = audit.snapshot(ln, ["this_period", "materials_stored"])
    ln.this_period, ln.materials_stored = round_money(this_period), round_money(stored)
    a.version += 1
    db.flush()
    changes = audit.diff(before, audit.snapshot(ln, ["this_period", "materials_stored"]))
    if changes:
        audit.record(
            db,
            ctx.actor(),
            action="payment_application.line_updated",
            entity_type="payment_application",
            entity_id=a.id,
            project_id=project.id,
            summary=f"{label(ctx.tenant.country_code)} {a.number}: {ln.item} {ln.description}"[:300],
            changes=changes,
        )


def sync_schedule(
    db: Session, ctx: TenantContext, project: Project, a: PaymentApplication, version: int
) -> int:
    """Bring the schedule of values up to date (changes approved since the draft was started). Returns lines added;
    the version is bumped when anything was added so the caller reviews before submitting."""
    _assert_draft(ctx, project, a, version)
    added = _sync_lines(db, ctx, a, _previous(db, a))
    if added:
        a.version += 1
        db.flush()
    return added


def submit(db: Session, ctx: TenantContext, project: Project, a: PaymentApplication, version: int) -> None:
    _assert_draft(ctx, project, a, version)
    result = compute(db, a)
    bad = [
        f"{ln.item} {ln.description}: {msg}"
        for ln, _r in result["lines"]
        for msg in calc.line_errors(ln.scheduled_value, ln.previous_work, ln.this_period, ln.materials_stored)
    ]
    if bad:
        raise ValidationFailed("Some lines are not valid", details=[{"field": "lines", "message": m} for m in bad])
    t = result["totals"]
    a.original_sum, a.net_changes, a.work_to_date = t.original_sum, t.net_changes, t.work_to_date
    a.materials_stored, a.retention_to_date = t.materials_stored, t.retention
    a.previous_certified, a.amount_due = t.previous_certified, t.amount_due
    a.status = "submitted"
    a.submitted_at = _now()
    a.submitted_by_id = ctx.user_id
    a.version += 1
    db.flush()
    audit.record(
        db,
        ctx.actor(),
        action="payment_application.submitted",
        entity_type="payment_application",
        entity_id=a.id,
        project_id=project.id,
        summary=f"{label(ctx.tenant.country_code)} {a.number} submitted",
        changes={"completed_to_date": t.completed_to_date, "retention": t.retention, "amount_due": t.amount_due},
    )


def return_to_draft(db: Session, ctx: TenantContext, project: Project, a: PaymentApplication, version: int) -> None:
    ctx.require(P.PAYMENTS_EDIT)
    _assert_live(project)
    if a.status != "submitted":
        raise Conflict("Only submitted applications can be returned to draft", code="application_locked")
    _check_version(a, version)
    a.status = "draft"
    a.version += 1
    db.flush()
    audit.record(
        db,
        ctx.actor(),
        action="payment_application.returned_to_draft",
        entity_type="payment_application",
        entity_id=a.id,
        project_id=project.id,
        summary=f"{label(ctx.tenant.country_code)} {a.number} returned to draft",
    )


def certify(
    db: Session, ctx: TenantContext, project: Project, a: PaymentApplication, version: int, data: dict[str, Any]
) -> None:
    ctx.require(P.PAYMENTS_CERTIFY)
    _assert_live(project)
    if a.status != "submitted":
        raise Conflict("Only submitted applications can be certified", code="application_locked")
    _check_version(a, version)
    amount = data["certified_amount"] if data.get("certified_amount") is not None else a.amount_due
    assert amount is not None and a.amount_due is not None
    errors = []
    if amount > a.amount_due:
        errors.append({"field": "certified_amount", "message": "Cannot be more than the amount applied for"})
    if amount != a.amount_due and not (data.get("certification_note") or "").strip():
        errors.append(
            {"field": "certification_note", "message": "Explain why the certified amount differs from the claim"}
        )
    cdate = data.get("certified_date") or date.today()
    if cdate > date.today():
        errors.append({"field": "certified_date", "message": "Cannot be in the future"})
    if a.submitted_at and cdate < a.submitted_at.date() - timedelta(days=1):
        errors.append({"field": "certified_date", "message": "Cannot be before the application was submitted"})
    if errors:
        raise ValidationFailed("Invalid input", details=errors)
    a.certified_amount, a.certified_date = amount, cdate
    a.certification_note = data.get("certification_note")
    a.certified_by_id = ctx.user_id
    a.status = "certified"
    a.version += 1
    db.flush()
    audit.record(
        db,
        ctx.actor(),
        action="payment_application.certified",
        entity_type="payment_application",
        entity_id=a.id,
        project_id=project.id,
        summary=f"{label(ctx.tenant.country_code)} {a.number} certified",
        changes={"applied_for": a.amount_due, "certified_amount": amount},
    )


def record_payment(
    db: Session, ctx: TenantContext, project: Project, a: PaymentApplication, version: int, data: dict[str, Any]
) -> None:
    ctx.require(P.PAYMENTS_CERTIFY)
    _assert_live(project)
    if a.status != "certified":
        raise Conflict("Payment can only be recorded against a certified application", code="application_locked")
    _check_version(a, version)
    amount = data["paid_amount"] if data.get("paid_amount") is not None else a.certified_amount
    pdate = data.get("paid_date") or date.today()
    errors = []
    if pdate > date.today():
        errors.append({"field": "paid_date", "message": "Cannot be in the future"})
    if a.certified_date and pdate < a.certified_date:
        errors.append({"field": "paid_date", "message": "Cannot be before the certificate date"})
    if amount is not None and amount < 0:
        errors.append({"field": "paid_amount", "message": "Cannot be negative"})
    if errors:
        raise ValidationFailed("Invalid input", details=errors)
    a.paid_amount, a.paid_date = amount, pdate
    a.payment_reference = data.get("payment_reference")
    a.status = "paid"
    a.version += 1
    db.flush()
    audit.record(
        db,
        ctx.actor(),
        action="payment_application.paid",
        entity_type="payment_application",
        entity_id=a.id,
        project_id=project.id,
        summary=f"{label(ctx.tenant.country_code)} {a.number} payment recorded",
        changes={"certified_amount": a.certified_amount, "paid_amount": amount},
    )


def delete_draft(db: Session, ctx: TenantContext, project: Project, a: PaymentApplication) -> None:
    _assert_draft(ctx, project, a)
    audit.record(
        db,
        ctx.actor(),
        action="payment_application.deleted",
        entity_type="payment_application",
        entity_id=a.id,
        project_id=project.id,
        summary=f"Draft {label(ctx.tenant.country_code).lower()} {a.number} deleted",
    )
    db.delete(a)
    db.flush()


# --- project positions -----------------------------------------------------------------------------------------------
def outstanding(a: PaymentApplication) -> Decimal:
    """Amount certified but not (fully) paid."""
    if a.status == "certified":
        return a.certified_amount or ZERO
    if a.status == "paid":
        return max((a.certified_amount or ZERO) - (a.paid_amount or ZERO), ZERO)
    return ZERO


def is_overdue(a: PaymentApplication, today: date | None = None) -> bool:
    today = today or date.today()
    deadline = a.final_payment_date or a.due_date
    return a.status == "certified" and deadline is not None and deadline < today


def billed_to_date(db: Session, project_id: uuid.UUID) -> Decimal | None:
    """Gross completed and stored to date on the latest submitted application of each contract (None if none)."""
    latest = (
        select(PaymentApplication)
        .where(PaymentApplication.project_id == project_id, PaymentApplication.status != "draft")
        .distinct(PaymentApplication.contract_id)
        .order_by(PaymentApplication.contract_id, PaymentApplication.number.desc())
    )
    rows = list(db.scalars(latest))
    if not rows:
        return None
    return sum(((a.work_to_date or ZERO) + (a.materials_stored or ZERO) for a in rows), ZERO)


def earned_revenue(f: Forecast) -> Decimal | None:
    if f.revenue is None or not f.final_cost:
        return None
    return round_money(f.revenue * (f.cost_to_date or ZERO) / f.final_cost)


def billing_summary(db: Session, ctx: TenantContext, project: Project) -> dict[str, Any]:
    ctx.require(P.PAYMENTS_VIEW)
    apps = list_for_project(db, ctx, project)
    forecast = db.scalar(
        select(Forecast)
        .where(Forecast.project_id == project.id, Forecast.status == "approved")
        .order_by(Forecast.period.desc())
        .limit(1)
    )
    billed = billed_to_date(db, project.id)
    earned = earned_revenue(forecast) if forecast else None
    over = under = None
    if billed is not None and earned is not None:
        over, under = calc.billing_position(billed, earned)
    retention_held = ZERO
    latest_seen: set[uuid.UUID] = set()
    for a in apps:  # ordered by contract, number desc: first per contract is the latest
        if a.contract_id in latest_seen or a.status == "draft":
            continue
        latest_seen.add(a.contract_id)
        retention_held += a.retention_to_date or ZERO
    return {
        "currency": project.currency,
        "billed_to_date": billed,
        "earned_revenue": earned,
        "forecast_period": forecast.period if forecast else None,
        "over_billed": over,
        "under_billed": under,
        "certified_to_date": sum((a.certified_amount or ZERO for a in apps if a.status in ("certified", "paid")), ZERO),
        "paid_to_date": sum((a.paid_amount or ZERO for a in apps if a.status == "paid"), ZERO),
        "outstanding": sum((outstanding(a) for a in apps), ZERO),
        "awaiting_certification": sum((a.amount_due or ZERO for a in apps if a.status == "submitted"), ZERO),
        "retention_held": retention_held,
        "overdue_count": sum(1 for a in apps if is_overdue(a)),
    }
