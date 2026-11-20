"""Customer-defined cost code structures ("their own format")."""

from __future__ import annotations

import csv
import io
import re
import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import TenantContext
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.domains.audit import service as audit
from app.domains.budgets.models import BudgetLine
from app.domains.cost_codes.models import CostCode, CostCodeSet
from app.domains.cost_codes.schemas import CODE_PATTERN, TEMPLATES
from app.domains.estimating.models import EstimateLine
from app.domains.tenancy.permissions import P

MAX_IMPORT_ROWS = 5000
_CODE_RE = re.compile(CODE_PATTERN)
READ_PERMISSIONS = (P.ESTIMATES_VIEW, P.BUDGETS_VIEW, P.COST_CODES_MANAGE)


def require_read(ctx: TenantContext) -> None:
    if not any(ctx.has(p) for p in READ_PERMISSIONS):
        raise PermissionDenied("You do not have permission to view cost codes")


def list_sets(db: Session, include_inactive: bool) -> list[tuple[CostCodeSet, int]]:
    counts = dict(db.execute(select(CostCode.set_id, func.count()).group_by(CostCode.set_id)).all())
    stmt = select(CostCodeSet).order_by(func.lower(CostCodeSet.name))
    if not include_inactive:
        stmt = stmt.where(CostCodeSet.is_active.is_(True))
    return [(s, int(counts.get(s.id, 0))) for s in db.scalars(stmt)]


def get_set(db: Session, set_id: uuid.UUID) -> CostCodeSet:
    code_set = db.get(CostCodeSet, set_id)
    if code_set is None:
        raise NotFound("Cost code structure not found")
    return code_set


def _name_taken(db: Session, name: str, exclude: uuid.UUID | None = None) -> bool:
    stmt = select(CostCodeSet.id).where(func.lower(CostCodeSet.name) == name.strip().lower())
    if exclude:
        stmt = stmt.where(CostCodeSet.id != exclude)
    return db.scalar(stmt) is not None


def create_set(db: Session, ctx: TenantContext, data: dict[str, Any]) -> CostCodeSet:
    if _name_taken(db, data["name"]):
        raise Conflict("A cost code structure with this name already exists")
    levels = data.get("level_names") or TEMPLATES[data["template_key"]][1]
    if not levels:
        raise ValidationFailed(
            "Define at least one level name for a custom structure",
            details=[{"field": "level_names", "message": "Required for custom structures"}],
        )
    code_set = CostCodeSet(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        name=data["name"].strip(),
        description=data.get("description"),
        template_key=data["template_key"],
        level_names=levels,
    )
    db.add(code_set)
    db.flush()
    audit.record(
        db,
        ctx.actor(),
        action="cost_code_set.created",
        entity_type="cost_code_set",
        entity_id=code_set.id,
        summary=f"Cost code structure '{code_set.name}' created",
        changes={"levels": levels},
    )
    return code_set


def _max_depth(db: Session, set_id: uuid.UUID) -> int:
    return db.scalar(select(func.coalesce(func.max(CostCode.level), 0)).where(CostCode.set_id == set_id)) or 0


def update_set(
    db: Session, ctx: TenantContext, code_set: CostCodeSet, version: int, data: dict[str, Any]
) -> CostCodeSet:
    if code_set.version != version:
        raise Conflict("This structure was changed by someone else. Reload and try again.", code="version_conflict")
    if data.get("name") and _name_taken(db, data["name"], exclude=code_set.id):
        raise Conflict("A cost code structure with this name already exists")
    if data.get("level_names") is not None and len(data["level_names"]) < _max_depth(db, code_set.id):
        raise ValidationFailed("Existing codes use more levels than the new structure allows")
    fields = [f for f in ("name", "level_names", "is_active") if data.get(f) is not None]
    if "description" in data:
        fields.append("description")
    before = audit.snapshot(code_set, fields)
    for f in fields:
        setattr(code_set, f, data[f])
    code_set.version += 1
    db.flush()
    changes = audit.diff(before, audit.snapshot(code_set, fields))
    if changes:
        audit.record(
            db,
            ctx.actor(),
            action="cost_code_set.updated",
            entity_type="cost_code_set",
            entity_id=code_set.id,
            summary=f"Cost code structure '{code_set.name}' updated",
            changes=changes,
        )
    return code_set


