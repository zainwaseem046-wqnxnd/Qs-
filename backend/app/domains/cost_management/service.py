"""Cost ledger and forecasts.

Ledger rules: entries are never edited or deleted. A wrong entry is corrected by posting its reversal
(an equal and opposite entry referencing it; at most one reversal per entry). Imports are all-or-nothing and the
same file (by SHA-256) cannot be imported twice into a project.
"""

from __future__ import annotations

import calendar
import csv
import hashlib
import io
import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import TenantContext
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.domains.audit import service as audit
from app.domains.budgets.models import Budget
from app.domains.change_orders.models import ChangeOrder, ChangeOrderLine
from app.domains.companies.models import Company
from app.domains.contracts.models import Commitment, Contract, ContractLine
from app.domains.contracts.service import commercial_summary
from app.domains.cost_codes.models import CostCode
from app.domains.cost_management import calc
from app.domains.cost_management.models import CostImportBatch, CostTransaction, Forecast, ForecastLine
from app.domains.estimating.models import Estimate
from app.domains.projects.models import Project
from app.domains.tenancy.permissions import P

ZERO = Decimal("0.00")
MAX_IMPORT_ROWS = 10000


def _now() -> datetime:
    return datetime.now(UTC)


def period_end(period: date) -> date:
    return period.replace(day=calendar.monthrange(period.year, period.month)[1])


def _assert_live(project: Project) -> None:
    if project.archived_at is not None:
        raise Conflict("Archived projects are read-only", code="project_archived")


def project_code_set(db: Session, project: Project) -> uuid.UUID | None:
    s = db.scalar(select(Budget.cost_code_set_id).where(Budget.project_id == project.id, Budget.status == "approved"))
    if s:
        return s
    return db.scalar(
        select(Estimate.cost_code_set_id)
        .where(Estimate.project_id == project.id, Estimate.cost_code_set_id.is_not(None))
        .order_by(Estimate.updated_at.desc())
        .limit(1)
    )


