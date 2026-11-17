from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import DB, TenantContext, require
from app.core.schemas import Page
from app.domains.companies import service
from app.domains.companies.schemas import (
    CompanyCreate,
    CompanyOut,
    CompanyUpdate,
    ContactIn,
    ContactOut,
)
from app.domains.tenancy.permissions import P

router = APIRouter(prefix="/companies", tags=["directory"])
Viewer = Annotated[TenantContext, Depends(require(P.COMPANIES_VIEW))]
Manager = Annotated[TenantContext, Depends(require(P.COMPANIES_MANAGE))]


@router.get("", response_model=Page[CompanyOut])
def list_companies(
    db: DB, ctx: Viewer,
    q: Annotated[str | None, Query(max_length=100)] = None,
    company_type: str | None = None,
    include_inactive: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[CompanyOut]:
    rows, total = service.list_companies(db, q=q, company_type=company_type, include_inactive=include_inactive,
                                         limit=limit, offset=offset)
    return Page(items=[CompanyOut.model_validate(c) for c in rows], total=total, limit=limit, offset=offset)


@router.post("", response_model=CompanyOut, status_code=201)
def create_company(body: CompanyCreate, db: DB, ctx: Manager) -> CompanyOut:
    company = service.create_company(db, ctx, body.model_dump(exclude={"address"}), body.address)
    db.commit()
    return CompanyOut.model_validate(company)


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(company_id: uuid.UUID, db: DB, ctx: Viewer) -> CompanyOut:
    return CompanyOut.model_validate(service.get_company(db, company_id))


@router.patch("/{company_id}", response_model=CompanyOut)
def update_company(company_id: uuid.UUID, body: CompanyUpdate, db: DB, ctx: Manager) -> CompanyOut:
    company = service.get_company(db, company_id)
    data = body.model_dump(exclude_unset=True, exclude={"address", "version"})
    data = {k: v for k, v in data.items() if not (k in ("name", "company_type") and v is None)}
    service.update_company(db, ctx, company, body.version, data, body.address,
                           address_provided="address" in body.model_fields_set)
    db.commit()
    return CompanyOut.model_validate(company)


@router.get("/{company_id}/contacts", response_model=list[ContactOut])
def list_contacts(company_id: uuid.UUID, db: DB, ctx: Viewer) -> list[ContactOut]:
    service.get_company(db, company_id)
    return [ContactOut.model_validate(c) for c in service.list_contacts(db, company_id)]


@router.post("/{company_id}/contacts", response_model=ContactOut, status_code=201)
def create_contact(company_id: uuid.UUID, body: ContactIn, db: DB, ctx: Manager) -> ContactOut:
    contact = service.create_contact(db, ctx, service.get_company(db, company_id), body.model_dump())
    db.commit()
    return ContactOut.model_validate(contact)


@router.put("/{company_id}/contacts/{contact_id}", response_model=ContactOut)
def update_contact(company_id: uuid.UUID, contact_id: uuid.UUID, body: ContactIn, db: DB, ctx: Manager) -> ContactOut:
    contact = service.update_contact(db, ctx, service.get_contact(db, company_id, contact_id), body.model_dump())
    db.commit()
    return ContactOut.model_validate(contact)


@router.delete("/{company_id}/contacts/{contact_id}", status_code=204)
def delete_contact(company_id: uuid.UUID, contact_id: uuid.UUID, db: DB, ctx: Manager) -> Response:
    service.delete_contact(db, ctx, service.get_contact(db, company_id, contact_id))
    db.commit()
    return Response(status_code=204)
