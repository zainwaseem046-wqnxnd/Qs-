"""Company & contact directory."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import TenantContext
from app.core.errors import Conflict, NotFound
from app.domains.audit import service as audit
from app.domains.companies.models import Address, Company, Contact
from app.domains.companies.schemas import AddressIn

COMPANY_FIELDS = ["name", "legal_name", "company_type", "trades", "website", "phone", "email", "notes", "is_active"]
ADDRESS_FIELDS = ["line1", "line2", "city", "state_code", "postal_code", "county", "country_code"]
CONTACT_FIELDS = ["first_name", "last_name", "title", "email", "phone", "mobile", "notes"]


def apply_address(
    db: Session, ctx: TenantContext, current: Address | None, data: AddressIn | None, field_prefix: str
) -> Address | None:
    """Create, update or clear an owned address. Returns the address to link (or None).

    Country rules (US state/ZIP, UK postcode) are applied using the address country, defaulting to the
    organization's country."""
    if data is None or data.is_empty():
        return None
    data = data.normalised_for(ctx.tenant.country_code, field_prefix)
    address = current or Address(id=uuid.uuid4(), tenant_id=ctx.tenant_id)
    for field in ADDRESS_FIELDS:
        setattr(address, field, getattr(data, field))
    if current is None:
        db.add(address)
    db.flush()
    return address


def address_snapshot(address: Address | None) -> dict[str, object] | None:
    return audit.snapshot(address, ADDRESS_FIELDS) if address else None


def list_companies(
    db: Session, *, q: str | None, company_type: str | None, include_inactive: bool, limit: int, offset: int
) -> tuple[list[Company], int]:
    stmt = select(Company)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Company.name.ilike(like), Company.legal_name.ilike(like), Company.email.ilike(like)))
    if company_type:
        stmt = stmt.where(Company.company_type == company_type)
    if not include_inactive:
        stmt = stmt.where(Company.is_active.is_(True))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(func.lower(Company.name)).limit(limit).offset(offset)).unique().all()
    return list(rows), total


def get_company(db: Session, company_id: uuid.UUID) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise NotFound("Company not found")
    return company


def create_company(db: Session, ctx: TenantContext, data: dict[str, object], address: AddressIn | None) -> Company:
    company = Company(id=uuid.uuid4(), tenant_id=ctx.tenant_id, **{k: data[k] for k in COMPANY_FIELDS if k in data})
    company.address = apply_address(db, ctx, None, address, "address")
    db.add(company)
    db.flush()
    audit.record(db, ctx.actor(), action="company.created", entity_type="company", entity_id=company.id,
                 summary=f"Company '{company.name}' added to directory")
    return company


def update_company(
    db: Session, ctx: TenantContext, company: Company, version: int, data: dict[str, object],
    address: AddressIn | None, address_provided: bool,
) -> Company:
    if company.version != version:
        raise Conflict("This company was changed by someone else. Reload and try again.", code="version_conflict")
    fields = [f for f in COMPANY_FIELDS if f in data]
    before = audit.snapshot(company, fields)
    before_addr = address_snapshot(company.address)
    for f in fields:
        setattr(company, f, data[f])
    if address_provided:
        company.address = apply_address(db, ctx, company.address, address, "address")
    company.version += 1
    db.flush()
    changes = audit.diff(before, audit.snapshot(company, fields))
    after_addr = address_snapshot(company.address)
    if address_provided and before_addr != after_addr:
        changes["address"] = {"from": before_addr, "to": after_addr}
    if changes:
        audit.record(db, ctx.actor(), action="company.updated", entity_type="company", entity_id=company.id,
                     summary=f"Company '{company.name}' updated", changes=changes)
    return company


def list_contacts(db: Session, company_id: uuid.UUID) -> list[Contact]:
    return list(db.scalars(select(Contact).where(Contact.company_id == company_id)
                           .order_by(Contact.last_name, Contact.first_name)))


def create_contact(db: Session, ctx: TenantContext, company: Company, data: dict[str, object]) -> Contact:
    contact = Contact(id=uuid.uuid4(), tenant_id=ctx.tenant_id, company_id=company.id, **data)
    db.add(contact)
    db.flush()
    audit.record(db, ctx.actor(), action="contact.created", entity_type="contact", entity_id=contact.id,
                 summary=f"Contact {contact.first_name} {contact.last_name} added to {company.name}")
    return contact


def get_contact(db: Session, company_id: uuid.UUID, contact_id: uuid.UUID) -> Contact:
    contact = db.get(Contact, contact_id)
    if contact is None or contact.company_id != company_id:
        raise NotFound("Contact not found")
    return contact


def update_contact(db: Session, ctx: TenantContext, contact: Contact, data: dict[str, object]) -> Contact:
    before = audit.snapshot(contact, CONTACT_FIELDS)
    for k, v in data.items():
        setattr(contact, k, v)
    db.flush()
    changes = audit.diff(before, audit.snapshot(contact, CONTACT_FIELDS))
    if changes:
        audit.record(db, ctx.actor(), action="contact.updated", entity_type="contact", entity_id=contact.id,
                     summary=f"Contact {contact.first_name} {contact.last_name} updated", changes=changes)
    return contact


def delete_contact(db: Session, ctx: TenantContext, contact: Contact) -> None:
    audit.record(db, ctx.actor(), action="contact.deleted", entity_type="contact", entity_id=contact.id,
                 summary=f"Contact {contact.first_name} {contact.last_name} deleted",
                 changes={"deleted": audit.snapshot(contact, CONTACT_FIELDS)})
    db.delete(contact)
    db.flush()
