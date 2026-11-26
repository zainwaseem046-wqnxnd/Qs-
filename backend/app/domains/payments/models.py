"""Payment applications (US) / interim valuations (UK) against an executed prime contract.

Lifecycle: draft <-> submitted -> certified -> paid. Lines and claim figures are editable only in draft; on
submission the summary figures are snapshotted. Certification records what the certifier (architect, contract
administrator, employer) certified; payment records what was received. Enforced by database triggers:
submitted/certified applications can only move forward, and paid applications are final.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPrimaryKey

STATUSES = ("draft", "submitted", "certified", "paid")


class PaymentApplication(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "payment_applications"
    __table_args__ = (
        UniqueConstraint("contract_id", "number"),
        CheckConstraint("status IN ('draft', 'submitted', 'certified', 'paid')", name="status_valid"),
        CheckConstraint("retention_percent BETWEEN 0 AND 100", name="retention_range"),
        CheckConstraint("number >= 1", name="number_positive"),
        CheckConstraint(
            "final_payment_date IS NULL OR due_date IS NULL OR final_payment_date >= due_date", name="final_after_due"
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    period_to: Mapped[date] = mapped_column(Date, nullable=False)
    application_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    final_payment_date: Mapped[date | None] = mapped_column(Date)
    pay_less_notice_date: Mapped[date | None] = mapped_column(Date)
    retention_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    # Snapshot at submission (NULL while draft: drafts are computed live).
    original_sum: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    net_changes: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    work_to_date: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    materials_stored: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    retention_to_date: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    previous_certified: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    amount_due: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    certified_amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    certified_date: Mapped[date | None] = mapped_column(Date)
    certification_note: Mapped[str | None] = mapped_column(Text)
    certified_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    paid_amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    paid_date: Mapped[date | None] = mapped_column(Date)
    payment_reference: Mapped[str | None] = mapped_column(String(80))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class PaymentApplicationLine(UUIDPrimaryKey, Timestamps, Base):
    """One schedule-of-values line: a contract line or an approved change order (see calc.py for columns)."""

    __tablename__ = "payment_application_lines"
    __table_args__ = (
        CheckConstraint("(contract_line_id IS NULL) <> (change_order_id IS NULL)", name="one_source"),
        UniqueConstraint("application_id", "contract_line_id"),
        UniqueConstraint("application_id", "change_order_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    contract_line_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contract_lines.id", ondelete="RESTRICT")
    )
    change_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("change_orders.id", ondelete="RESTRICT")
    )
    cost_code_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_codes.id", ondelete="RESTRICT")
    )
    item: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    scheduled_value: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    previous_work: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False, default=0, server_default="0")
    this_period: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False, default=0, server_default="0")
    materials_stored: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False, default=0, server_default="0")
