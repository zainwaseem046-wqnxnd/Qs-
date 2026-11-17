"""Audit trail recording and querying."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domains.audit.models import AuditEvent

# Fields never written to the audit log.
REDACTED_FIELDS = {"password_hash", "mfa_secret_encrypted", "mfa_pending_secret_encrypted", "token_hash"}


@dataclass(frozen=True)
class AuditActor:
    user_id: uuid.UUID | None
    tenant_id: uuid.UUID | None
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return value


def snapshot(obj: Any, fields: list[str]) -> dict[str, Any]:
    return {f: _json_safe(getattr(obj, f)) for f in fields if f not in REDACTED_FIELDS}


def diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, dict[str, Any]]:
    changes: dict[str, dict[str, Any]] = {}
    for key in sorted(set(before) | set(after)):
        if key in REDACTED_FIELDS:
            continue
        old, new = _json_safe(before.get(key)), _json_safe(after.get(key))
        if old != new:
            changes[key] = {"from": old, "to": new}
    return changes


def record(
    db: Session,
    actor: AuditActor,
    *,
    action: str,
    entity_type: str,
    summary: str,
    entity_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    changes: dict[str, Any] | None = None,
    tenant_id: uuid.UUID | None = None,
) -> AuditEvent:
    event = AuditEvent(
        tenant_id=tenant_id if tenant_id is not None else actor.tenant_id,
        actor_user_id=actor.user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        project_id=project_id,
        summary=summary[:500],
        changes=_json_safe(changes) if changes else None,
        context={
            k: v
            for k, v in {
                "ip": actor.ip_address,
                "user_agent": (actor.user_agent or "")[:300] or None,
                "request_id": actor.request_id,
            }.items()
            if v
        }
        or None,
    )
    db.add(event)
    db.flush()
    return event


def list_events(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    project_ids: list[uuid.UUID] | None = None,
    actor_user_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AuditEvent], int]:
    stmt = select(AuditEvent).where(AuditEvent.tenant_id == tenant_id)
    if entity_type:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditEvent.entity_id == entity_id)
    if project_id:
        stmt = stmt.where(AuditEvent.project_id == project_id)
    if project_ids is not None:
        stmt = stmt.where(AuditEvent.project_id.in_(project_ids))
    if actor_user_id:
        stmt = stmt.where(AuditEvent.actor_user_id == actor_user_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id).limit(limit).offset(offset))
    return list(rows), total