# --- ledger ------------------------------------------------------------------------------------------------------
def list_transactions(
    db: Session,
    ctx: TenantContext,
    project: Project,
    *,
    cost_code_id: uuid.UUID | None,
    transaction_type: str | None,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
) -> tuple[list[CostTransaction], int, Decimal]:
    ctx.require(P.COSTS_VIEW)
    stmt = select(CostTransaction).where(CostTransaction.project_id == project.id)
    if cost_code_id:
        stmt = stmt.where(CostTransaction.cost_code_id == cost_code_id)
    if transaction_type:
        stmt = stmt.where(CostTransaction.transaction_type == transaction_type)
    if date_from:
        stmt = stmt.where(CostTransaction.transaction_date >= date_from)
    if date_to:
        stmt = stmt.where(CostTransaction.transaction_date <= date_to)
    sub = stmt.subquery()
    total = db.scalar(select(func.count()).select_from(sub)) or 0
    amount = db.scalar(select(func.coalesce(func.sum(sub.c.amount), 0))) or ZERO
    rows = db.scalars(
        stmt.order_by(CostTransaction.transaction_date.desc(), CostTransaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows), int(total), Decimal(amount).quantize(Decimal("0.01"))


def _validate_refs(db: Session, project: Project, data: dict[str, Any]) -> None:
    errors = []
    code_set = project_code_set(db, project)
    if data.get("cost_code_id"):
        code = db.get(CostCode, data["cost_code_id"])
        if code is None or (code_set and code.set_id != code_set):
            errors.append(
                {"field": "cost_code_id", "message": "Cost code not found in the project's cost code structure"}
            )
    if data.get("commitment_id"):
        c = db.get(Commitment, data["commitment_id"])
        if c is None or c.project_id != project.id or c.status not in ("executed", "closed"):
            errors.append({"field": "commitment_id", "message": "Executed commitment on this project not found"})
    if data.get("vendor_company_id") and db.get(Company, data["vendor_company_id"]) is None:
        errors.append({"field": "vendor_company_id", "message": "Company not found"})
    if data["transaction_date"] > date.today():
        errors.append({"field": "transaction_date", "message": "Cost cannot be dated in the future"})
    if errors:
        raise ValidationFailed("Invalid input", details=errors)


def post_transaction(db: Session, ctx: TenantContext, project: Project, data: dict[str, Any]) -> CostTransaction:
    ctx.require(P.COSTS_EDIT)
    _assert_live(project)
    _validate_refs(db, project, data)
    if data.get("commitment_id") and not data.get("vendor_company_id"):
        data["vendor_company_id"] = db.get(Commitment, data["commitment_id"]).vendor_company_id  # type: ignore[union-attr]
    tx = CostTransaction(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        project_id=project.id,
        created_by_id=ctx.user_id,
        **{
            k: data.get(k)
            for k in (
                "cost_code_id",
                "commitment_id",
                "vendor_company_id",
                "transaction_type",
                "reference",
                "description",
                "transaction_date",
                "amount",
            )
        },
    )
    db.add(tx)
    db.flush()
    audit.record(
        db,
        ctx.actor(),
        action="cost.posted",
        entity_type="cost_transaction",
        entity_id=tx.id,
        project_id=project.id,
        summary=f"{tx.transaction_type.title()} posted: {tx.description} ({tx.amount})",
        changes={"amount": tx.amount, "date": tx.transaction_date, "reference": tx.reference},
    )
    return tx


def reverse(db: Session, ctx: TenantContext, project: Project, tx: CostTransaction, reason: str) -> CostTransaction:
    ctx.require(P.COSTS_EDIT)
    _assert_live(project)
    if tx.reverses_id is not None:
        raise Conflict(
            "Reversing entries cannot themselves be reversed; post a new entry instead", code="invalid_reversal"
        )
    if db.scalar(select(CostTransaction.id).where(CostTransaction.reverses_id == tx.id)):
        raise Conflict("This entry has already been reversed", code="already_reversed")
    rev = CostTransaction(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        project_id=project.id,
        cost_code_id=tx.cost_code_id,
        commitment_id=tx.commitment_id,
        vendor_company_id=tx.vendor_company_id,
        transaction_type=tx.transaction_type,
        reference=tx.reference,
        description=f"Reversal: {reason.strip()}"[:300],
        transaction_date=date.today(),
        amount=-tx.amount,
        reverses_id=tx.id,
        created_by_id=ctx.user_id,
    )
    db.add(rev)
    db.flush()
    audit.record(
        db,
        ctx.actor(),
        action="cost.reversed",
        entity_type="cost_transaction",
        entity_id=tx.id,
        project_id=project.id,
        summary=f"Entry reversed ({tx.amount}): {reason.strip()}",
    )
    return rev


def get_transaction(db: Session, project: Project, tx_id: uuid.UUID) -> CostTransaction:
    tx = db.get(CostTransaction, tx_id)
    if tx is None or tx.project_id != project.id:
        raise NotFound("Cost entry not found")
    return tx


def reversed_ids(db: Session, ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not ids:
        return set()
    return set(db.scalars(select(CostTransaction.reverses_id).where(CostTransaction.reverses_id.in_(ids))))


_AMOUNT_RE = re.compile(r"^\(?-?[£$€]?-?[\d,]+(\.\d{1,2})?\)?$")


def _parse_amount(raw: str) -> Decimal:
    s = raw.strip().replace(" ", "")
    if not _AMOUNT_RE.match(s):
        raise ValueError(f"invalid amount '{raw}'")
    negative = s.startswith("(") or "-" in s
    digits = re.sub(r"[()£$€,\-]", "", s)
    try:
        value = Decimal(digits)
    except InvalidOperation as exc:
        raise ValueError(f"invalid amount '{raw}'") from exc
    return -value if negative else value


def _parse_date(raw: str, country: str) -> date:
    s = raw.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return date.fromisoformat(s)
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if not m:
        raise ValueError(
            f"invalid date '{raw}' (use YYYY-MM-DD or {'DD/MM/YYYY' if country == 'GB' else 'MM/DD/YYYY'})"
        )
    a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    day, month = (a, b) if country == "GB" else (b, a)
    return date(y, month, day)


def import_csv(
    db: Session, ctx: TenantContext, project: Project, filename: str, content: bytes
) -> tuple[int, Decimal, list[dict[str, object]]]:
    """Columns: date, cost_code, description, amount, reference?, type? (actual|accrual), commitment?
    Dates: ISO, or the organization's local format. Amounts: '1,234.50', '(1,234.50)', '-1234.5', '$1,234'."""
    ctx.require(P.COSTS_EDIT)
    _assert_live(project)
    digest = hashlib.sha256(content).hexdigest()
    if db.scalar(
        select(CostImportBatch.id).where(CostImportBatch.project_id == project.id, CostImportBatch.sha256 == digest)
    ):
        raise Conflict("This exact file has already been imported into this project", code="duplicate_import")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValidationFailed("File must be UTF-8 encoded CSV") from None
    reader = csv.DictReader(io.StringIO(text))
    headers = {(h or "").strip().lower() for h in (reader.fieldnames or [])}
    if not {"date", "cost_code", "description", "amount"} <= headers:
        raise ValidationFailed(
            "CSV needs a header row with: date, cost_code, description, amount (optional: reference, type, commitment)"
        )
    code_set = project_code_set(db, project)
    codes = {c.code: c.id for c in db.scalars(select(CostCode).where(CostCode.set_id == code_set))} if code_set else {}
    commitments = {
        c.number.lower(): c
        for c in db.scalars(
            select(Commitment).where(Commitment.project_id == project.id, Commitment.status.in_(("executed", "closed")))
        )
    }
    country = ctx.tenant.country_code
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, object]] = []
    for i, raw in enumerate(reader, start=2):
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        if not any(r.values()):
            continue
        if len(rows) >= MAX_IMPORT_ROWS:
            raise ValidationFailed(f"At most {MAX_IMPORT_ROWS} rows per import")
        row: dict[str, Any] = {"row": i}
        try:
            row["transaction_date"] = _parse_date(r.get("date", ""), country)
            if row["transaction_date"] > date.today():
                raise ValueError("date is in the future")
        except ValueError as exc:
            errors.append({"row": i, "message": str(exc)})
        try:
            row["amount"] = _parse_amount(r.get("amount", ""))
            if row["amount"] == 0:
                raise ValueError("amount cannot be zero")
        except ValueError as exc:
            errors.append({"row": i, "message": str(exc)})
        code = r.get("cost_code", "")
        if code and code not in codes:
            errors.append({"row": i, "message": f"cost code '{code}' not in the project's cost code structure"})
        row["cost_code_id"] = codes.get(code)
        if not r.get("description"):
            errors.append({"row": i, "message": "description is required"})
        row["description"] = r.get("description", "")[:300]
        row["reference"] = (r.get("reference") or None) and r["reference"][:80]
        kind = (r.get("type") or "actual").lower()
        if kind not in ("actual", "accrual"):
            errors.append({"row": i, "message": f"type must be actual or accrual, not '{kind}'"})
        row["transaction_type"] = kind
        number = (r.get("commitment") or "").lower()
        if number and number not in commitments:
            errors.append({"row": i, "message": f"executed commitment '{r['commitment']}' not found on this project"})
        com = commitments.get(number) if number else None
        row["commitment_id"] = com.id if com else None
        row["vendor_company_id"] = com.vendor_company_id if com else None
        rows.append(row)
    if errors:
        return 0, ZERO, errors
    if not rows:
        raise ValidationFailed("The file has no data rows")
    total = sum((r["amount"] for r in rows), ZERO)
    batch = CostImportBatch(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        project_id=project.id,
        filename=filename[:255],
        sha256=digest,
        row_count=len(rows),
        total=total,
        created_by_id=ctx.user_id,
    )
    db.add(batch)
    db.flush()
    for r in rows:
        db.add(
            CostTransaction(
                id=uuid.uuid4(),
                tenant_id=ctx.tenant_id,
                project_id=project.id,
                import_batch_id=batch.id,
                created_by_id=ctx.user_id,
                **{
                    k: r[k]
                    for k in (
                        "cost_code_id",
                        "commitment_id",
                        "vendor_company_id",
                        "transaction_type",
                        "reference",
                        "description",
                        "transaction_date",
                        "amount",
                    )
                },
            )
        )
    db.flush()
    audit.record(
        db,
        ctx.actor(),
        action="cost.imported",
        entity_type="project",
        entity_id=project.id,
        project_id=project.id,
        summary=f"{len(rows)} cost entries imported from {filename} (total {total})",
        changes={"sha256": digest, "rows": len(rows), "total": total},
    )
    return len(rows), total, []


