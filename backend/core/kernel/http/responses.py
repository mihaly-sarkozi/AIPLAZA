# backend/core/kernel/http/responses.py
# Feladat: Közös HTTP response DTO-k az ad-hoc {"ok": ...}, {"status": ...}
# és lapozott listaválaszok kiváltására. Public kernel HTTP contract.

from __future__ import annotations

from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, computed_field


class OperationStatus(StrEnum):
    OK = "ok"
    SUCCESS = "success"
    ACCEPTED = "accepted"
    SKIPPED = "skipped"


class BaseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str | None = None


class ErrorResponse(BaseResponse):
    code: str
    message: str
    details: dict[str, Any] | None = None


T = TypeVar("T")


class PageResponse(BaseResponse, Generic[T]):
    items: list[T]
    total: int | None = None
    limit: int | None = None
    offset: int | None = None
    next_cursor: str | None = None


class OperationStatusResponse(BaseResponse):
    status: OperationStatus = OperationStatus.OK
    message: str | None = None
    reason: str | None = None
    details: dict[str, Any] | None = None
    legacy_ok: bool = Field(default=True, alias="ok", exclude=True)

    @computed_field(alias="ok", repr=False)
    @property
    def ok(self) -> bool:
        return self.legacy_ok

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        payload = super().model_dump(*args, **kwargs)
        if not kwargs.get("by_alias", False):
            payload.pop("ok", None)
        return payload


__all__ = [
    "BaseResponse",
    "ErrorResponse",
    "OperationStatus",
    "OperationStatusResponse",
    "PageResponse",
]
