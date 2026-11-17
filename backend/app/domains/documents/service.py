"""Document management: upload validation, immutable versions, visibility and soft deletion."""

from __future__ import annotations

import hashlib
import re
import tempfile
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, BinaryIO

import filetype
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import TenantContext
from app.core.config import get_settings
from app.core.errors import NotFound, PayloadTooLarge, ValidationFailed
from app.domains.audit import service as audit
from app.domains.documents.constants import ALLOWED_FILE_TYPES, MAGIC_REQUIRED
from app.domains.documents.models import Document, DocumentVersion
from app.domains.documents.storage import get_storage
from app.domains.projects.models import Project
from app.domains.projects.service import get_project, visible_project_ids
from app.domains.tenancy.permissions import P

DANGEROUS_MIME_PREFIXES = ("application/x-executable", "application/x-msdownload", "application/x-sharedlib",
                           "application/x-mach-binary", "application/x-dosexec", "application/x-elf")
DOC_FIELDS = ["title", "category", "discipline", "document_number", "description", "tags", "project_id"]


def sanitize_filename(name: str) -> str:
    base = PureWindowsPath(PurePosixPath(name or "").name).name
    base = unicodedata.normalize("NFKC", base)
    base = re.sub(r"[\x00-\x1f\x7f\"\\/:*?<>|]", "_", base).strip(" .")
    return (base or "file")[:255]


@dataclass
class ValidatedUpload:
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    spool: BinaryIO


def validate_and_spool(stream: BinaryIO, filename: str) -> ValidatedUpload:
    """Copy the upload to a temp file while hashing, enforce size and type allow-lists."""
    safe_name = sanitize_filename(filename)
    ext = PurePosixPath(safe_name.lower()).suffix
    if ext not in ALLOWED_FILE_TYPES:
        raise ValidationFailed(
            f"File type '{ext or 'none'}' is not allowed",
            details={"allowed": sorted(ALLOWED_FILE_TYPES)}, code="file_type_not_allowed",
        )
    max_bytes = get_settings().max_upload_bytes
    digest = hashlib.sha256()
    size = 0
    spool: BinaryIO = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)  # type: ignore[assignment]
    head = b""
    while chunk := stream.read(1024 * 1024):
        size += len(chunk)
        if size > max_bytes:
            spool.close()
            raise PayloadTooLarge(f"File exceeds the {max_bytes // (1024 * 1024)} MB upload limit")
        if len(head) < 8192:
            head += chunk[: 8192 - len(head)]
        digest.update(chunk)
        spool.write(chunk)
    if size == 0:
        spool.close()
        raise ValidationFailed("File is empty", code="file_empty")

    guessed = filetype.guess(head)
    guessed_mime = guessed.mime if guessed else None
    allowed = ALLOWED_FILE_TYPES[ext]
    if guessed_mime and guessed_mime.startswith(DANGEROUS_MIME_PREFIXES):
        spool.close()
        raise ValidationFailed("Executable content is not allowed", code="file_content_rejected")
    if ext in MAGIC_REQUIRED and guessed_mime not in allowed:
        spool.close()
        raise ValidationFailed(f"File content does not match the '{ext}' extension", code="file_content_mismatch")
    content_type = guessed_mime if guessed_mime in allowed else sorted(allowed)[0]
    if ext in {".docx", ".xlsx", ".pptx"}:
        content_type = next(m for m in allowed if m != "application/zip")
    spool.seek(0)
    return ValidatedUpload(safe_name, content_type, size, digest.hexdigest(), spool)


def _visible_documents(ctx: TenantContext):  # type: ignore[no-untyped-def]
    stmt = select(Document).where(Document.deleted_at.is_(None))
    if not ctx.has(P.PROJECTS_VIEW_ALL):
        stmt = stmt.where(or_(Document.project_id.is_(None), Document.project_id.in_(visible_project_ids(ctx))))
    return stmt


def list_documents(
    db: Session, ctx: TenantContext, *, project_id: uuid.UUID | None, category: str | None, q: str | None,
    scope: str, limit: int, offset: int,
) -> tuple[list[Document], int]:
    stmt = _visible_documents(ctx)
    if project_id:
        get_project(db, ctx, project_id)
        stmt = stmt.where(Document.project_id == project_id)
    elif scope == "organization":
        stmt = stmt.where(Document.project_id.is_(None))
    if category:
        stmt = stmt.where(Document.category == category)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Document.title.ilike(like), Document.document_number.ilike(like),
                              Document.description.ilike(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Document.updated_at.desc(), Document.id).limit(limit).offset(offset))
    return list(rows.unique()), total


