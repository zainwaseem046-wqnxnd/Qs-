from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field, field_validator

from app.core.schemas import ApiModel, InputModel
from app.domains.documents.constants import DISCIPLINES, DOCUMENT_CATEGORIES


def check_category(v: str) -> str:
    if v not in DOCUMENT_CATEGORIES:
        raise ValueError("Unknown document category")
    return v


def check_discipline(v: str | None) -> str | None:
    if v in (None, ""):
        return None
    if v not in DISCIPLINES:
        raise ValueError("Unknown discipline")
    return v


class DocumentVersionOut(ApiModel):
    id: uuid.UUID
    version_number: int
    revision_label: str | None
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    scan_status: str
    notes: str | None
    uploaded_by_id: uuid.UUID | None
    created_at: datetime


class DocumentOut(ApiModel):
    id: uuid.UUID
    project_id: uuid.UUID | None
    title: str
    category: str
    discipline: str | None
    document_number: str | None
    description: str | None
    tags: list[str] | None
    current_version_number: int
    current_version: DocumentVersionOut | None
    created_at: datetime
    updated_at: datetime


class DocumentDetailOut(DocumentOut):
    versions: list[DocumentVersionOut]


class DocumentUpdate(InputModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    category: str | None = None
    discipline: str | None = None
    document_number: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=5000)
    tags: list[str] | None = Field(default=None, max_length=20)

    @field_validator("category")
    @classmethod
    def _cat(cls, v: str | None) -> str | None:
        return check_category(v) if v is not None else v

    @field_validator("discipline")
    @classmethod
    def _disc(cls, v: str | None) -> str | None:
        return check_discipline(v)
