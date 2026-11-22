"""Cost ledger (actual cost and accruals) and monthly forecasts.

cost_transactions is an immutable ledger: rows are never updated or deleted (database trigger + grants);
corrections are posted as reversing entries. Approved forecasts are frozen snapshots.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPrimaryKey


def _now() -> datetime:
    return datetime.now(UTC)


class CostImportBatch(UUIDPrimaryKey, Base):
    __tablename__ = "cost_import_batches"
    __table_args__ = (UniqueConstraint("project_id", "sha256"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), nullable=False
    )


class CostTransaction(UUIDPrimaryKey, Base):
    __tablename__ = "cost_transactions"
    __table_args__ = (
        CheckConstraint("transaction_type IN ('actual', 'accrual')", name="type_valid"),
        CheckConstraint("amount <> 0", name="amount_non_zero"),
        Index(
            "uq_cost_transactions_one_reversal",
            "reverses_id",
            unique=True,
            postgresql_where=text("reverses_id IS NOT NULL"),
        ),
        Index("ix_cost_transactions_project_date", "project_id", "transaction_date"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    cost_code_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_codes.id", ondelete="RESTRICT")
    )
    commitment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commitments.id", ondelete="RESTRICT"), index=True
    )
    vendor_company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT")
    )
    transaction_type: Mapped[str] = mapped_column(String(10), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    reverses_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_transactions.id", ondelete="RESTRICT")
    )
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_import_batches.id", ondelete="RESTRICT")
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), nullable=False
    )


class Forecast(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "forecasts"
    __table_args__ = (
        UniqueConstraint("project_id", "period"),
        CheckConstraint("status IN ('draft', 'approved')", name="status_valid"),
        CheckConstraint("extract(day from period) = 1", name="period_first_of_month"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    revenue_adjustment: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False, default=0, server_default="0")
    revenue_adjustment_note: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    # Snapshot at approval
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    revised_budget: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    cost_to_date: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    cost_to_complete: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    final_cost: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    gross_profit: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    margin_percent: Mapped[Decimal | None] = mapped_column(Numeric(9, 2))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class ForecastLine(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "forecast_lines"
    __table_args__ = (
        UniqueConstraint("forecast_id", "cost_code_id", postgresql_nulls_not_distinct=True),
        CheckConstraint(
            "method IN ('greater_of', 'budget_remaining', 'committed_remaining', 'manual')", name="method_valid"
        ),
        CheckConstraint("method <> 'manual' OR manual_ctc IS NOT NULL", name="manual_has_value"),
        CheckConstraint("manual_ctc IS NULL OR manual_ctc >= 0", name="manual_non_negative"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    forecast_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("forecasts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cost_code_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_codes.id", ondelete="RESTRICT")
    )
    method: Mapped[str] = mapped_column(String(30), nullable=False, default="greater_of", server_default="greater_of")
    manual_ctc: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    revised_budget: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    committed: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    cost_to_date: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    cost_to_complete: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    final_cost: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
