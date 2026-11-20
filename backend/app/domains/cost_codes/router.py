from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile

from app.api.deps import DB, Ctx, TenantContext, require
from app.core.errors import PayloadTooLarge
from app.domains.cost_codes import service
from app.domains.cost_codes.schemas import (
    TEMPLATES,
    CostCodeIn,
    CostCodeOut,
    CostCodeSetCreate,
    CostCodeSetOut,
    CostCodeSetUpdate,
    CostCodeUpdate,
    ImportResult,
    TemplateOut,
)
from app.domains.tenancy.permissions import P

router = APIRouter(prefix="/cost-code-sets", tags=["cost codes"])
Manager = Annotated[TenantContext, Depends(require(P.COST_CODES_MANAGE))]
MAX_IMPORT_BYTES = 2 * 1024 * 1024


def _set_out(code_set, count: int = 0) -> CostCodeSetOut:  # type: ignore[no-untyped-def]
    out = CostCodeSetOut.model_validate(code_set)
    out.code_count = count
    return out


@router.get("/templates", response_model=list[TemplateOut])
def templates(ctx: Ctx) -> list[TemplateOut]:
    return [TemplateOut(key=k, name=n, level_names=lv) for k, (n, lv) in TEMPLATES.items()]


@router.get("", response_model=list[CostCodeSetOut])
def list_sets(db: DB, ctx: Ctx, include_inactive: bool = False) -> list[CostCodeSetOut]:
    service.require_read(ctx)
    return [_set_out(s, c) for s, c in service.list_sets(db, include_inactive)]


@router.post("", response_model=CostCodeSetOut, status_code=201)
def create_set(body: CostCodeSetCreate, db: DB, ctx: Manager) -> CostCodeSetOut:
    code_set = service.create_set(db, ctx, body.model_dump())
    db.commit()
    return _set_out(code_set)


@router.get("/{set_id}", response_model=CostCodeSetOut)
def get_set(set_id: uuid.UUID, db: DB, ctx: Ctx) -> CostCodeSetOut:
    service.require_read(ctx)
    code_set = service.get_set(db, set_id)
    return _set_out(code_set, len(service.list_codes(db, set_id, None, True)))


@router.patch("/{set_id}", response_model=CostCodeSetOut)
def update_set(set_id: uuid.UUID, body: CostCodeSetUpdate, db: DB, ctx: Manager) -> CostCodeSetOut:
    code_set = service.update_set(
        db, ctx, service.get_set(db, set_id), body.version, body.model_dump(exclude_unset=True, exclude={"version"})
    )
    db.commit()
    return _set_out(code_set)


@router.get("/{set_id}/codes", response_model=list[CostCodeOut])
def list_codes(
    set_id: uuid.UUID,
    db: DB,
    ctx: Ctx,
    q: Annotated[str | None, Query(max_length=100)] = None,
    include_inactive: bool = False,
) -> list[CostCodeOut]:
    service.require_read(ctx)
    service.get_set(db, set_id)
    return [CostCodeOut.model_validate(c) for c in service.list_codes(db, set_id, q, include_inactive)]


@router.post("/{set_id}/codes", response_model=CostCodeOut, status_code=201)
def create_code(set_id: uuid.UUID, body: CostCodeIn, db: DB, ctx: Manager) -> CostCodeOut:
    code = service.create_code(db, ctx, service.get_set(db, set_id), body.model_dump())
    db.commit()
    return CostCodeOut.model_validate(code)


@router.patch("/{set_id}/codes/{code_id}", response_model=CostCodeOut)
def update_code(set_id: uuid.UUID, code_id: uuid.UUID, body: CostCodeUpdate, db: DB, ctx: Manager) -> CostCodeOut:
    code = service.update_code(db, ctx, service.get_code(db, set_id, code_id), body.model_dump(exclude_unset=True))
    db.commit()
    return CostCodeOut.model_validate(code)


@router.delete("/{set_id}/codes/{code_id}", status_code=204)
def delete_code(set_id: uuid.UUID, code_id: uuid.UUID, db: DB, ctx: Manager) -> Response:
    service.delete_code(db, ctx, service.get_code(db, set_id, code_id))
    db.commit()
    return Response(status_code=204)


@router.post("/{set_id}/import", response_model=ImportResult)
def import_codes(set_id: uuid.UUID, db: DB, ctx: Manager, file: Annotated[UploadFile, File()]) -> ImportResult:
    code_set = service.get_set(db, set_id)
    content = file.file.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        raise PayloadTooLarge("Import files are limited to 2 MB")
    created, errors = service.import_csv(db, ctx, code_set, content)
    if errors:
        db.rollback()
    else:
        db.commit()
    return ImportResult(created=created, errors=errors)