def cost_to_date_by_code(
    db: Session, project_id: uuid.UUID, as_of: date | None = None
) -> dict[uuid.UUID | None, Decimal]:
    stmt = select(CostTransaction.cost_code_id, func.sum(CostTransaction.amount)).where(
        CostTransaction.project_id == project_id
    )
    if as_of:
        stmt = stmt.where(CostTransaction.transaction_date <= as_of)
    return {code: Decimal(total) for code, total in db.execute(stmt.group_by(CostTransaction.cost_code_id))}


def invoiced_to_date(db: Session, commitment_id: uuid.UUID) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(CostTransaction.amount), 0)).where(CostTransaction.commitment_id == commitment_id)
    )
    return Decimal(total).quantize(Decimal("0.01"))


# --- forecasts -----------------------------------------------------------------------------------------------------
def revised_contract_sum(db: Session, project_id: uuid.UUID) -> Decimal:
    original = db.scalar(
        select(func.coalesce(func.sum(ContractLine.amount), 0))
        .join(Contract, Contract.id == ContractLine.contract_id)
        .where(Contract.project_id == project_id, Contract.status.in_(("executed", "closed")))
    )
    changes = db.scalar(
        select(func.coalesce(func.sum(ChangeOrderLine.amount), 0))
        .join(ChangeOrder, ChangeOrder.id == ChangeOrderLine.change_order_id)
        .where(
            ChangeOrder.project_id == project_id, ChangeOrder.contract_id.is_not(None), ChangeOrder.status == "approved"
        )
    )
    return (Decimal(original) + Decimal(changes)).quantize(Decimal("0.01"))


