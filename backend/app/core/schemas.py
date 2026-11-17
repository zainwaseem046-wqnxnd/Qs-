from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class InputModel(BaseModel):
    """Request bodies: reject unknown fields so typos fail loudly instead of being ignored."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Page[T](ApiModel):
    items: list[T]
    total: int
    limit: int
    offset: int


NonEmptyStr = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
StateCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}$", to_upper=True, strip_whitespace=True)]
ZipCode = Annotated[str, StringConstraints(pattern=r"^\d{5}(-\d{4})?$", strip_whitespace=True)]


def empty_to_none(value: object) -> object:
    if isinstance(value, str) and value.strip() == "":
        return None
    return value
