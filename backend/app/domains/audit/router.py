from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import DB, TenantContext, require
from app.core.schemas import Page
from app.domains.audit.schemas import AuditEventOut, to_out
from app.domains.audit.service import list_events
from app.domains.tenancy.permissions import P

router = APIRouter(prefix="/audit-events", tags=["audit"])


@router.get("", response_model=Page[AuditEventOut])
def audit_log(
    db: DB,
    ctx: Annotated[TenantContext, Depends(require(P.AUDIT_VIEW))],
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AuditEventOut]:
    events, total = list_events(db, ctx.tenant_id, entity_type=entity_type, entity_id=entity_id,
                                project_id=project_id, actor_user_id=actor_user_id, limit=limit, offset=offset)
    hide = not ctx.has(P.PROJECTS_FINANCIALS_VIEW)
    return Page(items=to_out(db, events, redact_financials=hide), total=total, limit=limit, offset=offset)