def list_forecasts(db: Session, ctx: TenantContext, project: Project) -> list[Forecast]:
    ctx.require(P.FORECASTS_VIEW)
    return list(db.scalars(select(Forecast).where(Forecast.project_id == project.id).order_by(Forecast.period.desc())))


def get_forecast(db: Session, ctx: TenantContext, forecast_id: uuid.UUID) -> tuple[Forecast, Project]:
    from app.domains.projects.service import get_project

    ctx.require(P.FORECASTS_VIEW)
    f = db.get(Forecast, forecast_id)
    if f is None:
        raise NotFound("Forecast not found")
    return f, get_project(db, ctx, f.project_id)


def create_forecast(db: Session, ctx: TenantContext, project: Project, period: date) -> Forecast:
    ctx.require(P.FORECASTS_EDIT)
    _assert_live(project)
    period = period.replace(day=1)
    if period > date.today().replace(day=1):
        raise ValidationFailed("Forecasts can only be prepared for the current or past months")
    if db.scalar(select(Forecast.id).where(Forecast.project_id == project.id, Forecast.period == period)):
        raise Conflict("A forecast for this period already exists", code="duplicate_period")
    if db.scalar(select(Forecast.id).where(Forecast.project_id == project.id, Forecast.status == "draft")):
        raise Conflict("Approve or delete the existing draft forecast first", code="draft_exists")
    previous = db.scalar(
        select(Forecast)
        .where(Forecast.project_id == project.id, Forecast.status == "approved")
        .order_by(Forecast.period.desc())
        .limit(1)
    )
    if previous and previous.period >= period:
        raise ValidationFailed("A later forecast is already approved; prepare a later period")
    f = Forecast(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        project_id=project.id,
        period=period,
        currency=project.currency,
        created_by_id=ctx.user_id,
    )
    db.add(f)
    db.flush()
    prior = {}
    if previous:
        prior = {
            ln.cost_code_id: ln
            for ln in db.scalars(select(ForecastLine).where(ForecastLine.forecast_id == previous.id))
        }
    codes = set(cost_to_date_by_code(db, project.id).keys())
    codes |= {r["cost_code_id"] for r in commercial_summary(db, ctx, project)["rows"]}
    for code_id in codes:
        p = prior.get(code_id)
        db.add(
            ForecastLine(
                id=uuid.uuid4(),
                tenant_id=ctx.tenant_id,
                forecast_id=f.id,
                cost_code_id=code_id,
                method=p.method if p and p.method != "manual" else "greater_of",
            )
        )
    db.flush()
    audit.record(
        db,
        ctx.actor(),
        action="forecast.created",
        entity_type="forecast",
        entity_id=f.id,
        project_id=project.id,
        summary=f"Forecast for {period:%B %Y} started",
    )
    return f


