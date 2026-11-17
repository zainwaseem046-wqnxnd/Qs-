from __future__ import annotations

import uuid
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from fastapi.responses import StreamingResponse

from app.api.deps import DB, TenantContext, require
from app.core.errors import ValidationFailed
from app.core.schemas import Page
from app.domains.documents import service
from app.domains.documents.schemas import (
    DocumentDetailOut,
    DocumentOut,
    DocumentUpdate,
    check_category,
    check_discipline,
)
from app.domains.documents.storage import get_storage
from app.domains.tenancy.permissions import P

router = APIRouter(prefix="/documents", tags=["documents"])
Viewer = Annotated[TenantContext, Depends(require(P.DOCUMENTS_VIEW))]
Uploader = Annotated[TenantContext, Depends(require(P.DOCUMENTS_VIEW, P.DOCUMENTS_UPLOAD))]


def _clean(value: str | None, max_len: int, field: str) -> str | None:
    if value is None or value.strip() == "":
        return None
    value = value.strip()
    if len(value) > max_len:
        raise ValidationFailed("Invalid input", details=[{"field": field, "message": f"Max {max_len} characters"}])
    return value


@router.get("", response_model=Page[DocumentOut])
def list_documents(
    db: DB, ctx: Viewer,
    project_id: uuid.UUID | None = None,
    category: str | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    scope: Literal["all", "organization"] = "all",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[DocumentOut]:
    rows, total = service.list_documents(db, ctx, project_id=project_id, category=category, q=q, scope=scope,
                                         limit=limit, offset=offset)
    return Page(items=[DocumentOut.model_validate(d) for d in rows], total=total, limit=limit, offset=offset)


@router.post("", response_model=DocumentDetailOut, status_code=201)
def upload_document(
    db: DB, ctx: Uploader,
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form(min_length=1, max_length=300)],
    category: Annotated[str, Form()],
    project_id: Annotated[uuid.UUID | None, Form()] = None,
    discipline: Annotated[str | None, Form()] = None,
    document_number: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    revision_label: Annotated[str | None, Form()] = None,
) -> DocumentDetailOut:
    try:
        meta = {
            "title": title.strip(), "category": check_category(category), "discipline": check_discipline(discipline),
            "document_number": _clean(document_number, 80, "document_number"),
            "description": _clean(description, 5000, "description"), "project_id": project_id,
        }
    except ValueError as exc:
        raise ValidationFailed(str(exc)) from exc
    upload = service.validate_and_spool(file.file, file.filename or "file")
    doc = service.create_document(db, ctx, meta, upload, _clean(revision_label, 40, "revision_label"))
    out = DocumentDetailOut.model_validate(doc)
    db.commit()
    return out


@router.get("/{document_id}", response_model=DocumentDetailOut)
def get_document(document_id: uuid.UUID, db: DB, ctx: Viewer) -> DocumentDetailOut:
    return DocumentDetailOut.model_validate(service.get_document(db, ctx, document_id))


@router.patch("/{document_id}", response_model=DocumentDetailOut)
def update_document(document_id: uuid.UUID, body: DocumentUpdate, db: DB, ctx: Uploader) -> DocumentDetailOut:
    doc = service.update_metadata(db, ctx, service.get_document(db, ctx, document_id),
                                  body.model_dump(exclude_unset=True))
    out = DocumentDetailOut.model_validate(doc)
    db.commit()
    return out


@router.post("/{document_id}/versions", response_model=DocumentDetailOut, status_code=201)
def upload_version(
    document_id: uuid.UUID, db: DB, ctx: Uploader,
    file: Annotated[UploadFile, File()],
    revision_label: Annotated[str | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
) -> DocumentDetailOut:
    doc = service.get_document(db, ctx, document_id)
    upload = service.validate_and_spool(file.file, file.filename or "file")
    doc = service.add_version(db, ctx, doc, upload, _clean(revision_label, 40, "revision_label"),
                              _clean(notes, 2000, "notes"))
    out = DocumentDetailOut.model_validate(doc)
    db.commit()
    return out


@router.get("/{document_id}/versions/{version_number}/download")
def download_version(document_id: uuid.UUID, version_number: int, db: DB, ctx: Viewer) -> StreamingResponse:
    doc = service.get_document(db, ctx, document_id)
    version = service.get_version(doc, version_number)
    stream = get_storage().open(version.storage_key)
    filename = version.original_filename
    ascii_name = filename.encode("ascii", "ignore").decode() or "download"
    headers = {
        "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}",
        "X-Content-Type-Options": "nosniff",
        "Content-Length": str(version.size_bytes),
        "Cache-Control": "private, no-store",
        "Content-Security-Policy": "default-src 'none'; sandbox",
    }
    return StreamingResponse(stream, media_type=version.content_type, headers=headers)


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: uuid.UUID, db: DB, ctx: Annotated[TenantContext, Depends(require(P.DOCUMENTS_DELETE))]
) -> Response:
    service.soft_delete(db, ctx, service.get_document(db, ctx, document_id))
    db.commit()
    return Response(status_code=204)
