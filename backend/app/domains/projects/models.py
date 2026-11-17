from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, Timestamps, UUIDPrimaryKey
from app.domains.companies.models import Address, Company


class Project(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number"),
        CheckConstraint(
            "original_contract_value IS NULL OR original_contract_value >= 0", name="contract_value_non_negative"
        ),
        CheckConstraint("reporting_period_end_day BETWEEN 1 AND 31", name="reporting_day_range"),
        CheckConstraint(
            "planned_completion_date IS NULL OR start_date IS NULL OR planned_completion_date >= start_date",
            name="planned_dates_order",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    sector: Mapped[str] = mapped_column(String(40), nullable=False)
    project_type: Mapped[str | None] = mapped_column(String(80))
    delivery_method: Mapped[str] = mapped_column(String(40), nullable=False)
    contract_type: Mapped[str] = mapped_column(String(40), nullable=False)
    our_role: Mapped[str] = mapped_column(String(40), nullable=False)
    client_company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL")
    )
    site_address_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("addresses.id", ondelete="SET NULL")
    )
    start_date: Mapped[date | None] = mapped_column(Date)
    planned_completion_date: Mapped[date | None] = mapped_column(Date)
    actual_completion_date: Mapped[date | None] = mapped_column(Date)
    # Original (as-awarded) contract value. Revised values come from approved change orders (Phase 2).
    original_contract_value: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD", server_default="USD")
    is_public_works: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    prevailing_wage: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    retainage_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    reporting_period_end_day: Mapped[int] = mapped_column(Integer, nullable=False, default=31, server_default="31")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    site_address: Mapped[Address | None] = relationship(lazy="joined")
    client_company: Mapped[Company | None] = relationship(lazy="joined")


class ProjectMember(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_role: Mapped[str] = mapped_column(String(40), nullable=False)


class ProjectParty(UUIDPrimaryKey, Timestamps, Base):
    """A company's role on a project (owner, architect, engineer, subcontractor...)."""

    __tablename__ = "project_parties"
    __table_args__ = (UniqueConstraint("project_id", "company_id", "party_role"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    party_role: Mapped[str] = mapped_column(String(40), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    company: Mapped[Company] = relationship(lazy="joined")


class ProjectPhase(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "project_phases"
    __table_args__ = (
        UniqueConstraint("project_id", "sequence"),
        CheckConstraint("end_date IS NULL OR start_date IS NULL OR end_date >= start_date", name="dates_order"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned", server_default="planned")
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
