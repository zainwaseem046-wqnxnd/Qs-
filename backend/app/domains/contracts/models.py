"""Prime contracts (with the client) and commitments (subcontracts and purchase orders with suppliers).

Lifecycle for both: draft -> executed -> closed, or draft -> void. Executing records the original sum and freezes
the commercial terms and lines (database triggers). Post-execution changes come through change orders.
"""

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
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.core.db import Base, Timestamps, UUIDPrimaryKey


class _Terms:
    """Commercial terms shared by prime contracts and commitments."""

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    contract_form: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    retention_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    retention_terms: Mapped[str | None] = mapped_column(Text)
    payment_terms_days: Mapped[int | None] = mapped_column(Integer)
    start_date: Mapped[date | None] = mapped_column(Date)
    completion_date: Mapped[date | None] = mapped_column(Date)
    scope_summary: Mapped[str | None] = mapped_column(Text)
    original_sum: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    executed_date: Mapped[date | None] = mapped_column(Date)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    @declared_attr
    def cost_code_set_id(cls) -> Mapped[uuid.UUID | None]:
        return mapped_column(UUID(as_uuid=True), ForeignKey("cost_code_sets.id", ondelete="RESTRICT"))


class Contract(_Terms, UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "contracts"
    __table_args__ = (
        UniqueConstraint("project_id", "number"),
        CheckConstraint("status IN ('draft', 'executed', 'closed', 'void')", name="status_valid"),
        CheckConstraint("retention_percent IS NULL OR retention_percent BETWEEN 0 AND 100", name="retention_range"),
        CheckConstraint(
            "liquidated_damages_period IS NULL OR liquidated_damages_period IN ('day', 'week')", name="ld_period_valid"
        ),
        CheckConstraint(
            "completion_date IS NULL OR start_date IS NULL OR completion_date >= start_date", name="dates_order"
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number: Mapped[str] = mapped_column(String(40), nullable=False)
    client_company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT")
    )
    defects_period_months: Mapped[int | None] = mapped_column(Integer)
    liquidated_damages_amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    liquidated_damages_period: Mapped[str | None] = mapped_column(String(10))
    bond_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    bond_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    insurance_notes: Mapped[str | None] = mapped_column(Text)
    executed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class ContractLine(UUIDPrimaryKey, Timestamps, Base):
    """Schedule of values / contract sum analysis line."""

    __tablename__ = "contract_lines"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_code_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_codes.id", ondelete="RESTRICT")
    )
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)


class Commitment(_Terms, UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "commitments"
    __table_args__ = (
        UniqueConstraint("project_id", "number"),
        CheckConstraint("status IN ('draft', 'executed', 'closed', 'void')", name="status_valid"),
        CheckConstraint("commitment_type IN ('subcontract', 'purchase_order')", name="type_valid"),
        CheckConstraint("retention_percent IS NULL OR retention_percent BETWEEN 0 AND 100", name="retention_range"),
        CheckConstraint(
            "completion_date IS NULL OR start_date IS NULL OR completion_date >= start_date", name="dates_order"
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number: Mapped[str] = mapped_column(String(40), nullable=False)
    commitment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    vendor_company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    exclusions: Mapped[str | None] = mapped_column(Text)
    executed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class CommitmentLine(UUIDPrimaryKey, Timestamps, Base):
    """Committed scope line. When quantity and unit rate are given, amount = round2(quantity x unit_rate)."""

    __tablename__ = "commitment_lines"
    __table_args__ = (
        CheckConstraint("(quantity IS NULL) = (unit_rate IS NULL)", name="qty_rate_together"),
        CheckConstraint("quantity IS NULL OR quantity >= 0", name="qty_non_negative"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    commitment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_code_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_codes.id", ondelete="RESTRICT")
    )
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(19, 4))
    unit: Mapped[str | None] = mapped_column(String(20))
    unit_rate: Mapped[Decimal | None] = mapped_column(Numeric(19, 6))
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