def compute(db: Session, ctx: TenantContext, project: Project, f: Forecast) -> dict[str, Any]:
    """Live calculation for drafts; snapshot values for approved forecasts."""
    lines = list(db.scalars(select(ForecastLine).where(ForecastLine.forecast_id == f.id)))
    codes = {
        c.id: c
        for c in db.scalars(
            select(CostCode).where(CostCode.id.in_([ln.cost_code_id for ln in lines if ln.cost_code_id]))
        )
    }
    out_lines = []
    if f.status == "approved":
        results = [
            calc.LineForecast(
                ln.revised_budget or ZERO,
                ln.committed or ZERO,
                ln.cost_to_date or ZERO,
                ln.cost_to_complete or ZERO,
                ln.final_cost or ZERO,
                (ln.revised_budget or ZERO) - (ln.final_cost or ZERO),
            )
            for ln in lines
        ]
        revised_contract = (f.revenue or ZERO) - f.revenue_adjustment
    else:
        summary = {r["cost_code_id"]: r for r in commercial_summary(db, ctx, project)["rows"]}
        ctd = cost_to_date_by_code(db, project.id, period_end(f.period))
        results = []
        for ln in lines:
            s = summary.get(ln.cost_code_id, {})
            results.append(
                calc.forecast_line(
                    ln.method,
                    s.get("revised_budget", ZERO),
                    s.get("committed", ZERO),
                    ctd.get(ln.cost_code_id, ZERO),
                    ln.manual_ctc,
                )
            )
        revised_contract = revised_contract_sum(db, project.id)
    for ln, r in zip(lines, results, strict=True):
        code = codes.get(ln.cost_code_id) if ln.cost_code_id else None
        out_lines.append({"line": ln, "code": code, "result": r})
    out_lines.sort(key=lambda x: (x["code"] is None, x["code"].code if x["code"] else ""))
    totals = calc.project_forecast([x["result"] for x in out_lines], revised_contract, f.revenue_adjustment)
    return {"lines": out_lines, "totals": totals, "revised_contract": revised_contract}


def _assert_draft(ctx: TenantContext, project: Project, f: Forecast, version: int | None = None) -> None:
    ctx.require(P.FORECASTS_EDIT)
    _assert_live(project)
    if f.status != "draft":
        raise Conflict("Approved forecasts are locked", code="forecast_locked")
    if version is not None and f.version != version:
        raise Conflict("This forecast was changed by someone else. Reload and try again.", code="version_conflict")


