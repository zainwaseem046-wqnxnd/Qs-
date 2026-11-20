from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPrimaryKey


class CostCodeSet(UUIDPrimaryKey, Timestamps, Base):
    """A customer-defined cost code structure (their own format, e.g. an NRM-based or CSI-based scheme).

    ``level_names`` labels the hierarchy (e.g. ["Group element", "Element", "Sub-element"]). Templates only
    pre-fill level names; no third-party classification content is shipped (ADR-009)."""

    __tablename__ = "cost_code_sets"
    __table_args__ = (Index("uq_cost_code_sets_tenant_name", "tenant_id", text("lower(name)"), unique=True),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    template_key: Mapped[str] = mapped_column(String(40), nullable=False, default="custom", server_default="custom")
    level_names: Mapped[list[str]] = mapped_column(ARRAY(String(60)), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class CostCode(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "cost_codes"
    __table_args__ = (UniqueConstraint("set_id", "code"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_code_sets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_codes.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
