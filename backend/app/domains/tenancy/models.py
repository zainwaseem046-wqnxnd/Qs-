from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, Timestamps, UUIDPrimaryKey


class Tenant(UUIDPrimaryKey, Timestamps, Base):
    """A customer organisation (contractor, owner, developer...). The unit of data isolation."""

    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint("slug ~ '^[a-z0-9][a-z0-9-]{1,62}$'", name="slug_format"),
        CheckConstraint("country_code IN ('US', 'GB')", name="country_code_supported"),
        CheckConstraint("data_region IN ('us', 'uk')", name="data_region_supported"),
        CheckConstraint("measurement_system IN ('us_customary', 'metric')", name="measurement_system_supported"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(63), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    default_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD", server_default="USD")
    measurement_system: Mapped[str] = mapped_column(
        String(20), nullable=False, default="us_customary", server_default="us_customary"
    )
    home_state: Mapped[str | None] = mapped_column(String(2))
    # Business country (drives defaults and address rules) and the regional deployment holding the data.
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, default="US", server_default="US")
    data_region: Mapped[str] = mapped_column(String(2), nullable=False, default="us", server_default="us")
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="America/New_York", server_default="America/New_York"
    )


class Permission(Base):
    """Global permission catalog (seeded by migrations, read-only at runtime)."""

    __tablename__ = "permissions"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)


class Role(UUIDPrimaryKey, Timestamps, Base):
    """System roles have tenant_id NULL and are visible to every tenant; custom roles are tenant-owned."""

    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "key"),
        Index("uq_roles_system_key", "key", unique=True, postgresql_where=text("tenant_id IS NULL")),
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))

    permissions: Mapped[list[RolePermission]] = relationship(
        back_populates="role", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def permission_keys(self) -> list[str]:
        return sorted(p.permission_key for p in self.permissions)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_key: Mapped[str] = mapped_column(
        String(64), ForeignKey("permissions.key", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[Role] = relationship(back_populates="permissions")


class TenantMembership(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "tenant_memberships"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    job_title: Mapped[str | None] = mapped_column(String(120))


class Invitation(UUIDPrimaryKey, Base):
    __tablename__ = "invitations"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    invited_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
