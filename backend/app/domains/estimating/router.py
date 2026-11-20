from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter

from app.api.deps import DB, Ctx
from app.core.errors import ValidationFailed
from app.domains.cost_codes.schemas import CostCodeRef
from app.domains.estimating import service
from app.domains.estimating.calc import calculate_line
from app.domains.estimating.models import Estimate
from app.domains.estimating.schemas import (
    ESTIMATE_TYPES,
    LINE_TYPES,
    AlternateOut,
    CompareOut,
    CompareRow,
    EstimateCreate,
    EstimateOut,
    EstimateUpdate,
    LineCalcOut,
    LineFields,
    LineIn,
    LineOut,
    MarkupOut,
    MarkupsIn,
    TotalsOut,
    VersionOut,
    VersionSummary,
    VersionUpdate,
)
from app.domains.projects.models import Project
from app.domains.projects.service import get_project
from app.domains.tenancy.permissions import P

router = APIRouter(tags=["estimating"])


def _estimate_out(db, ctx, estimate: Estimate, project: Project) -> EstimateOut:  # type: ignore[no-untyped-def]
    return EstimateOut(
        id=estimate.id,
        project_id=project.id,
        project_number=project.number,
        project_name=project.name,
        name=estimate.name,
        estimate_type=estimate.estimate_type,
        cost_code_set_id=estimate.cost_code_set_id,
        currency=estimate.currency,
        current_version_number=estimate.current_version_number,
        versions=[VersionSummary.model_validate(v) for v in service.versions(db, estimate)],
        can_edit=service.can_edit(ctx, project),
        created_at=estimate.created_at,
        updated_at=estimate.updated_at,
    )


def _version_out(db, ctx, project: Project, version) -> VersionOut:  # type: ignore[no-untyped-def]
    priced = service.price_version(db, version)
    t = priced.totals
    lines = [
        LineOut(
            **{
                k: getattr(line, k)
                for k in (
                    "id",
                    "sequence",
                    "line_type",
                    "inclusion",
                    "alternate_label",
                    "description",
                    "quantity",
                    "unit",
                    "labour_hours_per_unit",
                    "labour_rate",
                    "material_rate",
                    "material_waste_percent",
                    "equipment_rate",
                    "subcontract_rate",
                    "other_rate",
                    "notes",
                )
            },
            cost_code=CostCodeRef.model_validate(code) if code else None,
            calc=LineCalcOut.model_validate(result.__dict__),
        )
        for line, result, code in priced.lines
    ]
    return VersionOut(
        **VersionSummary.model_validate(version).model_dump(),
        notes=version.notes,
        price_base_date=version.price_base_date,
        is_editable=version.status == "draft" and service.can_edit(ctx, project),
        lines=lines,
        markups=[MarkupOut.model_validate(m.__dict__) for m in t.markups],
        totals=TotalsOut(
            direct_cost=t.direct_cost,
            markup_total=t.markup_total,
            total=t.total,
            alternates=[AlternateOut(label=k, amount=v) for k, v in t.alternates.items()],
            excluded_total=t.excluded_total,
            labour_hours=t.labour_hours,
            components=t.components,
        ),
    )


@router.get("/estimating/reference")
def reference(ctx: Ctx) -> dict[str, dict[str, str]]:
    return {"estimate_types": ESTIMATE_TYPES, "line_types": LINE_TYPES}


@router.post("/estimating/calculate-line", response_model=LineCalcOut)
def calculate(body: LineFields, ctx: Ctx) -> LineCalcOut:
    """Stateless preview so the UI shows build-ups computed by the same engine (no client-side arithmetic)."""
    ctx.require(P.ESTIMATES_VIEW)
    return LineCalcOut.model_validate(calculate_line(body).__dict__)


@router.get("/estimates", response_model=list[EstimateOut])
def list_estimates(db: DB, ctx: Ctx, project_id: uuid.UUID | None = None) -> list[EstimateOut]:
    return [_estimate_out(db, ctx, e, p) for e, p in service.list_estimates(db, ctx, project_id)]


@router.post("/projects/{project_id}/estimates", response_model=EstimateOut, status_code=201)
def create_estimate(project_id: uuid.UUID, body: EstimateCreate, db: DB, ctx: Ctx) -> EstimateOut:
    project = get_project(db, ctx, project_id)
    estimate = service.create_estimate(db, ctx, project, body.model_dump())
    db.commit()
    return _estimate_out(db, ctx, estimate, project)


@router.get("/estimates/{estimate_id}", response_model=EstimateOut)
def get_estimate(estimate_id: uuid.UUID, db: DB, ctx: Ctx) -> EstimateOut:
    estimate, project = service.get_estimate(db, ctx, estimate_id)
    return _estimate_out(db, ctx, estimate, project)


@router.patch("/estimates/{estimate_id}", response_model=EstimateOut)
def rename(estimate_id: uuid.UUID, body: EstimateUpdate, db: DB, ctx: Ctx) -> EstimateOut:
    estimate, project = service.get_estimate(db, ctx, estimate_id)
    service.rename_estimate(db, ctx, estimate, project, body.name)
    db.commit()
    return _estimate_out(db, ctx, estimate, project)


