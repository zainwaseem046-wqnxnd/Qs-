from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.schemas import ApiModel
from app.domains.audit.models import AuditEvent
from app.domains.identity.models import User

FINANCIAL_KEYS = {"original_contract_value", "retainage_percent"}
RESTRICTED = "[restricted]"


class AuditEventOut(ApiModel):
    id: uuid.UUID
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    project_id: uuid.UUID | None
    summary: str
    changes: dict[str, Any] | None
    actor_user_id: uuid.UUID | None
    actor_name: str | None
    occurred_at: datetime


def _redact(changes: dict[str, Any] | None) -> dict[str, Any] | None:
    if not changes:
        return changes
    out: dict[str, Any] = {}
    for key, value in changes.items():
        if key in FINANCIAL_KEYS:
            out[key] = {"from": RESTRICTED, "to": RESTRICTED} if isinstance(value, dict) else RESTRICTED
        elif isinstance(value, dict):
            out[key] = _redact(value)
        else:
            out[key] = value
    return out


def to_out(db: Session, events: list[AuditEvent], *, redact_financials: bool = False) -> list[AuditEventOut]:
    actor_ids = {e.actor_user_id for e in events if e.actor_user_id}
    names = dict(db.execute(select(User.id, User.full_name).where(User.id.in_(actor_ids))).all()) if actor_ids else {}
    return [
        AuditEventOut(
            id=e.id, action=e.action, entity_type=e.entity_type, entity_id=e.entity_id, project_id=e.project_id,
            summary=e.summary, changes=_redact(e.changes) if redact_financials else e.changes,
            actor_user_id=e.actor_user_id, actor_name=names.get(e.actor_user_id) if e.actor_user_id else None,
            occurred_at=e.occurred_at,
        )
        for e in events
    ]