def list_codes(db: Session, set_id: uuid.UUID, q: str | None, include_inactive: bool) -> list[CostCode]:
    stmt = select(CostCode).where(CostCode.set_id == set_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(CostCode.code.ilike(like), CostCode.title.ilike(like)))
    if not include_inactive:
        stmt = stmt.where(CostCode.is_active.is_(True))
    return list(db.scalars(stmt.order_by(CostCode.code)))


def get_code(db: Session, set_id: uuid.UUID, code_id: uuid.UUID) -> CostCode:
    code = db.get(CostCode, code_id)
    if code is None or code.set_id != set_id:
        raise NotFound("Cost code not found")
    return code


def _level_for(code_set: CostCodeSet, parent: CostCode | None) -> int:
    level = (parent.level + 1) if parent else 1
    if level > len(code_set.level_names):
        raise ValidationFailed(
            f"'{code_set.name}' has {len(code_set.level_names)} levels; this code would be level {level}"
        )
    return level


def create_code(db: Session, ctx: TenantContext, code_set: CostCodeSet, data: dict[str, Any]) -> CostCode:
    if db.scalar(select(CostCode.id).where(CostCode.set_id == code_set.id, CostCode.code == data["code"])):
        raise Conflict(f"Code {data['code']} already exists in this structure")
    parent = get_code(db, code_set.id, data["parent_id"]) if data.get("parent_id") else None
    code = CostCode(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        set_id=code_set.id,
        parent_id=parent.id if parent else None,
        code=data["code"].strip(),
        title=data["title"].strip(),
        unit=data.get("unit"),
        level=_level_for(code_set, parent),
    )
    db.add(code)
    db.flush()
    audit.record(
        db,
        ctx.actor(),
        action="cost_code.created",
        entity_type="cost_code",
        entity_id=code.id,
        summary=f"Cost code {code.code} '{code.title}' added to {code_set.name}",
    )
    return code


def update_code(db: Session, ctx: TenantContext, code: CostCode, data: dict[str, Any]) -> CostCode:
    fields = [f for f in ("title", "unit", "is_active") if f in data and (data[f] is not None or f == "unit")]
    before = audit.snapshot(code, fields)
    for f in fields:
        setattr(code, f, data[f])
    db.flush()
    changes = audit.diff(before, audit.snapshot(code, fields))
    if changes:
        audit.record(
            db,
            ctx.actor(),
            action="cost_code.updated",
            entity_type="cost_code",
            entity_id=code.id,
            summary=f"Cost code {code.code} updated",
            changes=changes,
        )
    return code


def delete_code(db: Session, ctx: TenantContext, code: CostCode) -> None:
    in_use = db.scalar(
        select(func.count()).select_from(EstimateLine).where(EstimateLine.cost_code_id == code.id)
    ) or db.scalar(select(func.count()).select_from(BudgetLine).where(BudgetLine.cost_code_id == code.id))
    children = db.scalar(select(func.count()).select_from(CostCode).where(CostCode.parent_id == code.id))
    if in_use or children:
        raise Conflict(
            "This code is used by estimates/budgets or has child codes. Deactivate it instead.", code="cost_code_in_use"
        )
    audit.record(
        db,
        ctx.actor(),
        action="cost_code.deleted",
        entity_type="cost_code",
        entity_id=code.id,
        summary=f"Cost code {code.code} deleted",
    )
    db.delete(code)
    db.flush()


