"""Change orders (US) / variations and compensation events (UK).

A change order targets exactly one executed prime contract (client side: changes revenue, and may carry a cost
budget adjustment per line) or one executed commitment (supply side: changes committed cost).

Lifecycle: draft <-> submitted -> approved | rejected; draft/submitted -> withdrawn. Content (lines, amounts) is
editable only in draft; approved/rejected/withdrawn records are final. Enforced by database triggers.
Revised sums are derived (original + approved changes); signed contracts and approved budgets are never edited.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPrimaryKey


class ChangeOrder(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "change_orders"
    __table_args__ = (
        UniqueConstraint("project_id", "number"),
        CheckConstraint("(contract_id IS NULL) <> (commitment_id IS NULL)", name="one_target"),
        CheckConstraint("status IN ('draft', 'submitted', 'approved', 'rejected', 'withdrawn')", name="status_valid"),
        CheckConstraint(
            "response_due_date IS NULL OR notified_date IS NULL OR response_due_date >= notified_date",
            name="due_after_notified",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contract_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="RESTRICT"), index=True
    )
    commitment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commitments.id", ondelete="RESTRICT"), index=True
    )
    number: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(String(40), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    schedule_impact_days: Mapped[int | None] = mapped_column(Integer)
    notified_date: Mapped[date | None] = mapped_column(Date)
    response_due_date: Mapped[date | None] = mapped_column(Date)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    decision_notes: Mapped[str | None] = mapped_column(Text)
    approved_amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    approved_budget_amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class ChangeOrderLine(UUIDPrimaryKey, Timestamps, Base):
    """Positive amounts are additions, negative amounts omissions. Measured lines: amount = round2(qty x rate),
    where quantity may be negative for omitted work. budget_amount (client-side changes only) is the cost to add
    to (or remove from) the budget for this line's cost code."""

    __tablename__ = "change_order_lines"
    __table_args__ = (CheckConstraint("(quantity IS NULL) = (unit_rate IS NULL)", name="qty_rate_together"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    change_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("change_orders.id", ondelete="CASCADE"), nullable=False, index=True
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
    budget_amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
