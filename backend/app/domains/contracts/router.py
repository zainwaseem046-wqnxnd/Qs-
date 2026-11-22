# No `from __future__ import annotations`: route factories need real (not string) annotations for FastAPI.
import uuid
from typing import Any

from fastapi import APIRouter, Response

from app.api.deps import DB, Ctx, TenantContext
from app.domains.change_orders import service as change_service
from app.domains.companies.models import Company
from app.domains.companies.schemas import CompanyRef
from app.domains.contracts import service
from app.domains.contracts.constants import COMMITMENT_TYPES, STATUSES, prime_forms, subcontract_forms
from app.domains.contracts.schemas import (
    CommercialSummary,
    CommitmentCreate,
    CommitmentLineIn,
    CommitmentOut,
    CommitmentUpdate,
    ContractCreate,
    ContractLineIn,
    ContractOut,
    ContractUpdate,
    ContractVocab,
    ExecuteIn,
    LineOut,
    ListItem,
    StatusIn,
)
from app.domains.cost_codes.schemas import CostCodeRef
from app.domains.projects.models import Project
from app.domains.projects.service import get_project

router = APIRouter(tags=["contracts"])


def _company(db: Any, company_id: uuid.UUID | None) -> CompanyRef | None:
    c = db.get(Company, company_id) if company_id else None
    return CompanyRef.model_validate(c) if c else None


def _out(db: Any, ctx: TenantContext, kind: service.Kind, obj: Any, project: Project) -> ContractOut | CommitmentOut:
    ct = _change_totals(db, kind, obj)
    common = {
        "approved_changes": ct["approved"],
        "pending_changes": ct["pending"],
        "revised_sum": obj.original_sum + ct["approved"] if obj.original_sum is not None else None,
        "project_number": project.number,
        "project_name": project.name,
        "current_total": service.current_total(db, kind, obj),
        "is_editable": service.is_editable(ctx, kind, obj, project),
        "can_execute": ctx.has(kind.execute) and project.archived_at is None,
        "lines": [
            LineOut(
                id=ln.id,
                sequence=ln.sequence,
                description=ln.description,
                amount=ln.amount,
                quantity=getattr(ln, "quantity", None),
                unit=getattr(ln, "unit", None),
                unit_rate=getattr(ln, "unit_rate", None),
                cost_code=CostCodeRef.model_validate(code) if code else None,
            )
            for ln, code in service.lines(db, kind, obj)
        ],
    }
    fields = {
        k: getattr(obj, k)
        for k in (
            "id",
            "project_id",
            "number",
            "title",
            "contract_form",
            "status",
            "currency",
            "cost_code_set_id",
            "retention_percent",
            "retention_terms",
            "payment_terms_days",
            "start_date",
            "completion_date",
            "scope_summary",
            "original_sum",
            "executed_date",
            "executed_at",
            "closed_at",
            "version",
            "created_at",
            "updated_at",
        )
    }
    if kind is service.CONTRACT:
        extra = {
            k: getattr(obj, k)
            for k in (
                "defects_period_months",
                "liquidated_damages_amount",
                "liquidated_damages_period",
                "bond_required",
                "bond_percent",
                "insurance_notes",
            )
        }
        return ContractOut(**fields, **common, **extra, client_company=_company(db, obj.client_company_id))
    vendor = _company(db, obj.vendor_company_id)
    assert vendor is not None
    return CommitmentOut(
        **fields, **common, commitment_type=obj.commitment_type, vendor=vendor, exclusions=obj.exclusions
    )


def _change_totals(db: Any, kind: service.Kind, obj: Any) -> dict[str, Any]:
    if kind is service.CONTRACT:
        return change_service.change_totals(db, contract_id=obj.id)
    return change_service.change_totals(db, commitment_id=obj.id)


def _item(db: Any, kind: service.Kind, obj: Any, project: Project) -> ListItem:
    party = _company(db, obj.client_company_id if kind is service.CONTRACT else obj.vendor_company_id)
    return ListItem(
        id=obj.id,
        project_id=project.id,
        project_number=project.number,
        project_name=project.name,
        number=obj.number,
        title=obj.title,
        status=obj.status,
        currency=obj.currency,
        counterparty=party.name if party else None,
        commitment_type=getattr(obj, "commitment_type", None),
        current_total=service.current_total(db, kind, obj),
        original_sum=obj.original_sum,
        revised_sum=(obj.original_sum + _change_totals(db, kind, obj)["approved"])
        if obj.original_sum is not None
        else None,
        executed_date=obj.executed_date,
        updated_at=obj.updated_at,
    )


@router.get("/contracts/vocabulary", response_model=ContractVocab)
def vocabulary(ctx: Ctx) -> ContractVocab:
    country = ctx.tenant.country_code
    return ContractVocab(
        prime_forms=prime_forms(country),
        subcontract_forms=subcontract_forms(country),
        commitment_types=COMMITMENT_TYPES,
        statuses=STATUSES,
    )


@router.get("/projects/{project_id}/commercial-summary", response_model=CommercialSummary)
def commercial_summary(project_id: uuid.UUID, db: DB, ctx: Ctx) -> CommercialSummary:
    project = get_project(db, ctx, project_id)
    return CommercialSummary.model_validate(service.commercial_summary(db, ctx, project))


