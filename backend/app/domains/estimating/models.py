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
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPrimaryKey

ZERO = text("0")


class Estimate(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "estimates"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    estimate_type: Mapped[str] = mapped_column(String(30), nullable=False)
    cost_code_set_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_code_sets.id", ondelete="RESTRICT")
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    current_version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EstimateVersion(UUIDPrimaryKey, Timestamps, Base):
    """A version of an estimate. Draft versions are editable; issued and approved versions are frozen
    (enforced by a database trigger). Totals are snapshotted when a version is issued."""

    __tablename__ = "estimate_versions"
    __table_args__ = (
        UniqueConstraint("estimate_id", "version_number"),
        CheckConstraint("status IN ('draft', 'issued', 'approved')", name="status_valid"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    estimate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("estimates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    label: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    price_base_date: Mapped[date | None] = mapped_column(Date)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    direct_cost: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    markup_total: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    total: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    issued_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class EstimateLine(UUIDPrimaryKey, Timestamps, Base):
    """One priced item. Unit cost build-up: labour (hours/unit x rate), material (rate x (1 + waste%)),
    equipment/plant, subcontract and other rates per unit. See app/domains/estimating/calc.py."""

    __tablename__ = "estimate_lines"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="quantity_non_negative"),
        CheckConstraint(
            "labour_hours_per_unit >= 0 AND labour_rate >= 0 AND material_rate >= 0 AND equipment_rate >= 0 "
            "AND subcontract_rate >= 0 AND other_rate >= 0",
            name="rates_non_negative",
        ),
        CheckConstraint("material_waste_percent >= 0 AND material_waste_percent <= 100", name="waste_range"),
        CheckConstraint("inclusion IN ('base', 'alternate', 'excluded')", name="inclusion_valid"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("estimate_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_code_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_codes.id", ondelete="RESTRICT")
    )
    line_type: Mapped[str] = mapped_column(String(30), nullable=False, default="item", server_default="item")
    inclusion: Mapped[str] = mapped_column(String(20), nullable=False, default="base", server_default="base")
    alternate_label: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    labour_hours_per_unit: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, default=0, server_default=ZERO
    )
    labour_rate: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False, default=0, server_default=ZERO)
    material_rate: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False, default=0, server_default=ZERO)
    material_waste_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=0, server_default=ZERO
    )
    equipment_rate: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False, default=0, server_default=ZERO)
    subcontract_rate: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False, default=0, server_default=ZERO)
    other_rate: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False, default=0, server_default=ZERO)
    notes: Mapped[str | None] = mapped_column(Text)


class EstimateMarkup(UUIDPrimaryKey, Timestamps, Base):
    """Percentage additions applied in sequence (preliminaries, overheads & profit, contingency...)."""

    __tablename__ = "estimate_markups"
    __table_args__ = (
        UniqueConstraint("version_id", "sequence"),
        CheckConstraint("basis IN ('direct_cost', 'cumulative')", name="basis_valid"),
        CheckConstraint("percent >= 0 AND percent <= 1000", name="percent_range"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("estimate_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    percent: Mapped[Decimal] = mapped_column(Numeric(9, 4), nullable=False)
    basis: Mapped[str] = mapped_column(String(20), nullable=False)
    include_in_budget: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
