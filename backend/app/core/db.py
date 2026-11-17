"""Database engine, ORM base and Row-Level Security (RLS) context management.

Tenant isolation is enforced in two independent layers:

1. Application layer: every request resolves an authenticated user and an active tenant membership,
   and every service query filters by ``tenant_id``.
2. Database layer: PostgreSQL RLS policies compare each row's ``tenant_id`` with the transaction-local
   setting ``app.tenant_id``. The API connects as a non-owner role without BYPASSRLS, so a bug in
   layer 1 cannot leak another tenant's rows.

The settings are applied with ``set_config(..., is_local => true)`` so they are scoped to a transaction
and cannot leak between pooled connections. The session remembers the context and re-applies it at the
start of each new transaction (see ``_reapply_rls_context``). Route handlers commit once at the end of
the unit of work; services only flush.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import datetime

from sqlalchemy import DateTime, MetaData, create_engine, event, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import get_settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPrimaryKey:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=10, max_overflow=10)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, autoflush=True)
    return _engine


def reset_engine() -> None:
    """Dispose the engine (used by tests when settings change)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session (and one transaction) per request.

    Route handlers that mutate data call ``db.commit()`` explicitly before returning.
    Anything not committed is rolled back here.
    """
    db = session_factory()()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


_SET_CONTEXT_SQL = text("SELECT set_config('app.user_id', :u, true), set_config('app.tenant_id', :t, true)")
_RLS_KEY = "rls_context"


def set_rls_context(db: Session, *, user_id: uuid.UUID | None = None, tenant_id: uuid.UUID | None = None) -> None:
    """Set the RLS context for this session.

    The values are applied transaction-locally now, and remembered in ``session.info`` so the
    ``after_begin`` hook below re-applies them to every later transaction on the same session
    (for example, reloading attributes after ``commit()``). Sessions are request-scoped, so the
    context never outlives the request.
    """
    params = {"u": str(user_id) if user_id else "", "t": str(tenant_id) if tenant_id else ""}
    db.info[_RLS_KEY] = params
    db.execute(_SET_CONTEXT_SQL, params)


@event.listens_for(Session, "after_begin")
def _reapply_rls_context(session: Session, _transaction: object, connection: Connection) -> None:
    params = session.info.get(_RLS_KEY)
    if params:
        connection.execute(_SET_CONTEXT_SQL, params)