def _register(kind: service.Kind, path: str, create_in: type, update_in: type, line_in: type, out: type) -> None:
    @router.get(f"/{path}", response_model=list[ListItem], name=f"list_{path}")
    def list_records(
        db: DB, ctx: Ctx, project_id: uuid.UUID | None = None, status: str | None = None
    ) -> list[ListItem]:
        return [_item(db, kind, o, p) for o, p in service.list_records(db, ctx, kind, project_id, status)]

    @router.post(f"/projects/{{project_id}}/{path}", response_model=out, status_code=201, name=f"create_{path}")
    def create(project_id: uuid.UUID, body: create_in, db: DB, ctx: Ctx):  # type: ignore[no-untyped-def,valid-type]
        project = get_project(db, ctx, project_id)
        obj = service.create(db, ctx, kind, project, body.model_dump())  # type: ignore[attr-defined]
        db.commit()
        return _out(db, ctx, kind, obj, project)

    @router.get(f"/{path}/{{record_id}}", response_model=out, name=f"get_{path}")
    def get(record_id: uuid.UUID, db: DB, ctx: Ctx):  # type: ignore[no-untyped-def]
        obj, project = service.get_record(db, ctx, kind, record_id)
        return _out(db, ctx, kind, obj, project)

    @router.patch(f"/{path}/{{record_id}}", response_model=out, name=f"update_{path}")
    def update(record_id: uuid.UUID, body: update_in, db: DB, ctx: Ctx):  # type: ignore[no-untyped-def,valid-type]
        obj, project = service.get_record(db, ctx, kind, record_id)
        data = body.model_dump(exclude_unset=True, exclude={"version"})  # type: ignore[attr-defined]
        service.update(db, ctx, kind, project, obj, body.version, data)  # type: ignore[attr-defined]
        db.commit()
        return _out(db, ctx, kind, obj, project)

    @router.delete(f"/{path}/{{record_id}}", status_code=204, name=f"delete_{path}")
    def delete(record_id: uuid.UUID, db: DB, ctx: Ctx) -> Response:
        obj, project = service.get_record(db, ctx, kind, record_id)
        service.delete_draft(db, ctx, kind, project, obj)
        db.commit()
        return Response(status_code=204)

    @router.post(f"/{path}/{{record_id}}/lines", response_model=out, status_code=201, name=f"add_line_{path}")
    def add_line(record_id: uuid.UUID, body: line_in, db: DB, ctx: Ctx):  # type: ignore[no-untyped-def,valid-type]
        obj, project = service.get_record(db, ctx, kind, record_id)
        service.add_line(db, ctx, kind, project, obj, body.model_dump())  # type: ignore[attr-defined]
        db.commit()
        return _out(db, ctx, kind, obj, project)

    @router.put(f"/{path}/{{record_id}}/lines/{{line_id}}", response_model=out, name=f"update_line_{path}")
    def update_line(record_id: uuid.UUID, line_id: uuid.UUID, body: line_in, db: DB, ctx: Ctx):  # type: ignore[no-untyped-def,valid-type]
        obj, project = service.get_record(db, ctx, kind, record_id)
        service.update_line(db, ctx, kind, project, obj, service.get_line(db, kind, obj, line_id), body.model_dump())  # type: ignore[attr-defined]
        db.commit()
        return _out(db, ctx, kind, obj, project)

    @router.delete(f"/{path}/{{record_id}}/lines/{{line_id}}", response_model=out, name=f"delete_line_{path}")
    def delete_line(record_id: uuid.UUID, line_id: uuid.UUID, db: DB, ctx: Ctx):  # type: ignore[no-untyped-def]
        obj, project = service.get_record(db, ctx, kind, record_id)
        service.delete_line(db, ctx, kind, project, obj, service.get_line(db, kind, obj, line_id))
        db.commit()
        return _out(db, ctx, kind, obj, project)

    @router.post(f"/{path}/{{record_id}}/execute", response_model=out, name=f"execute_{path}")
    def execute(record_id: uuid.UUID, body: ExecuteIn, db: DB, ctx: Ctx):  # type: ignore[no-untyped-def]
        obj, project = service.get_record(db, ctx, kind, record_id)
        service.execute(db, ctx, kind, project, obj, body.version, body.executed_date)
        db.commit()
        return _out(db, ctx, kind, obj, project)

    @router.post(f"/{path}/{{record_id}}/close", response_model=out, name=f"close_{path}")
    def close(record_id: uuid.UUID, body: StatusIn, db: DB, ctx: Ctx):  # type: ignore[no-untyped-def]
        obj, project = service.get_record(db, ctx, kind, record_id)
        service.set_status(db, ctx, kind, project, obj, body.version, "closed")
        db.commit()
        return _out(db, ctx, kind, obj, project)

    @router.post(f"/{path}/{{record_id}}/void", response_model=out, name=f"void_{path}")
    def void(record_id: uuid.UUID, body: StatusIn, db: DB, ctx: Ctx):  # type: ignore[no-untyped-def]
        obj, project = service.get_record(db, ctx, kind, record_id)
        service.set_status(db, ctx, kind, project, obj, body.version, "void")
        db.commit()
        return _out(db, ctx, kind, obj, project)


_register(service.CONTRACT, "contracts", ContractCreate, ContractUpdate, ContractLineIn, ContractOut)
_register(service.COMMITMENT, "commitments", CommitmentCreate, CommitmentUpdate, CommitmentLineIn, CommitmentOut)
