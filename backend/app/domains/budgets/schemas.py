from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.core.money import CurrencyCode, DecimalOut, MoneyAmount
from app.core.schemas import ApiModel, InputModel
from app.domains.cost_codes.schemas import CostCodeRef


class BudgetFromEstimate(InputModel):
    estimate_id: uuid.UUID
    version_number: int = Field(ge=1)
    name: str = Field(default="Original budget", min_length=2, max_length=200)


class BudgetCreate(InputModel):
    name: str = Field(default="Original budget", min_length=2, max_length=200)
    cost_code_set_id: uuid.UUID | None = None
    currency: CurrencyCode | None = None


class BudgetLineIn(InputModel):
    cost_code_id: uuid.UUID | None = None
    description: str = Field(min_length=1, max_length=300)
    amount: MoneyAmount
    notes: str | None = Field(default=None, max_length=2000)


class BudgetLineOut(ApiModel):
    id: uuid.UUID
    sequence: int
    cost_code: CostCodeRef | None
    description: str
    amount: DecimalOut
    notes: str | None


class BudgetOut(ApiModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    kind: str
    status: str
    currency: str
    cost_code_set_id: uuid.UUID | None
    source_estimate_version_id: uuid.UUID | None
    source_description: str | None = None
    total: DecimalOut
    approved_at: datetime | None
    created_at: datetime
    is_editable: bool
    lines: list[BudgetLineOut]