def update_header(
    db: Session, ctx: TenantContext, project: Project, f: Forecast, version: int, data: dict[str, Any]
) -> None:
    _assert_draft(ctx, project, f, version)
    fields = [k for k in ("revenue_adjustment", "revenue_adjustment_note", "notes") if k in data]
    before = audit.snapshot(f, fields)
    for k in fields:
        setattr(f, k, data[k] if data[k] is not None or k != "revenue_adjustment" else ZERO)
    f.version += 1
    db.flush()
    changes = audit.diff(before, audit.snapshot(f, fields))
    if changes:
        audit.record(
            db,
            ctx.actor(),
            action="forecast.updated",
            entity_type="forecast",
            entity_id=f.id,
            project_id=project.id,
            summary=f"Forecast {f.period:%b %Y} updated",
            changes=changes,
        )


def update_line(
    db: Session, ctx: TenantContext, project: Project, f: Forecast, line_id: uuid.UUID, data: dict[str, Any]
) -> None:
    _assert_draft(ctx, project, f)
    ln = db.get(ForecastLine, line_id)
    if ln is None or ln.forecast_id != f.id:
        raise NotFound("Forecast line not found")
    if data["method"] == "manual" and data.get("manual_ctc") is None:
        raise ValidationFailed(
            "Enter the cost to complete for a manual forecast",
            details=[{"field": "manual_ctc", "message": "Required for manual"}],
        )
    before = audit.snapshot(ln, ["method", "manual_ctc", "notes"])
    ln.method = data["method"]
    ln.manual_ctc = data.get("manual_ctc") if data["method"] == "manual" else None
    ln.notes = data.get("notes")
    f.version += 1
    db.flush()
    changes = audit.diff(before, audit.snapshot(ln, ["method", "manual_ctc", "notes"]))
    if changes:
        audit.record(
            db,
            ctx.actor(),
            action="forecast.line_updated",
            entity_type="forecast",
            entity_id=f.id,
            project_id=project.id,
            summary=f"Forecast {f.period:%b %Y} line updated",
            changes=changes,
        )


def approve(db: Session, ctx: TenantContext, project: Project, f: Forecast, version: int) -> Forecast:
    ctx.require(P.FORECASTS_APPROVE)
    _assert_live(project)
    if f.status != "draft":
        raise Conflict("This forecast is already approved", code="forecast_locked")
    if f.version != version:
        raise Conflict("This forecast was changed by someone else. Reload and try again.", code="version_conflict")
    result = compute(db, ctx, project, f)
    for x in result["lines"]:  # snapshot lines first (header still draft)
        ln, r = x["line"], x["result"]
        ln.revised_budget, ln.committed, ln.cost_to_date = r.revised_budget, r.committed, r.cost_to_date
        ln.cost_to_complete, ln.final_cost = r.cost_to_complete, r.final_cost
    db.flush()
    t = result["totals"]
    f.revenue, f.revised_budget, f.cost_to_date = t.revenue, t.revised_budget, t.cost_to_date
    f.cost_to_complete, f.final_cost, f.gross_profit, f.margin_percent = (
        t.cost_to_complete,
        t.final_cost,
        t.gross_profit,
        t.margin_percent,
    )
    f.status = "approved"
    f.approved_at = _now()
    f.approved_by_id = ctx.user_id
    f.version += 1
    db.flush()
    audit.record(
        db,
        ctx.actor(),
        action="forecast.approved",
        entity_type="forecast",
        entity_id=f.id,
        project_id=project.id,
        summary=f"Forecast {f.period:%B %Y} approved",
        changes={
            "revenue": t.revenue,
            "final_cost": t.final_cost,
            "gross_profit": t.gross_profit,
            "margin_percent": t.margin_percent,
        },
    )
    return f


def delete_draft(db: Session, ctx: TenantContext, project: Project, f: Forecast) -> None:
    _assert_draft(ctx, project, f)
    audit.record(
        db,
        ctx.actor(),
        action="forecast.deleted",
        entity_type="forecast",
        entity_id=f.id,
        project_id=project.id,
        summary=f"Draft forecast {f.period:%b %Y} deleted",
    )
    db.delete(f)
    db.flush()