def get_document(db: Session, ctx: TenantContext, document_id: uuid.UUID) -> Document:
    doc = db.scalar(_visible_documents(ctx).where(Document.id == document_id))
    if doc is None:
        raise NotFound("Document not found")
    return doc


def _store_version(db: Session, ctx: TenantContext, doc: Document, upload: ValidatedUpload,
                   revision_label: str | None, notes: str | None) -> DocumentVersion:
    version_id = uuid.uuid4()
    key = f"tenants/{ctx.tenant_id}/documents/{doc.id}/{version_id}"
    try:
        get_storage().put(key, upload.spool, upload.content_type)
    finally:
        upload.spool.close()
    doc.current_version_number += 1
    version = DocumentVersion(
        id=version_id, tenant_id=ctx.tenant_id, document_id=doc.id, version_number=doc.current_version_number,
        revision_label=revision_label, storage_key=key, original_filename=upload.filename,
        content_type=upload.content_type, size_bytes=upload.size_bytes, sha256=upload.sha256,
        # No malware scanner is integrated yet; the status says so truthfully (see docs/SECURITY.md).
        scan_status="not_scanned", notes=notes, uploaded_by_id=ctx.user_id,
    )
    db.add(version)
    db.flush()
    return version


def create_document(db: Session, ctx: TenantContext, meta: dict[str, Any], upload: ValidatedUpload,
                    revision_label: str | None) -> Document:
    project: Project | None = None
    if meta.get("project_id"):
        project = get_project(db, ctx, meta["project_id"])
        if project.archived_at is not None:
            raise ValidationFailed("Cannot add documents to an archived project")
    doc = Document(id=uuid.uuid4(), tenant_id=ctx.tenant_id, created_by_id=ctx.user_id,
                   **{k: meta.get(k) for k in DOC_FIELDS})
    db.add(doc)
    db.flush()
    version = _store_version(db, ctx, doc, upload, revision_label, None)
    audit.record(db, ctx.actor(), action="document.uploaded", entity_type="document", entity_id=doc.id,
                 project_id=doc.project_id, summary=f"Document '{doc.title}' uploaded",
                 changes={"filename": version.original_filename, "sha256": version.sha256,
                          "size_bytes": version.size_bytes})
    db.refresh(doc)
    return doc


def add_version(db: Session, ctx: TenantContext, doc: Document, upload: ValidatedUpload,
                revision_label: str | None, notes: str | None) -> Document:
    if doc.project_id:
        project = get_project(db, ctx, doc.project_id)
        if project.archived_at is not None:
            raise ValidationFailed("Cannot add documents to an archived project")
    version = _store_version(db, ctx, doc, upload, revision_label, notes)
    audit.record(db, ctx.actor(), action="document.version_added", entity_type="document", entity_id=doc.id,
                 project_id=doc.project_id,
                 summary=f"Version {version.version_number} of '{doc.title}' uploaded",
                 changes={"filename": version.original_filename, "sha256": version.sha256,
                          "revision_label": revision_label})
    db.refresh(doc)
    return doc


def update_metadata(db: Session, ctx: TenantContext, doc: Document, data: dict[str, Any]) -> Document:
    fields = [f for f in ("title", "category", "discipline", "document_number", "description", "tags") if f in data]
    before = audit.snapshot(doc, fields)
    for f in fields:
        setattr(doc, f, data[f])
    db.flush()
    changes = audit.diff(before, audit.snapshot(doc, fields))
    if changes:
        audit.record(db, ctx.actor(), action="document.updated", entity_type="document", entity_id=doc.id,
                     project_id=doc.project_id, summary=f"Document '{doc.title}' details updated", changes=changes)
    return doc


def soft_delete(db: Session, ctx: TenantContext, doc: Document) -> None:
    doc.deleted_at = datetime.now(UTC)
    db.flush()
    audit.record(db, ctx.actor(), action="document.deleted", entity_type="document", entity_id=doc.id,
                 project_id=doc.project_id, summary=f"Document '{doc.title}' deleted (versions retained)")


def get_version(doc: Document, version_number: int) -> DocumentVersion:
    for v in doc.versions:
        if v.version_number == version_number:
            return v
    raise NotFound("Version not found")