@router.get("/estimates/{estimate_id}/versions/{number}", response_model=VersionOut)
def get_version(estimate_id: uuid.UUID, number: int, db: DB, ctx: Ctx) -> VersionOut:
    estimate, project = service.get_estimate(db, ctx, estimate_id)
    return _version_out(db, ctx, project, service.get_version(db, estimate, number))


@router.patch("/estimates/{estimate_id}/versions/{number}", response_model=VersionOut)
def update_version(estimate_id: uuid.UUID, number: int, body: VersionUpdate, db: DB, ctx: Ctx) -> VersionOut:
    estimate, project = service.get_estimate(db, ctx, estimate_id)
    version = service.get_version(db, estimate, number)
    service.update_version(db, ctx, estimate, project, version, body.model_dump(exclude_unset=True))
    db.commit()
    return _version_out(db, ctx, project, version)


@router.post("/estimates/{estimate_id}/versions/{number}/lines", response_model=VersionOut, status_code=201)
def add_line(estimate_id: uuid.UUID, number: int, body: LineIn, db: DB, ctx: Ctx) -> VersionOut:
    estimate, project = service.get_estimate(db, ctx, estimate_id)
    version = service.get_version(db, estimate, number)
    service.add_line(db, ctx, estimate, project, version, body.model_dump())
    db.commit()
    return _version_out(db, ctx, project, version)


@router.put("/estimates/{estimate_id}/versions/{number}/lines/{line_id}", response_model=VersionOut)
def update_line(estimate_id: uuid.UUID, number: int, line_id: uuid.UUID, body: LineIn, db: DB, ctx: Ctx) -> VersionOut:
    estimate, project = service.get_estimate(db, ctx, estimate_id)
    version = service.get_version(db, estimate, number)
    service.update_line(db, ctx, estimate, project, version, service.get_line(db, version, line_id), body.model_dump())
    db.commit()
    return _version_out(db, ctx, project, version)


@router.delete("/estimates/{estimate_id}/versions/{number}/lines/{line_id}", response_model=VersionOut)
def delete_line(estimate_id: uuid.UUID, number: int, line_id: uuid.UUID, db: DB, ctx: Ctx) -> VersionOut:
    estimate, project = service.get_estimate(db, ctx, estimate_id)
    version = service.get_version(db, estimate, number)
    service.delete_line(db, ctx, estimate, project, version, service.get_line(db, version, line_id))
    db.commit()
    return _version_out(db, ctx, project, version)


@router.put("/estimates/{estimate_id}/versions/{number}/markups", response_model=VersionOut)
def set_markups(estimate_id: uuid.UUID, number: int, body: MarkupsIn, db: DB, ctx: Ctx) -> VersionOut:
    estimate, project = service.get_estimate(db, ctx, estimate_id)
    version = service.get_version(db, estimate, number)
    service.set_markups(db, ctx, estimate, project, version, [m.model_dump() for m in body.markups])
    db.commit()
    return _version_out(db, ctx, project, version)


@router.post("/estimates/{estimate_id}/versions/{number}/issue", response_model=VersionOut)
def issue(estimate_id: uuid.UUID, number: int, db: DB, ctx: Ctx) -> VersionOut:
    estimate, project = service.get_estimate(db, ctx, estimate_id)
    version = service.issue_version(db, ctx, estimate, project, service.get_version(db, estimate, number))
    db.commit()
    return _version_out(db, ctx, project, version)


@router.post("/estimates/{estimate_id}/versions/{number}/approve", response_model=VersionOut)
def approve(estimate_id: uuid.UUID, number: int, db: DB, ctx: Ctx) -> VersionOut:
    estimate, project = service.get_estimate(db, ctx, estimate_id)
    version = service.approve_version(db, ctx, estimate, project, service.get_version(db, estimate, number))
    db.commit()
    return _version_out(db, ctx, project, version)


@router.post("/estimates/{estimate_id}/versions", response_model=VersionOut, status_code=201)
def create_version(estimate_id: uuid.UUID, db: DB, ctx: Ctx) -> VersionOut:
    estimate, project = service.get_estimate(db, ctx, estimate_id)
    version = service.new_version(db, ctx, estimate, project)
    db.commit()
    return _version_out(db, ctx, project, version)


@router.get("/estimates/{estimate_id}/compare", response_model=CompareOut)
def compare(estimate_id: uuid.UUID, db: DB, ctx: Ctx, from_version: int, to_version: int) -> CompareOut:
    estimate, _ = service.get_estimate(db, ctx, estimate_id)
    if from_version == to_version:
        raise ValidationFailed("Choose two different versions")
    rows, ta, tb = service.compare(db, estimate, from_version, to_version)
    return CompareOut(
        from_version=from_version,
        to_version=to_version,
        rows=[CompareRow(**r) for r in rows],
        from_total=ta,
        to_total=tb,
        change=tb - ta + Decimal("0.00"),
    )