def import_csv(
    db: Session, ctx: TenantContext, code_set: CostCodeSet, content: bytes
) -> tuple[int, list[dict[str, object]]]:
    """All-or-nothing import. Columns: code, title, parent_code (optional), unit (optional).
    Parents may appear anywhere in the file or already exist in the structure."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValidationFailed("File must be UTF-8 encoded CSV") from None
    reader = csv.DictReader(io.StringIO(text))
    headers = {h.strip().lower() for h in (reader.fieldnames or [])}
    if not {"code", "title"} <= headers:
        raise ValidationFailed("CSV must have a header row with at least 'code' and 'title' columns")
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, object]] = []
    for i, raw in enumerate(reader, start=2):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        if not any(row.values()):
            continue
        if len(rows) >= MAX_IMPORT_ROWS:
            raise ValidationFailed(f"At most {MAX_IMPORT_ROWS} rows per import")
        code, title = row.get("code", ""), row.get("title", "")
        if not code or len(code) > 40 or not _CODE_RE.match(code):
            errors.append({"row": i, "message": f"Invalid code '{code}'"})
        if not title or len(title) > 300:
            errors.append({"row": i, "message": "Title is required (max 300 characters)"})
        if len(row.get("unit", "")) > 20:
            errors.append({"row": i, "message": "Unit is too long (max 20 characters)"})
        rows.append(
            {
                "row": i,
                "code": code,
                "title": title,
                "parent_code": row.get("parent_code") or None,
                "unit": row.get("unit") or None,
            }
        )

    existing = {c.code: c for c in db.scalars(select(CostCode).where(CostCode.set_id == code_set.id))}
    seen: set[str] = set()
    for r in rows:
        if r["code"] in existing or r["code"] in seen:
            errors.append({"row": r["row"], "message": f"Duplicate code {r['code']}"})
        seen.add(r["code"])

    # Resolve levels: a row's parent is an existing code or another row in this file.
    file_rows = {r["code"]: r for r in rows}
    levels: dict[str, int] = {c: e.level for c, e in existing.items()}

    def level_of(code: str, trail: tuple[str, ...] = ()) -> int | None:
        if code in levels:
            return levels[code]
        r = file_rows.get(code)
        if r is None or code in trail:
            return None
        if r["parent_code"] is None:
            levels[code] = 1
            return 1
        parent_level = level_of(r["parent_code"], (*trail, code))
        if parent_level is None:
            return None
        levels[code] = parent_level + 1
        return levels[code]

    max_levels = len(code_set.level_names)
    for r in rows:
        lvl = level_of(r["code"])
        if lvl is None:
            errors.append({"row": r["row"], "message": f"Parent code '{r['parent_code']}' not found (or circular)"})
        elif lvl > max_levels:
            errors.append({"row": r["row"], "message": f"Code would be level {lvl}; structure has {max_levels} levels"})
    if errors:
        return 0, sorted(errors, key=lambda e: int(e["row"]))  # type: ignore[call-overload]

    ids: dict[str, uuid.UUID] = {c: e.id for c, e in existing.items()}
    for level in sorted({levels[r["code"]] for r in rows}):  # parents are flushed before children
        for r in (r for r in rows if levels[r["code"]] == level):
            new_id = uuid.uuid4()
            ids[r["code"]] = new_id
            db.add(
                CostCode(
                    id=new_id,
                    tenant_id=ctx.tenant_id,
                    set_id=code_set.id,
                    code=r["code"],
                    title=r["title"],
                    unit=r["unit"],
                    level=level,
                    parent_id=ids[r["parent_code"]] if r["parent_code"] else None,
                )
            )
        db.flush()
    audit.record(
        db,
        ctx.actor(),
        action="cost_code_set.imported",
        entity_type="cost_code_set",
        entity_id=code_set.id,
        summary=f"{len(rows)} cost codes imported into '{code_set.name}'",
    )
    return len(rows), []
