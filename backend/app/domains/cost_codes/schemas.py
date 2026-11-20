from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field, field_validator

from app.core.schemas import ApiModel, InputModel

CODE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9 ._/\-]*$"

# Templates pre-fill level NAMES only. No third-party codes or titles are shipped (ADR-009).
TEMPLATES: dict[str, tuple[str, list[str]]] = {
    "custom": ("Custom structure", []),
    "nrm1_elemental": ("NRM1-style elemental (UK)", ["Group element", "Element", "Sub-element", "Component"]),
    "nrm2_work_sections": ("NRM2-style work sections (UK)", ["Work section", "Item"]),
    "masterformat_style": ("MasterFormat-style (US)", ["Division", "Section", "Subsection"]),
    "uniformat_style": ("UniFormat-style elemental (US)", ["Major group", "Group element", "Individual element"]),
    "trade_packages": ("Trade / package breakdown", ["Package", "Trade", "Item"]),
}
MAX_LEVELS = 6


def _clean_levels(v: list[str] | None) -> list[str] | None:
    if v is None:
        return v
    cleaned = [x.strip() for x in v]
    if any(not x or len(x) > 60 for x in cleaned):
        raise ValueError("Level names must be 1-60 characters")
    if len(cleaned) > MAX_LEVELS:
        raise ValueError(f"At most {MAX_LEVELS} levels")
    return cleaned


class CostCodeSetCreate(InputModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    template_key: str = "custom"
    level_names: list[str] | None = None

    @field_validator("template_key")
    @classmethod
    def _tpl(cls, v: str) -> str:
        if v not in TEMPLATES:
            raise ValueError(f"Unknown template; expected one of {sorted(TEMPLATES)}")
        return v

    @field_validator("level_names")
    @classmethod
    def _levels(cls, v: list[str] | None) -> list[str] | None:
        return _clean_levels(v)


class CostCodeSetUpdate(InputModel):
    version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    level_names: list[str] | None = None
    is_active: bool | None = None

    @field_validator("level_names")
    @classmethod
    def _levels(cls, v: list[str] | None) -> list[str] | None:
        return _clean_levels(v)


class CostCodeSetOut(ApiModel):
    id: uuid.UUID
    name: str
    description: str | None
    template_key: str
    level_names: list[str]
    is_active: bool
    version: int
    code_count: int = 0
    created_at: datetime
    updated_at: datetime


class CostCodeIn(InputModel):
    code: str = Field(min_length=1, max_length=40, pattern=CODE_PATTERN)
    title: str = Field(min_length=1, max_length=300)
    parent_id: uuid.UUID | None = None
    unit: str | None = Field(default=None, max_length=20)


class CostCodeUpdate(InputModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    unit: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None


class CostCodeOut(ApiModel):
    id: uuid.UUID
    set_id: uuid.UUID
    parent_id: uuid.UUID | None
    code: str
    title: str
    level: int
    unit: str | None
    is_active: bool


class CostCodeRef(ApiModel):
    id: uuid.UUID
    code: str
    title: str


class ImportResult(ApiModel):
    created: int
    errors: list[dict[str, object]]


class TemplateOut(ApiModel):
    key: str
    name: str
    level_names: list[str]
